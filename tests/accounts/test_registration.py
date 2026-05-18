"""Tests for ``RegisterView`` (FR-06).

End-to-end happy-path + negative scenarios for the registration flow.
Form-level validation is covered by ``test_forms.py``; this file focuses
on the view contract:

- creates an inactive user
- sends an activation email
- does NOT auto-log-in
- redirects to ``activation_sent`` on success
- re-renders form on validation failure (no user created, no email sent)
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from tests.accounts.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
def test_register_get_renders_form(client) -> None:
    """GIVEN anonymous user
    WHEN GET /accounts/register/
    THEN 200 + form in context (so the template can render fields)."""
    response = client.get(reverse("accounts:register"))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_register_post_valid_creates_inactive_user(client) -> None:
    """GIVEN valid POST data
    WHEN /accounts/register/ receives it
    THEN a user is persisted with is_active=False (NOT logged in until
    they click the activation link)."""
    client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    user = User.objects.get(email="newbie@example.com")
    assert user.is_active is False, (
        "Newly registered user must be inactive until they click the "
        "activation link in their email."
    )


@pytest.mark.django_db
def test_register_post_valid_redirects_to_activation_sent(client) -> None:
    """Success path → 302 to ``activation_sent`` (the "check your inbox" page)."""
    response = client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_sent")


@pytest.mark.django_db
def test_register_post_valid_sends_activation_email(client) -> None:
    """GIVEN valid registration POST
    WHEN it succeeds
    THEN exactly one email lands in the outbox, addressed to the user
    and containing an activation link."""
    client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == ["newbie@example.com"]
    assert "/accounts/activate/" in sent.body


@pytest.mark.django_db
def test_register_post_valid_does_not_log_user_in(client) -> None:
    """The activation flow is the gate — successful POST must NOT create
    an authenticated session. ``_auth_user_id`` is Django's session key
    for the logged-in user id."""
    client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_register_post_rejects_duplicate_email(client) -> None:
    """GIVEN an existing user with the email
    WHEN someone tries to register with the same email
    THEN form re-renders with error (status 200), no second user is
    created, and NO email is sent (we shouldn't spam the original
    owner with activation links triggered by attackers)."""
    UserFactory(email="existing@example.com")

    response = client.post(
        reverse("accounts:register"),
        data={
            "email": "existing@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    assert response.status_code == 200, "re-renders form on validation error"
    assert "email" in response.context["form"].errors
    assert User.objects.filter(email="existing@example.com").count() == 1
    assert len(mail.outbox) == 0, (
        "No email should be sent on validation failure — otherwise an "
        "attacker could spam any registered user."
    )


@pytest.mark.django_db
def test_register_post_rejects_mismatched_passwords(client) -> None:
    """Mismatched passwords → no user, no email, form re-renders."""
    response = client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "different-pw",
        },
    )

    assert response.status_code == 200
    assert "password2" in response.context["form"].errors
    assert not User.objects.filter(email="newbie@example.com").exists()
    assert len(mail.outbox) == 0
