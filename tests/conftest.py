"""Shared pytest fixtures."""

import pytest


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
