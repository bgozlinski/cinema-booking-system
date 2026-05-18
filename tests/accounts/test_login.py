"""Tests for the login view (FR-06).

Uses Django's stock ``auth_views.LoginView`` — no custom code. Behaviour
under test:

- active users with correct credentials → logged in, redirected
- inactive users with correct password → NOT logged in, generic error
  (security-first: no enumeration leak hint that the account exists
  but is pending activation)
- wrong password → generic error
- ``?next=`` redirect honored

Django's ``AuthenticationForm`` uses the field name ``username`` even when
``USERNAME_FIELD = "email"`` — the field name in POST data is still
``"username"`` regardless of the underlying USERNAME_FIELD setting.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_login_get_renders_form(client) -> None:
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_active_user_can_log_in(client) -> None:
    """Happy path — active user with the password that UserFactory hashes
    via UserManager.create_user logs in and is redirected to /."""
    UserFactory(email="alice@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login"),
        data={"username": "alice@example.com", "password": "test1234"},
    )

    assert response.status_code == 302
    assert response.url == "/"
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_inactive_user_cannot_log_in(client) -> None:
    """Inactive user with the correct password must NOT be logged in.
    ``ModelBackend.user_can_authenticate()`` returns False for is_active=False
    and ``AuthenticationForm`` shows the generic "invalid credentials"
    error — no leak that the account exists but is awaiting activation."""
    UserFactory(inactive=True, email="dormant@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login"),
        data={"username": "dormant@example.com", "password": "test1234"},
    )

    assert response.status_code == 200, (
        "Failed login must re-render the form (status 200), not redirect."
    )
    assert "_auth_user_id" not in client.session, (
        "Inactive user must not get a session — even though the password "
        "was correct, ModelBackend rejects them at user_can_authenticate."
    )


@pytest.mark.django_db
def test_login_with_wrong_password_fails(client) -> None:
    """Wrong password → no session, form re-rendered."""
    UserFactory(email="alice@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login"),
        data={"username": "alice@example.com", "password": "wrong"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_with_nonexistent_user_fails(client) -> None:
    """User not registered at all → generic error, no session.
    Compared with the inactive case above: both produce the same
    response (no enumeration leak)."""
    response = client.post(
        reverse("accounts:login"),
        data={"username": "ghost@example.com", "password": "test1234"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_redirects_to_next_param(client) -> None:
    """?next=/path/ → redirect to that path instead of LOGIN_REDIRECT_URL.
    Django sanitizes this against open-redirect attacks, but we test the
    happy path where ``next`` is a same-origin path."""
    UserFactory(email="alice@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login") + "?next=/protected/",
        data={"username": "alice@example.com", "password": "test1234"},
    )

    assert response.status_code == 302
    assert response.url == "/protected/"
