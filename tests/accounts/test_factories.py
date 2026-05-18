"""Smoke tests for ``UserFactory`` traits (FR-06).

The ``inactive`` trait is load-bearing for the email-activation tests —
if it silently produces an active user, every "inactive user cannot log in"
test would pass for the wrong reason. These cheap smoke tests catch that
regression at the factory level so failures point at the right place.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from tests.accounts.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
def test_user_factory_default_is_active() -> None:
    """GIVEN ``UserFactory()`` with no overrides
    WHEN a user is created
    THEN ``is_active`` defaults to True — backwards-compat with all
    pre-FR-06 tests (US-06 model/admin tests) that never set this
    explicitly and rely on the default.
    """
    user = UserFactory()
    assert user.is_active is True


@pytest.mark.django_db
def test_user_factory_inactive_trait_creates_inactive_user() -> None:
    """GIVEN ``UserFactory(inactive=True)``
    WHEN a user is created
    THEN ``is_active`` is False and the user is still persisted to the DB
    (so views under test can fetch them via ``User.objects.get(...)`` /
    activation tokens still work — the user record must exist for
    ``default_token_generator`` to validate against it).
    """
    user = UserFactory(inactive=True)
    assert user.is_active is False
    assert User.objects.filter(email=user.email).exists(), (
        "Inactive user must still be persisted — activation views fetch "
        "the user by pk via the uidb64 in the link."
    )


@pytest.mark.django_db
def test_user_factory_inactive_trait_does_not_leak_to_subsequent_calls() -> None:
    """GIVEN one inactive user followed by a default-flag call
    WHEN both are created in the same test
    THEN the second user is active — the trait must NOT mutate class
    state. (factory_boy traits are scoped to the single call, but a
    naive implementation that sets ``cls.is_active = False`` would
    poison subsequent factories. This is the regression guard.)
    """
    inactive = UserFactory(inactive=True)
    active = UserFactory()

    assert inactive.is_active is False
    assert active.is_active is True
