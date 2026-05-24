"""Tests for the stripe_webhook view (US-25 / FR-22)."""

import json

import pytest
import stripe
from django.test import Client
from django.urls import reverse

from apps.booking.models import BookingStatus
from tests.booking.factories import BookingFactory

pytestmark = [pytest.mark.django_db, pytest.mark.stripe]


def _payload(booking_id, event_type="checkout.session.completed", event_id="evt_view_1"):
    return json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "data": {"object": {"client_reference_id": str(booking_id), "payment_intent": "pi_1"}},
        }
    )


def _post(client, payload):
    return client.post(
        reverse("payments:stripe_webhook"),
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=fake",
    )


class TestStripeWebhookView:
    def test_valid_signature_returns_200_and_confirms(self, client, mocker):
        booking = BookingFactory()
        mocker.patch("apps.payments.views.stripe.Webhook.construct_event")
        resp = _post(client, _payload(booking.id))
        assert resp.status_code == 200
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_bad_signature_returns_400(self, client, mocker):
        mocker.patch(
            "apps.payments.views.stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError("bad", "sig"),
        )
        resp = _post(client, _payload(1))
        assert resp.status_code == 400

    def test_malformed_payload_returns_400(self, client, mocker):
        mocker.patch(
            "apps.payments.views.stripe.Webhook.construct_event",
            side_effect=ValueError("bad json"),
        )
        resp = _post(client, "not-json")
        assert resp.status_code == 400

    def test_get_not_allowed(self, client):
        resp = client.get(reverse("payments:stripe_webhook"))
        assert resp.status_code == 405

    def test_csrf_exempt_allows_post_without_token(self, mocker):
        mocker.patch("apps.payments.views.stripe.Webhook.construct_event")
        booking = BookingFactory()
        csrf_client = Client(enforce_csrf_checks=True)
        resp = _post(csrf_client, _payload(booking.id))
        assert resp.status_code != 403
