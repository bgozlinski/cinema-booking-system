import uuid

import stripe
from django.conf import settings
from django.urls import reverse

from apps.booking.models import Booking

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
