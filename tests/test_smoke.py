"""Smoke tests for the project skeleton.

Three tests:
- `test_app_starts` — Django serves /admin/login/ without 500. (US-01)
- `test_settings_loads_env_vars` — django-environ correctly populated
  SECRET_KEY and DEBUG from .env / .env.example. (US-01)
- `test_database_is_postgres` — DATABASE_URL points at PostgreSQL via
  docker-compose, not SQLite. (US-02)

These tests have no business logic to assert — they only confirm that
the Poetry venv, settings package, pytest-django wiring, and dockerised
PostgreSQL are sane. Domain tests start at US-06 (custom User model).
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.db import connection
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


@pytest.mark.django_db
def test_database_is_postgres() -> None:
    """GIVEN DATABASE_URL pointing at the docker-compose Postgres instance
    WHEN django opens its default DB connection
    THEN connection.vendor == 'postgresql' (proves we're not on SQLite anymore).

    Catches accidental SQLite fallback (e.g. `.env` not loaded, DATABASE_URL
    typo) and confirms the docker-compose service is reachable.
    """
    assert connection.vendor == "postgresql", (
        f"Expected 'postgresql', got '{connection.vendor}'. "
        "Verify DATABASE_URL in .env starts with 'postgres://' and that "
        "`docker compose up -d` is running (check with `docker compose ps`)."
    )
    assert connection.is_usable(), (
        "Postgres connection opened but is not usable — likely the container "
        "is up but the DB inside is still initialising. Wait for healthcheck "
        "to report 'healthy', then re-run."
    )
