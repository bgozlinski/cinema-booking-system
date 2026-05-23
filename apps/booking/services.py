from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.cinema.models import Screening
from apps.payments.services import create_checkout_session


class BookingError(Exception):
    """Base for booking-creation domain errors (caught by the view)."""


class NotEnoughSeatsError(BookingError):
    """Requested seats exceed availability at lock time (race lost or sold out)."""

    def __init__(self, available: int) -> None:
        self.available = available
        super().__init__(f"Dostępnych jest tylko {available} miejsc — wybierz mniejszą liczbę.")


class ScreeningInPastError(BookingError):
    """Screening already started by lock time."""

    def __init__(self) -> None:
        super().__init__("Seans już się rozpoczął — nie można zarezerwować miejsc.")


def create_booking(*, user, screening: Screening, seats_count: int) -> tuple[Booking, str]:
    """Create a PENDING booking race-safely and return (booking, checkout_url).

    Locks the Screening row, re-checks availability + start time under the lock
    (authoritative — the form check in US-19 is a pre-check), creates the PENDING
    booking with a 15-minute expiry, commits, then (outside the lock) creates the
    Stripe checkout session (stubbed until US-24).

    Caller (BookingForm / API serializer) owns seats_count range [1, 10]; this
    service enforces only the lock-dependent rules.
    """
    with transaction.atomic():
        locked = Screening.objects.select_for_update().get(pk=screening.pk)
        if locked.is_in_past():
            raise ScreeningInPastError()
        available = locked.available_seats_count()
        if seats_count > available:
            raise NotEnoughSeatsError(available=available)
        booking = Booking.objects.create(
            user=user,
            screening=locked,
            seats_count=seats_count,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

    checkout_url, session_id = create_checkout_session(booking)
    if session_id:
        booking.stripe_session_id = session_id
        booking.save(update_fields=["stripe_session_id"])

    return booking, checkout_url
