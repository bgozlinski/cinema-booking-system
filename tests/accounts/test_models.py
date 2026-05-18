"""Model tests for ``accounts.User`` (US-06, FR-05).

Covers all five acceptance criteria from the US-06 card:

- ``test_create_user_with_email`` — happy path through ``UserManager.create_user``
- ``test_create_user_without_email_raises`` — blank email → ``ValueError``
- ``test_create_superuser_sets_flags`` — ``is_staff`` and ``is_superuser`` True
- ``test_email_is_username_field`` — model declares email as login field
- ``test_email_unique`` — DB-level unique constraint on email

These tests deliberately exercise the public API (``User.objects.create_user``,
``User.USERNAME_FIELD``) rather than poking at attributes directly — that way
the suite still passes if the implementation moves around between
``managers.py`` / ``models.py`` so long as behaviour is preserved.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_create_user_with_email() -> None:
    """GIVEN ``UserManager.create_user``
    WHEN called with a valid email and password
    THEN a persisted user is returned with the email set, the password
    hashed (verifiable via ``check_password``), and ``is_staff`` /
    ``is_superuser`` defaulting to False.
    """
    user = User.objects.create_user(email="alice@example.com", password="s3cret-test-pw")

    assert user.pk is not None, "create_user should persist the user to the DB"
    assert user.email == "alice@example.com"
    assert user.check_password("s3cret-test-pw"), (
        "Password should be hashed (set_password) — check_password must verify "
        "the raw value. If this fails, UserManager.create_user is likely "
        "storing the cleartext password instead of calling set_password()."
    )
    assert user.is_staff is False, "Regular users must default to is_staff=False"
    assert user.is_superuser is False, "Regular users must default to is_superuser=False"


@pytest.mark.django_db
def test_create_user_without_email_raises() -> None:
    """GIVEN ``UserManager.create_user``
    WHEN called with an empty email
    THEN ``ValueError`` is raised before any DB write — the validation
    must live in the manager (not rely on the DB unique constraint or a
    form), otherwise empty-string emails would silently get persisted.
    """
    with pytest.raises(ValueError, match=r"(?i)email"):
        User.objects.create_user(email="", password="whatever")


@pytest.mark.django_db
def test_create_superuser_sets_flags() -> None:
    """GIVEN ``UserManager.create_superuser``
    WHEN called with email + password
    THEN the returned user has ``is_staff=True`` and ``is_superuser=True``
    (the createsuperuser management command relies on these defaults).
    """
    admin = User.objects.create_superuser(email="admin@example.com", password="adm1n-pw")

    assert admin.is_staff is True, "create_superuser must set is_staff=True"
    assert admin.is_superuser is True, "create_superuser must set is_superuser=True"
    assert admin.check_password("adm1n-pw")


def test_email_is_username_field() -> None:
    """GIVEN the custom ``User`` model
    WHEN inspecting ``USERNAME_FIELD`` and ``REQUIRED_FIELDS``
    THEN ``USERNAME_FIELD == 'email'`` and ``'email'`` is *not* in
    ``REQUIRED_FIELDS`` (Django enforces this invariant and
    ``createsuperuser`` fails noisily if it is violated).
    """
    assert User.USERNAME_FIELD == "email", (
        f"Expected User.USERNAME_FIELD == 'email' (FR-05 — email-only login), "
        f"got {User.USERNAME_FIELD!r}."
    )
    assert "email" not in User.REQUIRED_FIELDS, (
        f"'email' must NOT appear in REQUIRED_FIELDS — it is already the "
        f"USERNAME_FIELD. Current REQUIRED_FIELDS={User.REQUIRED_FIELDS!r}."
    )


@pytest.mark.django_db
def test_email_unique() -> None:
    """GIVEN an existing user with email ``dup@example.com``
    WHEN a second user is created with the same email
    THEN the DB raises ``IntegrityError`` (unique constraint enforced at
    the schema level, not only via a form validator).

    Schema-level uniqueness matters because admin and management commands
    bypass forms and would otherwise silently create duplicate accounts.
    """
    User.objects.create_user(email="dup@example.com", password="pw1")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@example.com", password="pw2")
