"""Tests for apps.booking.Booking model."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.booking.models import Booking, BookingStatus
from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import ScreeningFactory

pytestmark = pytest.mark.django_db


class TestBookingCreation:
    def test_creation_with_required_fields(self):
        user = UserFactory()
        screening = ScreeningFactory()
        booking = Booking.objects.create(
            user=user,
            screening=screening,
            seats_count=2,
        )
        assert booking.pk is not None
        assert booking.user == user
        assert booking.screening == screening
        assert booking.seats_count == 2

    def test_status_default_is_pending(self):
        booking = Booking.objects.create(
            user=UserFactory(), screening=ScreeningFactory(), seats_count=1
        )
        assert booking.status == BookingStatus.PENDING

    def test_created_at_auto_set(self):
        booking = BookingFactory()
        assert booking.created_at is not None


class TestBookingProperties:
    def test_total_price_returns_seats_times_screening_price(self):
        screening = ScreeningFactory(price=Decimal("25.50"))
        booking = BookingFactory(screening=screening, seats_count=3)
        assert booking.total_price == Decimal("76.50")

    def test_str_includes_id_and_movie_title(self):
        booking = BookingFactory()
        assert f"Booking #{booking.pk}" in str(booking)
        assert booking.screening.movie.title in str(booking)


class TestBookingValidators:
    def test_seats_count_validator_rejects_zero(self):
        booking = BookingFactory(seats_count=0)
        with pytest.raises(ValidationError) as exc_info:
            booking.full_clean()
        # Assert seats_count is the specific cause (avoid false positive from
        # unrelated field validators tripping first).
        assert "seats_count" in exc_info.value.error_dict

    def test_seats_count_validator_rejects_eleven(self):
        booking = BookingFactory(seats_count=11)
        with pytest.raises(ValidationError) as exc_info:
            booking.full_clean()
        assert "seats_count" in exc_info.value.error_dict

    def test_seats_count_accepts_one(self):
        booking = BookingFactory(seats_count=1)
        booking.full_clean()  # should not raise

    def test_seats_count_accepts_ten(self):
        booking = BookingFactory(seats_count=10)
        booking.full_clean()  # should not raise


class TestBookingMeta:
    def test_default_ordering_newest_first(self):
        first = BookingFactory()
        second = BookingFactory()
        third = BookingFactory()
        bookings = list(Booking.objects.all())
        assert bookings == [third, second, first]

    def test_status_expires_index_exists(self):
        index_names = [idx.name for idx in Booking._meta.indexes]
        assert "booking_status_expires_idx" in index_names


class TestBookingCascade:
    def test_cascade_from_user(self):
        user = UserFactory()
        BookingFactory(user=user)
        BookingFactory(user=user)
        assert Booking.objects.filter(user=user).count() == 2
        user.delete()
        assert Booking.objects.filter(user__pk=user.pk).count() == 0

    def test_cascade_from_screening(self):
        screening = ScreeningFactory()
        BookingFactory(screening=screening)
        BookingFactory(screening=screening)
        assert Booking.objects.filter(screening=screening).count() == 2
        screening.delete()
        assert Booking.objects.filter(screening__pk=screening.pk).count() == 0


class TestBookingFactoryVariants:
    def test_confirmed_booking_factory_sets_status_and_stripe_ids(self):
        booking = ConfirmedBookingFactory()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.expires_at is None
        assert booking.stripe_session_id.startswith("cs_test_")
        assert booking.stripe_payment_intent_id.startswith("pi_test_")
