"""Tests for booking.services.create_booking (US-20 / FR-07)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.booking.services import (
    NotEnoughSeatsError,
    ScreeningInPastError,
    create_booking,
)
from tests.accounts.factories import UserFactory
from tests.booking.factories import ConfirmedBookingFactory
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _future_screening(capacity: int = 100):
    return ScreeningFactory(hall=HallFactory(capacity=capacity))


class TestCreateBookingSuccess:
    def test_creates_pending_with_expiry(self):
        user = UserFactory()
        screening = _future_screening(capacity=50)
        before = timezone.now()
        booking, _url = create_booking(user=user, screening=screening, seats_count=3)
        assert booking.status == BookingStatus.PENDING
        assert booking.seats_count == 3
        assert booking.user == user
        assert booking.screening == screening
        assert booking.expires_at is not None
        delta = booking.expires_at - before
        assert timedelta(minutes=14) <= delta <= timedelta(minutes=16)

    def test_returns_movie_detail_checkout_url(self):
        screening = _future_screening()
        _booking, url = create_booking(user=UserFactory(), screening=screening, seats_count=1)
        assert url == reverse("cinema:movie_detail", kwargs={"pk": screening.movie_id})

    def test_does_not_set_session_id_with_stub(self):
        screening = _future_screening()
        booking, _url = create_booking(user=UserFactory(), screening=screening, seats_count=1)
        assert booking.stripe_session_id == ""


class TestCreateBookingErrors:
    def test_raises_when_seats_exceed_available(self):
        screening = _future_screening(capacity=10)
        ConfirmedBookingFactory(screening=screening, seats_count=8)  # available 2
        with pytest.raises(NotEnoughSeatsError) as exc:
            create_booking(user=UserFactory(), screening=screening, seats_count=3)
        assert exc.value.available == 2
        assert Booking.objects.filter(status=BookingStatus.PENDING).count() == 0

    def test_raises_for_past_screening(self):
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        with pytest.raises(ScreeningInPastError):
            create_booking(user=UserFactory(), screening=screening, seats_count=1)

    def test_sequential_overbooking_impossible(self):
        screening = _future_screening(capacity=5)
        create_booking(user=UserFactory(), screening=screening, seats_count=4)
        with pytest.raises(NotEnoughSeatsError):
            create_booking(user=UserFactory(), screening=screening, seats_count=2)
        booked = sum(
            b.seats_count
            for b in Booking.objects.filter(screening=screening, status=BookingStatus.PENDING)
        )
        assert booked <= screening.hall.capacity
