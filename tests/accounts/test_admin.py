"""Admin registration tests for ``accounts.User`` (US-06, FR-11).

Two checks:

- ``test_user_admin_is_registered`` — ``User`` appears in ``admin.site._registry``.
- ``test_user_admin_form_has_no_username_field`` — neither the create nor
  the change fieldsets contain ``'username'``. Django's default
  ``UserAdmin`` (inherited from ``django.contrib.auth.admin``) includes
  ``'username'`` everywhere; FR-05 requires email-only auth, so the
  custom admin must drop it.

We intentionally inspect the admin class attributes rather than rendering
``/admin/accounts/user/add/`` because the latter pulls in URL routing,
templates, and authentication — overkill for verifying a configuration
fact. End-to-end admin rendering is covered manually in step 6 of US-06.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


def _collect_field_names(fieldsets: Iterable[Any] | None) -> list[str]:
    """Flatten ``fieldsets`` tuples into a list of field names.

    Django's fieldsets format is ``((header, {'fields': (...)}), ...)``.
    Returns an empty list when ``fieldsets`` is ``None`` so callers can
    treat ``add_fieldsets`` / ``fieldsets`` uniformly.
    """
    names: list[str] = []
    for _header, options in fieldsets or ():
        names.extend(options.get("fields", ()))
    return names


def test_user_admin_is_registered() -> None:
    """GIVEN a custom UserAdmin in ``accounts/admin.py``
    WHEN inspecting ``admin.site._registry``
    THEN ``accounts.User`` is present (registration ran at import time).
    """
    assert User in admin.site._registry, (
        "accounts.User is not registered with admin.site — verify that "
        "accounts/admin.py calls admin.site.register(User, UserAdmin) "
        "and that the accounts app is in INSTALLED_APPS."
    )


def test_user_admin_form_has_no_username_field() -> None:
    """GIVEN the custom UserAdmin
    WHEN inspecting its ``add_fieldsets`` and ``fieldsets``
    THEN ``'username'`` does not appear in either (FR-05 — email-only auth).

    The default ``django.contrib.auth.admin.UserAdmin`` declares
    ``'username'`` in both add and change fieldsets. Forgetting to
    override them is the most common source of "createsuperuser asks for
    username" regressions when wiring a custom user model.
    """
    user_admin = admin.site._registry[User]

    add_fields = _collect_field_names(getattr(user_admin, "add_fieldsets", None))
    change_fields = _collect_field_names(user_admin.fieldsets)

    assert "username" not in add_fields, (
        f"UserAdmin.add_fieldsets contains 'username' — override it to drop "
        f"the field (FR-05). Current add fields: {add_fields!r}."
    )
    assert "username" not in change_fields, (
        f"UserAdmin.fieldsets contains 'username' — override it to drop "
        f"the field (FR-05). Current change fields: {change_fields!r}."
    )
