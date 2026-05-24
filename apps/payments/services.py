import uuid

import stripe
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.payments.models import StripeEvent

stripe.api_key = settings.STRIPE_API_KEY


def create_checkout_session(booking: Booking) -> tuple[str, str]:
    """Create a real Stripe Checkout Session for a PENDING booking (FR-21).

    Returns (checkout_url, session_id). Raises stripe.error.StripeError on
    API/network failure — the caller handles it. No DB writes here.
    """
    detail_path = reverse("booking:detail", kwargs={"pk": booking.id})
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "pln",
                    "unit_amount": int(booking.total_price * 100),
                    "product_data": {
                        "name": f"Booking #{booking.id} — {booking.screening.movie.title}",
                    },
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(booking.id),
        success_url=f"{settings.BASE_URL}{detail_path}?stripe=success",
        cancel_url=f"{settings.BASE_URL}{detail_path}?stripe=cancelled",
        idempotency_key=uuid.uuid4().hex,
    )
    return session.url or "", session.id


def process_webhook_event(event: dict) -> bool:
    """Idempotently process a verified Stripe event. Returns True if newly processed.

    get_or_create + dispatch + processed_at run in one transaction, so a committed
    StripeEvent row means the event was fully processed. Duplicates return False.
    """
    with transaction.atomic():
        stripe_event, created = StripeEvent.objects.get_or_create(
            event_id=event["id"],
            defaults={"event_type": event["type"], "payload": event},
        )
        if not created:
            return False
        _dispatch(event)
        stripe_event.processed_at = timezone.now()
        stripe_event.save(update_fields=["processed_at"])
    return True


def _dispatch(event: dict) -> None:
    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type == "checkout.session.completed":
        _confirm_booking(obj)
    elif event_type == "checkout.session.expired":
        _expire_booking(obj)
    # any other type → audit-logged only (no state change)


def _confirm_booking(session: dict) -> None:
    booking = _lock_booking(session.get("client_reference_id"))
    if booking is None or booking.status != BookingStatus.PENDING:
        return
    booking.status = BookingStatus.CONFIRMED
    booking.stripe_payment_intent_id = session.get("payment_intent") or ""
    booking.expires_at = None
    booking.save(update_fields=["status", "stripe_payment_intent_id", "expires_at"])


def _expire_booking(session: dict) -> None:
    booking = _lock_booking(session.get("client_reference_id"))
    if booking is None or booking.status != BookingStatus.PENDING:
        return
    booking.status = BookingStatus.CANCELLED
    booking.save(update_fields=["status"])


def _lock_booking(client_reference_id) -> Booking | None:
    if not client_reference_id:
        return None
    try:
        return Booking.objects.select_for_update().get(pk=int(client_reference_id))
    except (Booking.DoesNotExist, ValueError, TypeError):
        return None
