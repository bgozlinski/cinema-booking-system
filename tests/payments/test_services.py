"""Tests for the real Stripe checkout session creation (US-24 / FR-21)."""

import pytest
import stripe
from django.conf import settings
from django.urls import reverse

from apps.payments.services import create_checkout_session
from tests.booking.factories import BookingFactory

pytestmark = [pytest.mark.django_db, pytest.mark.stripe]


def test_creates_session_with_expected_params(mock_checkout_session):
    booking = BookingFactory(seats_count=2)
    create_checkout_session(booking)

    kwargs = mock_checkout_session.call_args.kwargs
    assert kwargs["mode"] == "payment"
    assert kwargs["client_reference_id"] == str(booking.id)
    item = kwargs["line_items"][0]
    assert item["price_data"]["currency"] == "pln"
    assert item["price_data"]["unit_amount"] == int(booking.total_price * 100)
    detail = reverse("booking:detail", kwargs={"pk": booking.id})
    assert kwargs["success_url"] == f"{settings.BASE_URL}{detail}?stripe=success"
    assert kwargs["cancel_url"] == f"{settings.BASE_URL}{detail}?stripe=cancelled"
    assert "idempotency_key" in kwargs


def test_returns_url_and_session_id(mock_checkout_session):
    booking = BookingFactory()
    url, session_id = create_checkout_session(booking)
    assert url == "https://checkout.stripe.test/c/cs_test_123"
    assert session_id == "cs_test_123"


def test_propagates_stripe_error(mock_checkout_session):
    mock_checkout_session.side_effect = stripe.APIConnectionError("network down")
    with pytest.raises(stripe.StripeError):
        create_checkout_session(BookingFactory())
