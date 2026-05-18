"""Tests for ``apps.accounts.forms`` (FR-06).

Two forms under test:

- ``RegistrationForm`` — subclass of ``UserCreationForm`` adapted for the
  email-only login model. Inherits Django's password-match validator and
  AUTH_PASSWORD_VALIDATORS checks; we verify the email/unique/required
  paths because those are the surface that callers (RegisterView) rely on.
- ``ResendActivationForm`` — single-field form. Tested for required +
  email-syntax validation; the view-level "no enumeration leak" behavior
  is tested separately in ``test_resend.py``.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.forms import RegistrationForm, ResendActivationForm
from tests.accounts.factories import UserFactory

User = get_user_model()


# ─── RegistrationForm ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_registration_form_creates_user_with_email_and_hashed_password() -> None:
    """GIVEN valid POST data (email + matching passwords)
    WHEN form.is_valid + form.save
    THEN a persisted user is returned with email set and password hashed
    (verifiable via check_password — guards against a regression where
    Meta.fields drops password handling).
    """
    form = RegistrationForm(
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert form.is_valid(), form.errors
    user = form.save()

    assert user.email == "newbie@example.com"
    assert user.check_password("Str0ngP@ssw0rd"), (
        "Password must be hashed (set_password) — UserCreationForm.save() "
        "is expected to handle this automatically. If this fails, Meta is "
        "probably missing the password handling somehow."
    )
    assert User.objects.filter(email="newbie@example.com").exists()


@pytest.mark.django_db
def test_registration_form_rejects_mismatched_passwords() -> None:
    """GIVEN password1 != password2
    WHEN is_valid()
    THEN the form is invalid with an error on ``password2`` (Django's
    standard UserCreationForm convention)."""
    form = RegistrationForm(
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "different-pw",
        }
    )

    assert not form.is_valid()
    assert "password2" in form.errors


@pytest.mark.django_db
def test_registration_form_rejects_duplicate_email() -> None:
    """GIVEN an existing user with email "existing@example.com"
    WHEN we submit the form with the same email
    THEN the form is invalid with an error on ``email`` — enforced at
    form level (UserCreationForm + model unique=True) so callers get a
    nice field error instead of an IntegrityError at save time."""
    UserFactory(email="existing@example.com")

    form = RegistrationForm(
        data={
            "email": "existing@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert not form.is_valid()
    assert "email" in form.errors


def test_registration_form_rejects_invalid_email_syntax() -> None:
    """GIVEN syntactically invalid email
    WHEN is_valid()
    THEN error on ``email`` (Django EmailField validator)."""
    form = RegistrationForm(
        data={
            "email": "not-an-email",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert not form.is_valid()
    assert "email" in form.errors


def test_registration_form_requires_email() -> None:
    """GIVEN empty email field
    WHEN is_valid()
    THEN error on ``email`` (required=True implicit via Meta.fields)."""
    form = RegistrationForm(
        data={
            "email": "",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert not form.is_valid()
    assert "email" in form.errors


@pytest.mark.django_db
def test_registration_form_rejects_weak_password() -> None:
    """GIVEN a too-common / too-short password
    WHEN is_valid()
    THEN error on ``password2`` — AUTH_PASSWORD_VALIDATORS (CommonPassword,
    MinimumLength) are wired by UserCreationForm. This is a sanity check
    that we didn't accidentally bypass them.

    Marked django_db because ModelForm.is_valid() runs the unique-email
    check against the DB even when the password validators are the ones
    flagging the error.
    """
    form = RegistrationForm(
        data={
            "email": "newbie@example.com",
            "password1": "password",  # CommonPasswordValidator should reject
            "password2": "password",
        }
    )

    assert not form.is_valid()
    assert "password2" in form.errors


# ─── ResendActivationForm ───────────────────────────────────────────────────


def test_resend_activation_form_valid_with_email() -> None:
    """GIVEN syntactically valid email (any string — view layer decides
    whether to actually send)
    WHEN is_valid()
    THEN form is valid. The form is intentionally permissive at this
    layer — view-level logic handles the user-existence check silently
    (no enumeration leak)."""
    form = ResendActivationForm(data={"email": "anyone@example.com"})
    assert form.is_valid(), form.errors


def test_resend_activation_form_rejects_invalid_email() -> None:
    form = ResendActivationForm(data={"email": "not-an-email"})
    assert not form.is_valid()
    assert "email" in form.errors


def test_resend_activation_form_requires_email() -> None:
    form = ResendActivationForm(data={"email": ""})
    assert not form.is_valid()
    assert "email" in form.errors
