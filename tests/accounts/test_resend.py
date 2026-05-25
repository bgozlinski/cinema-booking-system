"""Tests for ``ResendActivationView`` (FR-06).

The critical contract here is **no enumeration leak**: the resend
endpoint must NOT reveal whether an email is registered. All three
scenarios (inactive user / active user / nonexistent email) must render
the same ``resend_done.html`` template — bodies must be byte-identical.
Real email is sent only in the inactive-user scenario.
"""

from __future__ import annotations

import re

import pytest
from django.core import mail
from django.urls import reverse

from tests.accounts.factories import UserFactory

# The global navbar language switcher (US-37) is a POST form, so every page now
# carries a per-request-random CSRF token. It is independent of the submitted
# email, so we normalize it out before asserting byte-identical responses below.
_CSRF_TOKEN_RE = re.compile(rb'name="csrfmiddlewaretoken" value="[^"]*"')


@pytest.mark.django_db
def test_resend_get_renders_form(client) -> None:
    """GIVEN anonymous user
    WHEN GET /accounts/activate/resend/
    THEN 200 + form in context."""
    response = client.get(reverse("accounts:activation_resend"))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_resend_for_inactive_user_sends_email(client) -> None:
    """Inactive user — the one case where we actually send an email.
    Verifies recipient + activation link in body."""
    UserFactory(inactive=True, email="dormant@example.com")

    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "dormant@example.com"},
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["dormant@example.com"]
    assert "/accounts/activate/" in mail.outbox[0].body


@pytest.mark.django_db
def test_resend_for_active_user_sends_no_email(client) -> None:
    """Already-activated user — the view must NOT send a fresh email.
    Otherwise an attacker could weaponize the endpoint as spam delivery
    against any registered user."""
    UserFactory(email="active@example.com")  # is_active=True by default

    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "active@example.com"},
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_resend_for_nonexistent_user_sends_no_email(client) -> None:
    """Email not registered at all — no email, same response as the other
    two scenarios."""
    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "nobody@example.com"},
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_resend_renders_the_same_response_in_all_scenarios(client) -> None:
    """The no-enumeration-leak invariant: response bodies must be identical
    across (inactive / active / nonexistent). If a future change adds
    e.g. "we sent you an email" copy that only appears in the inactive
    case, attackers can probe which emails are registered.

    The only per-request-variable content is the CSRF token in the global
    navbar language switcher (US-37) — random regardless of the submitted
    email, so it carries no enumeration signal and is normalized out before
    comparing. If anything *email-dependent* ever diverges, this test starts
    failing and forces a re-think."""
    UserFactory(inactive=True, email="dormant@example.com")
    UserFactory(email="active@example.com")

    bodies = []
    for email in ["dormant@example.com", "active@example.com", "nobody@example.com"]:
        response = client.post(
            reverse("accounts:activation_resend"),
            data={"email": email},
        )
        normalized = _CSRF_TOKEN_RE.sub(
            b'name="csrfmiddlewaretoken" value="NORMALIZED"', response.content
        )
        bodies.append(normalized)

    assert bodies[0] == bodies[1] == bodies[2], (
        "All three resend scenarios must render identical responses "
        "(no enumeration leak; CSRF token normalized out). If this fails, check "
        "whether resend_done.html started including email-dependent content."
    )


@pytest.mark.django_db
def test_resend_with_invalid_email_re_renders_form(client) -> None:
    """Syntactically invalid email — different from the "valid syntax but
    not registered" case. We re-render the form with field error, not the
    success page; the form is the place to fail a syntax-level mistake."""
    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "not-an-email"},
    )

    assert response.status_code == 200
    assert "form" in response.context
    assert "email" in response.context["form"].errors
    assert len(mail.outbox) == 0
