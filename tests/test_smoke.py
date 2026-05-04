"""Smoke tests for US-01 — verify the project skeleton boots.

Two tests:
- `test_app_starts` — Django serves /admin/login/ without 500.
- `test_settings_loads_env_vars` — django-environ correctly populated
  SECRET_KEY and DEBUG from .env / .env.example.

These tests have no business logic to assert — they only confirm that
the Poetry venv, settings package, and pytest-django wiring are sane.
Domain tests start at US-06 (custom User model).
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.test import Client


@pytest.mark.django_db
def test_app_starts(client: Client) -> None:
    """GIVEN a fresh Django project bootstrap
    WHEN GET /admin/login/ (the only URL wired in US-01)
    THEN the admin login form renders with HTTP 200.
    """
    response = client.get("/admin/login/")

    assert response.status_code == 200, (
        f"Expected 200 from /admin/login/, got {response.status_code}. "
        "If 500 — check that settings.dev loads, SECRET_KEY is set, and "
        "django.contrib.admin is in INSTALLED_APPS."
    )


def test_settings_loads_env_vars() -> None:
    """GIVEN .env (copied from .env.example) loaded by django-environ
    WHEN django settings are imported
    THEN SECRET_KEY is non-empty and DEBUG is True (dev profile invariant).
    """
    assert settings.SECRET_KEY, (
        "settings.SECRET_KEY is empty — django-environ did not read SECRET_KEY "
        "from .env. Verify environ.Env.read_env(BASE_DIR / '.env') runs in "
        "settings/base.py."
    )
    assert settings.SECRET_KEY != "change-me-in-production-and-keep-this-fake", (
        "settings.SECRET_KEY equals the .env.example placeholder — copy "
        ".env.example to .env and replace with a real-ish value."
    )

    assert settings.DEBUG is True, (
        f"settings.DEBUG should be True under settings.dev, got {settings.DEBUG}. "
        "Verify settings/dev.py forces DEBUG = True after `from settings.base import *`."
    )
