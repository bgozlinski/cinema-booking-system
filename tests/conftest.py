"""Shared pytest fixtures."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture
def mock_checkout_session(mocker):
    """Patch stripe.checkout.Session.create with a fake session.

    Returns the patched mock. Default returns a fake session (.url + .id); set
    ``.side_effect = stripe.APIConnectionError("boom")`` to simulate failure.
    """
    fake = mocker.MagicMock(url="https://checkout.stripe.test/c/cs_test_123", id="cs_test_123")
    return mocker.patch("apps.payments.services.stripe.checkout.Session.create", return_value=fake)


@pytest.fixture
def mock_refund(mocker):
    """Patch stripe.Refund.create with a fake refund (.id). Set .side_effect to fail."""
    fake = mocker.MagicMock(id="re_test_123")
    return mocker.patch("apps.payments.services.stripe.Refund.create", return_value=fake)


@pytest.fixture
def api_client():
    """Anonymous DRF API client."""
    return APIClient()


@pytest.fixture
def auth_client():
    """Factory: ``auth_client(user)`` -> APIClient carrying a Bearer JWT for that user.

    The canonical authed-client pattern reused by all US-30+ API tests.
    """

    def _make(user):
        client = APIClient()
        access = RefreshToken.for_user(user).access_token
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return client

    return _make


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Reset DRF throttle counters between tests (shared per-process LocMemCache)."""
    cache.clear()
    yield
    cache.clear()
