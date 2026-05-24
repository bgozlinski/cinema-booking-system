import pytest

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory

pytestmark = pytest.mark.django_db

BOOKINGS_URL = "/api/v1/bookings/"


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
