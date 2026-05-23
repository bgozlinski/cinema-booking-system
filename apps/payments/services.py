from django.urls import reverse

from apps.booking.models import Booking


def create_checkout_session(booking: Booking) -> tuple[str, str]:
    """Return (checkout_url, session_id) for a PENDING booking.

    STUB (US-20): returns the screening's movie detail URL and an empty session
    id — no Stripe call yet. US-24 replaces the body with
    stripe.checkout.Session.create(...) per FR-21 and returns (session.url, session.id).
    """
    checkout_url = reverse("cinema:movie_detail", kwargs={"pk": booking.screening.movie_id})
    return checkout_url, ""
