"""Tests for Screening method behavior (US-18 / FR-3.7).

Replaces the stub-based assertions previously in tests/cinema/test_models.py
(lines 280-329). After US-18, booked_seats_count aggregates CONFIRMED +
active-PENDING bookings rather than returning a stub 0.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.booking.models import BookingStatus
from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


class TestBookedSeatsCount:
    def test_zero_for_no_bookings(self):
        screening = ScreeningFactory()
        assert screening.booked_seats_count() == 0

    def test_sums_confirmed_bookings(self):
        screening = ScreeningFactory()
        ConfirmedBookingFactory(screening=screening, seats_count=3)
        ConfirmedBookingFactory(screening=screening, seats_count=2)
        assert screening.booked_seats_count() == 5

    def test_includes_active_pending(self):
        screening = ScreeningFactory()
        # PENDING with expires_at > now() counts as reserved (anti-overbook semantics)
        BookingFactory(
            screening=screening,
            seats_count=4,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        assert screening.booked_seats_count() == 4

    def test_excludes_expired_pending(self):
        screening = ScreeningFactory()
        # PENDING with expires_at <= now() is effectively cancelled
        BookingFactory(
            screening=screening,
            seats_count=4,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        assert screening.booked_seats_count() == 0

    def test_excludes_cancelled(self):
        screening = ScreeningFactory()
        CancelledBookingFactory(screening=screening, seats_count=4)
        assert screening.booked_seats_count() == 0

    def test_excludes_pending_with_null_expires_at(self):
        """Defensive — view layer should always set expires_at, but if it's None
        (broken state) we exclude it from the count rather than treating it as
        reserved indefinitely."""
        screening = ScreeningFactory()
        BookingFactory(
            screening=screening,
            seats_count=4,
            status=BookingStatus.PENDING,
            expires_at=None,
        )
        assert screening.booked_seats_count() == 0

    def test_combines_confirmed_and_active_pending(self):
        screening = ScreeningFactory()
        ConfirmedBookingFactory(screening=screening, seats_count=3)
        BookingFactory(
            screening=screening,
            seats_count=2,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        # CONFIRMED 3 + active-PENDING 2 = 5
        assert screening.booked_seats_count() == 5

    def test_uses_annotated_value_when_present(self):
        """View querysets annotate _annotated_booked_count to avoid N+1 from
        template loops. Model method should honor that annotation and skip the
        query — even if real bookings exist on the screening."""
        screening = ScreeningFactory()
        ConfirmedBookingFactory(screening=screening, seats_count=3)
        # Simulate queryset annotation (in production set via .annotate(...)).
        screening._annotated_booked_count = 42
        # Should return the annotated value, NOT the real aggregate (3).
        assert screening.booked_seats_count() == 42


class TestAvailableSeatsCount:
    def test_equals_capacity_minus_booked(self):
        # FR §7.2 unit example: hall 100, booking 30 → 70 available
        hall = HallFactory(capacity=100)
        screening = ScreeningFactory(hall=hall)
        ConfirmedBookingFactory(screening=screening, seats_count=30)
        assert screening.available_seats_count() == 70

    def test_zero_when_sold_out(self):
        hall = HallFactory(capacity=10)
        screening = ScreeningFactory(hall=hall)
        ConfirmedBookingFactory(screening=screening, seats_count=10)
        assert screening.available_seats_count() == 0


class TestIsAvailable:
    def test_true_for_future_with_seats(self):
        future = timezone.now() + timedelta(days=1)
        screening = ScreeningFactory(start_time=future)
        assert screening.is_available() is True

    def test_false_when_sold_out(self):
        future = timezone.now() + timedelta(days=1)
        hall = HallFactory(capacity=5)
        screening = ScreeningFactory(hall=hall, start_time=future)
        ConfirmedBookingFactory(screening=screening, seats_count=5)
        assert screening.is_available() is False

    def test_false_for_past_screening(self):
        past = timezone.now() - timedelta(days=1)
        screening = ScreeningFactory(start_time=past)
        assert screening.is_available() is False
