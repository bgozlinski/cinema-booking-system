"""Unit tests for BookingForm (US-19 / FR-07)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.booking.forms import BookingForm
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _future_screening(capacity: int = 100):
    """Future screening (start +7d via factory default) with given hall capacity."""
    return ScreeningFactory(hall=HallFactory(capacity=capacity))


class TestBookingFormValid:
    def test_valid_seats_within_availability(self):
        screening = _future_screening(capacity=100)
        form = BookingForm(data={"seats_count": 3}, screening=screening)
        assert form.is_valid()
        assert form.cleaned_data["seats_count"] == 3

    def test_one_seat_boundary_valid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": 1}, screening=screening)
        assert form.is_valid()

    def test_ten_seats_boundary_valid(self):
        screening = _future_screening(capacity=100)
        form = BookingForm(data={"seats_count": 10}, screening=screening)
        assert form.is_valid()

    def test_seats_equal_to_available_valid(self):
        screening = _future_screening(capacity=5)
        form = BookingForm(data={"seats_count": 5}, screening=screening)
        assert form.is_valid()


class TestBookingFormFieldRange:
    def test_zero_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": 0}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_eleven_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": 11}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_missing_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_non_integer_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": "abc"}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors


class TestBookingFormAvailability:
    def test_seats_exceed_capacity_invalid(self):
        # field max_value is 10, so 6 passes field validation; availability fails
        screening = _future_screening(capacity=5)
        form = BookingForm(data={"seats_count": 6}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_error_message_includes_available_count(self):
        screening = _future_screening(capacity=4)
        form = BookingForm(data={"seats_count": 5}, screening=screening)
        assert not form.is_valid()
        assert "4" in str(form.errors["seats_count"])

    def test_confirmed_bookings_reduce_availability(self):
        screening = _future_screening(capacity=10)
        ConfirmedBookingFactory(screening=screening, seats_count=7)
        # available now 3; requesting 4 fails
        form = BookingForm(data={"seats_count": 4}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_active_pending_reduces_availability(self):
        screening = _future_screening(capacity=10)
        BookingFactory(screening=screening, seats_count=8)  # PENDING, expires +15m
        # available now 2; requesting 3 fails
        form = BookingForm(data={"seats_count": 3}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_expired_pending_does_not_reduce_availability(self):
        screening = _future_screening(capacity=10)
        BookingFactory(
            screening=screening,
            seats_count=8,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        # expired PENDING not counted → 10 available; request 9 ok
        form = BookingForm(data={"seats_count": 9}, screening=screening)
        assert form.is_valid()

    def test_sold_out_screening_invalid(self):
        screening = _future_screening(capacity=5)
        ConfirmedBookingFactory(screening=screening, seats_count=5)
        form = BookingForm(data={"seats_count": 1}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors


class TestBookingFormPastScreening:
    def test_past_screening_invalid(self):
        screening = ScreeningFactory(
            hall=HallFactory(capacity=100),
            start_time=timezone.now() - timedelta(hours=1),
        )
        form = BookingForm(data={"seats_count": 2}, screening=screening)
        assert not form.is_valid()

    def test_past_screening_error_is_non_field(self):
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        form = BookingForm(data={"seats_count": 2}, screening=screening)
        assert not form.is_valid()
        assert form.non_field_errors()

    def test_screening_starting_now_invalid(self):
        # is_in_past() is start_time <= now(); now() at validation is later → past
        screening = ScreeningFactory(start_time=timezone.now())
        form = BookingForm(data={"seats_count": 2}, screening=screening)
        assert not form.is_valid()
        assert form.non_field_errors()
