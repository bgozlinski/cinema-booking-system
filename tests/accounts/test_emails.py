"""Tests for the activation email helper (FR-06).

``send_activation_email`` is the single mockable seam for activation emails:
views call it; tests inspect ``mail.outbox`` after it runs. Covering it
directly here means the view tests can stay focused on view behavior
without re-asserting email composition details.

pytest-django auto-overrides ``EMAIL_BACKEND`` to ``locmem`` in tests, so
``mail.outbox`` captures everything sent — no monkey-patching needed.
"""

from __future__ import annotations

import re

import pytest
from django.core import mail
from django.test import RequestFactory
from django.utils.http import urlsafe_base64_decode

from apps.accounts.emails import send_activation_email
from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_send_activation_email_puts_one_message_in_outbox() -> None:
    """GIVEN an inactive user
    WHEN send_activation_email is called
    THEN exactly one message lands in the outbox (no duplicates, no retries).
    """
    user = UserFactory(inactive=True, email="alice@example.com")
    request = RequestFactory().get("/accounts/register/")

    send_activation_email(user, request)

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_send_activation_email_uses_default_from_email(settings) -> None:
    """GIVEN settings.DEFAULT_FROM_EMAIL is configured
    WHEN send_activation_email runs
    THEN the message ``from_email`` matches the setting (not hardcoded)
    and ``to`` is the user's email.
    """
    settings.DEFAULT_FROM_EMAIL = "noreply@test.local"
    user = UserFactory(inactive=True, email="alice@example.com")
    request = RequestFactory().get("/accounts/register/")

    send_activation_email(user, request)

    sent = mail.outbox[0]
    assert sent.from_email == "noreply@test.local"
    assert sent.to == ["alice@example.com"]


@pytest.mark.django_db
def test_send_activation_email_subject_is_non_empty_single_line() -> None:
    """GIVEN an activation email
    WHEN it's composed
    THEN the subject is non-empty and single-line (Django enforces no
    newlines in email subjects — otherwise it 500s on send).
    """
    user = UserFactory(inactive=True)
    request = RequestFactory().get("/")

    send_activation_email(user, request)

    subject = mail.outbox[0].subject
    assert subject, "subject must not be empty"
    assert "\n" not in subject, "subject must be a single line"


@pytest.mark.django_db
def test_send_activation_email_body_contains_absolute_activation_url() -> None:
    """GIVEN a request with HTTP_HOST=testserver
    WHEN send_activation_email composes the message
    THEN the body contains an absolute URL anchored at the activate path —
    not just a relative ``/accounts/...`` (users clicking from a mail
    client need a full http(s) URL or it won't open).
    """
    user = UserFactory(inactive=True, email="alice@example.com")
    request = RequestFactory().get("/accounts/register/", HTTP_HOST="testserver")

    send_activation_email(user, request)

    body = mail.outbox[0].body
    assert "http://testserver/accounts/activate/" in body, (
        f"Body must contain an absolute activation URL anchored at "
        f"/accounts/activate/<uidb64>/<token>/. Body:\n{body}"
    )


@pytest.mark.django_db
def test_send_activation_email_link_encodes_user_pk() -> None:
    """GIVEN an activation email for a specific user
    WHEN we extract the uidb64 from the link and decode it
    THEN it decodes back to that user's pk — guards against a regression
    where the helper accidentally sends every user the same link.
    """
    user = UserFactory(inactive=True)
    request = RequestFactory().get("/", HTTP_HOST="testserver")

    send_activation_email(user, request)

    body = mail.outbox[0].body
    match = re.search(r"/accounts/activate/([^/]+)/([^/\s]+)/", body)
    assert match, f"could not find activation link in body:\n{body}"
    uidb64 = match.group(1)
    decoded_pk = urlsafe_base64_decode(uidb64).decode()
    assert int(decoded_pk) == user.pk


@pytest.mark.django_db
def test_send_activation_email_token_is_valid_for_user() -> None:
    """GIVEN the email helper produces a link with a token
    WHEN we feed that token back into ``default_token_generator.check_token``
    THEN it validates as a real, freshly issued token for that user —
    guards against a regression where the helper accidentally embeds
    a stale or wrong-user token.
    """
    from django.contrib.auth.tokens import default_token_generator

    user = UserFactory(inactive=True)
    request = RequestFactory().get("/", HTTP_HOST="testserver")

    send_activation_email(user, request)

    body = mail.outbox[0].body
    match = re.search(r"/accounts/activate/([^/]+)/([^/\s]+)/", body)
    assert match
    token = match.group(2)
    assert default_token_generator.check_token(user, token), (
        "Token embedded in the activation email must validate as a freshly "
        "issued token for the same user (round-trip check)."
    )
