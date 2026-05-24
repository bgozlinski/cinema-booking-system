"""Tests for BookingCancelView (US-23 / FR-10)."""

import pytest
from django.urls import reverse

from apps.booking.models import BookingStatus
from tests.accounts.factories import UserFactory
from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)

pytestmark = pytest.mark.django_db


def _cancel_url(booking):
    return reverse("booking:cancel", kwargs={"pk": booking.pk})


class TestBookingCancelView:
    def test_anonymous_redirected_to_login(self, client):
        booking = BookingFactory()
        resp = client.post(_cancel_url(booking))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url

    def test_get_not_allowed(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_cancel_url(booking))
        assert resp.status_code == 405

    def test_owner_cancels_pending(self, client):
        booking = BookingFactory()  # PENDING, future +7d
        client.force_login(booking.user)
        resp = client.post(_cancel_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:my_bookings")
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED
        assert any("anulowana" in str(m).lower() for m in resp.context["messages"])

    def test_non_owner_404(self, client):
        booking = BookingFactory()
        client.force_login(UserFactory())  # different user
        resp = client.post(_cancel_url(booking))
        assert resp.status_code == 404
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING

    def test_not_cancellable_flashes_error(self, client):
        booking = CancelledBookingFactory()  # already CANCELLED → not cancellable
        client.force_login(booking.user)
        resp = client.post(_cancel_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:my_bookings")
        assert any("nie można" in str(m).lower() for m in resp.context["messages"])

    @pytest.mark.stripe
    def test_owner_cancels_confirmed_with_refund(self, client, mock_refund):
        booking = ConfirmedBookingFactory()
        client.force_login(booking.user)
        resp = client.post(_cancel_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:my_bookings")
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED
        assert booking.refund_id == "re_test_123"
        assert any("anulowana" in str(m).lower() for m in resp.context["messages"])

    def test_404_for_missing_booking(self, client):
        client.force_login(UserFactory())
        resp = client.post(reverse("booking:cancel", kwargs={"pk": 999999}))
        assert resp.status_code == 404
