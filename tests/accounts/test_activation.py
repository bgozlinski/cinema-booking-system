"""Tests for ``ActivateView`` (FR-06).

Covers the full decision matrix:

- valid token (happy path) — activates user + flash success + redirect login
- invalid token — redirect to activation_invalid, user stays inactive
- malformed uidb64 — redirect to activation_invalid
- uidb64 for nonexistent user — redirect to activation_invalid
- expired token (>PASSWORD_RESET_TIMEOUT) — redirect to activation_invalid
- already-active user (double click) — flash "already active" + redirect login
- idempotency on second click — does not 500

``freezegun`` is used to simulate token expiry without sleeping for 3 days
or monkey-patching Django's clock primitives directly.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from freezegun import freeze_time

from tests.accounts.factories import UserFactory

User = get_user_model()


def _activation_url_for(user) -> str:
    """Build the canonical activation URL for ``user`` using the same
    encoder + token generator as the production ``send_activation_email``
    helper. Sharing this helper across tests ensures we exercise the
    exact path the view will see."""
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return reverse("accounts:activate", kwargs={"uidb64": uidb64, "token": token})


@pytest.mark.django_db
def test_activate_with_valid_token_activates_user(client) -> None:
    """Happy path — fresh inactive user clicks the link → is_active flips
    to True and they're sent to the login page."""
    user = UserFactory(inactive=True)
    url = _activation_url_for(user)

    response = client.get(url)

    user.refresh_from_db()
    assert user.is_active is True
    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


@pytest.mark.django_db
def test_activate_with_valid_token_shows_success_flash(client) -> None:
    """The activation success message must reach the user via Django's
    messages framework — verified by following the redirect and reading
    response.context["messages"]."""
    user = UserFactory(inactive=True)
    url = _activation_url_for(user)

    response = client.get(url, follow=True)

    messages_list = [str(m) for m in response.context["messages"]]
    assert any(
        "aktyw" in m.lower() for m in messages_list
    ), f"Expected a flash mentioning activation (case-insensitive 'aktyw'). Got: {messages_list}"


@pytest.mark.django_db
def test_activate_with_invalid_token_redirects_to_invalid_page(client) -> None:
    """Token that doesn't validate (e.g. tampered) → activation_invalid,
    user stays inactive."""
    user = UserFactory(inactive=True)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    url = reverse(
        "accounts:activate",
        kwargs={"uidb64": uidb64, "token": "totally-fake-token"},
    )

    response = client.get(url)

    user.refresh_from_db()
    assert user.is_active is False
    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


def test_activate_with_malformed_uidb64_redirects_to_invalid_page(client) -> None:
    """Garbage in uidb64 (not valid base64) must not 500 — view must
    catch the decode error and redirect gracefully."""
    url = reverse(
        "accounts:activate",
        kwargs={"uidb64": "!!!not-base64!!!", "token": "anything"},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


@pytest.mark.django_db
def test_activate_for_nonexistent_user_redirects_to_invalid_page(client) -> None:
    """Valid uidb64 syntax but the encoded pk doesn't match any user
    (deleted account, attack with crafted link) → activation_invalid."""
    uidb64 = urlsafe_base64_encode(force_bytes(99999))
    url = reverse(
        "accounts:activate",
        kwargs={"uidb64": uidb64, "token": "anything"},
    )

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


@pytest.mark.django_db
def test_activate_with_expired_token_redirects_to_invalid_page(client) -> None:
    """Tokens are time-stamped via ``default_token_generator`` and expire
    after PASSWORD_RESET_TIMEOUT (Django default 3 days). We jump 4 days
    forward to confirm the expiry check is wired correctly — without
    freezegun this test would need to sleep 3 real days."""
    with freeze_time("2026-05-18 12:00:00"):
        user = UserFactory(inactive=True)
        url = _activation_url_for(user)

    with freeze_time("2026-05-22 12:00:00"):
        response = client.get(url)

    user.refresh_from_db()
    assert user.is_active is False, "expired token must not activate the user"
    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


@pytest.mark.django_db
def test_activate_already_active_user_redirects_to_login_with_info(client) -> None:
    """If a user clicks the link a second time (or admin pre-activated
    them) we should NOT show 'invalid token' — that would be a confusing
    UX. Show 'already active' info flash and send them to login."""
    user = UserFactory()  # is_active=True by default
    url = _activation_url_for(user)

    response = client.get(url, follow=True)

    user.refresh_from_db()
    assert user.is_active is True
    assert response.redirect_chain[-1][0] == reverse("accounts:login")
    messages_list = [str(m) for m in response.context["messages"]]
    assert any(
        "już aktyw" in m.lower() or "already" in m.lower() for m in messages_list
    ), f"Expected an info flash about account already being active. Got: {messages_list}"


@pytest.mark.django_db
def test_activate_is_idempotent_on_second_click(client) -> None:
    """End-to-end idempotency: first click activates, second click hits
    the 'already active' branch and still ends at the login page. The
    test guards against a regression where a second click crashes with
    InvalidToken or 500s."""
    user = UserFactory(inactive=True)
    url = _activation_url_for(user)

    client.get(url)  # first click — activates
    response = client.get(url)  # second click — must not crash

    user.refresh_from_db()
    assert user.is_active is True
    assert response.status_code == 302
    assert response.url == reverse("accounts:login")
