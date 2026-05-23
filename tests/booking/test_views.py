"""Tests for BookingCreateView (US-20 / FR-07)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
import stripe
from django.urls import reverse
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.booking.services import NotEnoughSeatsError
from tests.accounts.factories import UserFactory
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _future_screening(capacity: int = 100):
    return ScreeningFactory(hall=HallFactory(capacity=capacity))


def _book_url(screening):
    return reverse("booking:create", kwargs={"pk": screening.pk})


class TestAuth:
    def test_get_requires_login(self, client):
        screening = _future_screening()
        resp = client.get(_book_url(screening))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert "next=" in resp.url

    def test_post_requires_login(self, client):
        screening = _future_screening()
        resp = client.post(_book_url(screening), {"seats_count": 2})
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert Booking.objects.count() == 0


class TestGet:
    def test_renders_form_and_summary(self, client):
        client.force_login(UserFactory())
        screening = _future_screening()
        resp = client.get(_book_url(screening))
        assert resp.status_code == 200
        assert "form" in resp.context
        assert resp.context["screening"] == screening
        assert "booking/booking_form.html" in [t.name for t in resp.templates]

    def test_404_for_missing_screening(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse("booking:create", kwargs={"pk": 999999}))
        assert resp.status_code == 404


class TestPost:
    @pytest.mark.stripe
    def test_valid_creates_booking_and_redirects_to_stripe(self, client, mock_checkout_session):
        user = UserFactory()
        client.force_login(user)
        screening = _future_screening(capacity=50)
        resp = client.post(_book_url(screening), {"seats_count": 3})
        assert resp.status_code == 302
        assert resp.url == "https://checkout.stripe.test/c/cs_test_123"
        booking = Booking.objects.get(user=user, screening=screening)
        assert booking.status == BookingStatus.PENDING
        assert booking.seats_count == 3
        assert booking.stripe_session_id == "cs_test_123"

    @pytest.mark.stripe
    def test_stripe_failure_redirects_to_detail(self, client, mock_checkout_session):
        mock_checkout_session.side_effect = stripe.APIConnectionError("boom")
        user = UserFactory()
        client.force_login(user)
        screening = _future_screening(capacity=50)
        resp = client.post(_book_url(screening), {"seats_count": 3})
        booking = Booking.objects.get(user=user, screening=screening)
        assert resp.status_code == 302
        assert resp.url == reverse("booking:detail", kwargs={"pk": booking.pk})
        assert booking.status == BookingStatus.PENDING

    def test_invalid_form_rerenders_no_booking(self, client):
        client.force_login(UserFactory())
        screening = _future_screening()
        resp = client.post(_book_url(screening), {"seats_count": 0})
        assert resp.status_code == 200
        assert "seats_count" in resp.context["form"].errors
        assert Booking.objects.count() == 0

    def test_service_error_rerenders_with_nonfield_error(self, client):
        client.force_login(UserFactory())
        screening = _future_screening(capacity=50)
        with patch(
            "apps.booking.views.create_booking",
            side_effect=NotEnoughSeatsError(available=2),
        ):
            resp = client.post(_book_url(screening), {"seats_count": 3})
        assert resp.status_code == 200
        assert resp.context["form"].non_field_errors()
        assert Booking.objects.count() == 0

    def test_past_screening_rerenders_with_error(self, client):
        client.force_login(UserFactory())
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        resp = client.post(_book_url(screening), {"seats_count": 1})
        assert resp.status_code == 200
        assert resp.context["form"].non_field_errors()
        assert Booking.objects.count() == 0
