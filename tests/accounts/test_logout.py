"""Tests for the logout view (FR-06).

Uses Django's stock ``auth_views.LogoutView``. Behaviour under test:

- POST → session destroyed + redirect to LOGOUT_REDIRECT_URL
- GET → 405 (Django 5+ default; logout via GET enables CSRF-style attacks
  where an attacker embeds an ``<img src="/accounts/logout/">`` to log
  victims out)
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_logout_post_destroys_session(client) -> None:
    """GIVEN a logged-in user
    WHEN POST /accounts/logout/
    THEN session is destroyed and we redirect to LOGOUT_REDIRECT_URL (/)."""
    user = UserFactory(email="alice@example.com", password="test1234")
    client.force_login(user)
    assert "_auth_user_id" in client.session

    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_logout_get_returns_405(client) -> None:
    """GET on logout must return 405 — Django 5+ default. Prevents
    drive-by logout where an attacker embeds a logout URL as an img/link
    on another page."""
    user = UserFactory(email="alice@example.com", password="test1234")
    client.force_login(user)

    response = client.get(reverse("accounts:logout"))

    assert response.status_code == 405
