from datetime import timedelta

import stripe
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.booking.models import Booking, BookingStatus
from apps.cinema.models import Screening
from apps.payments.services import create_checkout_session, create_refund


class BookingError(Exception):
    """Base for booking-creation domain errors (caught by the view)."""


class NotEnoughSeatsError(BookingError):
    """Requested seats exceed availability at lock time (race lost or sold out)."""

    def __init__(self, available: int) -> None:
        self.available = available
        super().__init__(
            ngettext(
                "Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę.",
                "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę.",
                available,
            )
            % {"count": available}
        )


class ScreeningInPastError(BookingError):
    """Screening already started by lock time."""

    def __init__(self) -> None:
        super().__init__(_("Seans już się rozpoczął — nie można zarezerwować miejsc."))


def create_booking(*, user, screening: Screening, seats_count: int) -> Booking:
    """Create a PENDING booking race-safely (FR-07). Returns the booking.

    The Stripe checkout session is created separately by start_checkout (US-24).
    Caller owns seats_count range [1, 10].
    """
    with transaction.atomic():
        locked = Screening.objects.select_for_update().get(pk=screening.pk)
        if locked.is_in_past():
            raise ScreeningInPastError()
        available = locked.available_seats_count()
        if seats_count > available:
            raise NotEnoughSeatsError(available=available)
        return Booking.objects.create(
            user=user,
            screening=locked,
            seats_count=seats_count,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15),
        )


def start_checkout(*, booking: Booking) -> str:
    """Create a Stripe Checkout session for a PENDING booking; return its URL.

    Persists the returned stripe_session_id. Lets stripe.StripeError propagate to
    the view. Shared by create + retry flows.
    """
    checkout_url, session_id = create_checkout_session(booking)
    booking.stripe_session_id = session_id
    booking.save(update_fields=["stripe_session_id"])
    return checkout_url


class BookingNotCancellableError(BookingError):
    """Booking can't be cancelled (wrong status, too late, or already cancelled)."""

    def __init__(self) -> None:
        super().__init__(_("Tej rezerwacji nie można już anulować."))


def cancel_booking(*, booking: Booking) -> Booking:
    """Cancel a booking race-safely (FR-10 + FR-24 refund).

    A CONFIRMED booking with a payment is refunded via Stripe inside the transaction
    (static idempotency key) before the status flips — a Stripe failure rolls back and
    raises RefundError, so we never end up CANCELLED without a refund. PENDING bookings
    cancel without any Stripe call. Caller verifies ownership.
    """
    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(pk=booking.pk)
        if not locked.can_be_cancelled():
            raise BookingNotCancellableError()
        if locked.status == BookingStatus.CONFIRMED and locked.stripe_payment_intent_id:
            try:
                refund_id = create_refund(locked)
            except stripe.StripeError as exc:
                raise RefundError() from exc
            locked.refund_id = refund_id
            locked.refunded_at = timezone.now()
        locked.status = BookingStatus.CANCELLED
        locked.expires_at = None
        locked.save(update_fields=["status", "expires_at", "refund_id", "refunded_at"])
    return locked


class RefundError(BookingError):
    """Stripe refund failed during cancellation — booking left unchanged."""

    def __init__(self) -> None:
        super().__init__(
            _("Anulowanie nieudane — zwrot płatności nie powiódł się. Skontaktuj się z obsługą.")
        )


class BookingNotRefundableError(BookingError):
    """Booking can't be refunded (not CONFIRMED or no payment to refund)."""

    def __init__(self) -> None:
        super().__init__(_("Tej rezerwacji nie można zwrócić."))


def refund_booking(*, booking: Booking) -> Booking:
    """Admin manual refund (FR-19) — overrides the auto cancel rules.

    Unlike cancel_booking, no can_be_cancelled() time check: an admin can refund a
    CONFIRMED booking regardless of how close the screening is. The refund runs inside
    the transaction before the status flips, so a Stripe failure rolls back (never
    CANCELLED without a refund).
    """
    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(pk=booking.pk)
        if locked.status != BookingStatus.CONFIRMED or not locked.stripe_payment_intent_id:
            raise BookingNotRefundableError()
        try:
            refund_id = create_refund(locked)
        except stripe.StripeError as exc:
            raise RefundError() from exc
        locked.refund_id = refund_id
        locked.refunded_at = timezone.now()
        locked.status = BookingStatus.CANCELLED
        locked.save(update_fields=["status", "refund_id", "refunded_at"])
    return locked
