import pytest

from apps.booking.models import BookingStatus
from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory

pytestmark = pytest.mark.django_db

ADMIN_BOOKINGS_URL = "/api/v1/admin/bookings/"


class TestAdminBookings:
    def test_non_staff_forbidden(self, auth_client):
        assert auth_client(UserFactory()).get(ADMIN_BOOKINGS_URL).status_code == 403

    def test_staff_lists_all(self, auth_client):
        BookingFactory()
        BookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).get(ADMIN_BOOKINGS_URL)
        assert resp.status_code == 200
        assert resp.data["count"] == 2

    def test_staff_patches_status(self, auth_client):
        booking = BookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).patch(
            f"{ADMIN_BOOKINGS_URL}{booking.id}/", {"status": "CANCELLED"}, format="json"
        )
        assert resp.status_code == 200
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_create_not_allowed(self, auth_client):
        resp = auth_client(UserFactory(is_staff=True)).post(ADMIN_BOOKINGS_URL, {}, format="json")
        assert resp.status_code == 405

    def test_delete_not_allowed(self, auth_client):
        booking = BookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).delete(f"{ADMIN_BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 405

    @pytest.mark.stripe
    def test_refund_action_confirmed(self, auth_client, mock_refund):
        booking = ConfirmedBookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).post(
            f"{ADMIN_BOOKINGS_URL}{booking.id}/refund/"
        )
        assert resp.status_code == 200
        assert resp.data["status"] == "CANCELLED"
        booking.refresh_from_db()
        assert booking.refund_id == "re_test_123"

    def test_refund_pending_conflict(self, auth_client):
        booking = BookingFactory()  # PENDING — nothing to refund
        resp = auth_client(UserFactory(is_staff=True)).post(
            f"{ADMIN_BOOKINGS_URL}{booking.id}/refund/"
        )
        assert resp.status_code == 409
