from datetime import timedelta

import pytest
import stripe
from django.utils import timezone

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db

BOOKINGS_URL = "/api/v1/bookings/"
FAKE_CHECKOUT_URL = "https://checkout.stripe.test/c/cs_test_123"


class TestBookingList:
    def test_owner_sees_only_own(self, auth_client):
        owner = UserFactory()
        BookingFactory(user=owner)
        BookingFactory()  # someone else's
        resp = auth_client(owner).get(BOOKINGS_URL)
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_staff_sees_all(self, auth_client):
        BookingFactory()
        BookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).get(BOOKINGS_URL)
        assert resp.data["count"] == 2

    def test_anon_unauthorized(self, api_client):
        assert api_client.get(BOOKINGS_URL).status_code == 401


class TestBookingRetrieve:
    def test_owner_can_retrieve(self, auth_client):
        owner = UserFactory()
        booking = BookingFactory(user=owner)
        resp = auth_client(owner).get(f"{BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 200
        assert resp.data["id"] == booking.id
        assert resp.data["screening"]["movie"]["title"] == booking.screening.movie.title
        assert "total_price" in resp.data

    def test_non_owner_gets_404(self, auth_client):
        booking = BookingFactory()
        resp = auth_client(UserFactory()).get(f"{BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 404

    def test_staff_can_retrieve(self, auth_client):
        booking = BookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).get(f"{BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 200


class TestBookingCreate:
    @pytest.mark.stripe
    def test_create_valid(self, auth_client, mock_checkout_session):
        screening = ScreeningFactory()
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 2}, format="json"
        )
        assert resp.status_code == 201
        assert resp.data["booking"]["status"] == "PENDING"
        assert resp.data["booking"]["seats_count"] == 2
        assert resp.data["checkout_url"] == FAKE_CHECKOUT_URL

    def test_seats_out_of_range(self, auth_client):
        screening = ScreeningFactory()
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 11}, format="json"
        )
        assert resp.status_code == 400
        assert "seats_count" in resp.data

    @pytest.mark.stripe
    def test_sold_out_conflict(self, auth_client, mock_checkout_session):
        hall = HallFactory(capacity=2)
        screening = ScreeningFactory(hall=hall)
        ConfirmedBookingFactory(screening=screening, seats_count=2)  # fills the hall
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 1}, format="json"
        )
        assert resp.status_code == 409

    @pytest.mark.stripe
    def test_past_screening_400(self, auth_client, mock_checkout_session):
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 1}, format="json"
        )
        assert resp.status_code == 400

    @pytest.mark.stripe
    def test_stripe_down_returns_201_null_checkout(self, auth_client, mock_checkout_session):
        mock_checkout_session.side_effect = stripe.APIConnectionError("boom")
        screening = ScreeningFactory()
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 1}, format="json"
        )
        assert resp.status_code == 201
        assert resp.data["checkout_url"] is None
        assert "detail" in resp.data
