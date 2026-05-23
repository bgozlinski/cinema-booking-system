"""Tests for BookingCheckoutView retry endpoint (US-24 / FR-21)."""

import pytest
import stripe
from django.urls import reverse

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory

pytestmark = [pytest.mark.django_db, pytest.mark.stripe]


def _checkout_url(booking):
    return reverse("booking:checkout", kwargs={"pk": booking.pk})


class TestBookingCheckoutView:
    def test_anonymous_redirected_to_login(self, client):
        booking = BookingFactory()
        resp = client.post(_checkout_url(booking))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url

    def test_get_not_allowed(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_checkout_url(booking))
        assert resp.status_code == 405

    def test_owner_pending_redirects_to_stripe(self, client, mock_checkout_session):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.post(_checkout_url(booking))
        assert resp.status_code == 302
        assert resp.url == "https://checkout.stripe.test/c/cs_test_123"
        booking.refresh_from_db()
        assert booking.stripe_session_id == "cs_test_123"

    def test_non_pending_flashes_error(self, client, mock_checkout_session):
        booking = ConfirmedBookingFactory()
        client.force_login(booking.user)
        resp = client.post(_checkout_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:detail", kwargs={"pk": booking.pk})
        assert any("nie można" in str(m).lower() for m in resp.context["messages"])
        assert mock_checkout_session.call_count == 0

    def test_stripe_failure_flashes_error(self, client, mock_checkout_session):
        mock_checkout_session.side_effect = stripe.APIConnectionError("boom")
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.post(_checkout_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:detail", kwargs={"pk": booking.pk})
        assert any("niedostępna" in str(m).lower() for m in resp.context["messages"])

    def test_non_owner_404(self, client, mock_checkout_session):
        booking = BookingFactory()
        client.force_login(UserFactory())
        resp = client.post(_checkout_url(booking))
        assert resp.status_code == 404
