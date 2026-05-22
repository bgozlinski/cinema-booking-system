"""factory_boy factories for the booking app."""

from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.booking.models import BookingStatus
from tests.accounts.factories import UserFactory
from tests.cinema.factories import ScreeningFactory


class BookingFactory(DjangoModelFactory):
    """Default factory creates a PENDING booking with expires_at = now + 15min."""

    class Meta:
        model = "booking.Booking"  # lazy string ref (per US-10 pitfall)

    user = factory.SubFactory(UserFactory)
    screening = factory.SubFactory(ScreeningFactory)
    seats_count = factory.Faker("pyint", min_value=1, max_value=10)
    status = BookingStatus.PENDING
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))


class ConfirmedBookingFactory(BookingFactory):
    """PENDING → CONFIRMED transition simulated. Stripe IDs populated."""

    status = BookingStatus.CONFIRMED
    expires_at = None  # CONFIRMED clears expires_at (no longer relevant after payment)
    stripe_session_id = factory.Sequence(lambda n: f"cs_test_{n}")
    stripe_payment_intent_id = factory.Sequence(lambda n: f"pi_test_{n}")


class CancelledBookingFactory(BookingFactory):
    """CANCELLED — used for testing list/history views."""

    status = BookingStatus.CANCELLED
    expires_at = None
