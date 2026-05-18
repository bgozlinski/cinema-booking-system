"""factory_boy factories for the accounts app.

Use ``UserFactory`` whenever a test needs an arbitrary user — it routes
through ``UserManager.create_user`` / ``create_superuser`` so passwords
are hashed correctly and any future manager-level invariants
(normalised email, default flags, audit fields) apply automatically.

Examples:
    UserFactory()                                  # regular user, hashed pw
    UserFactory(email="alice@example.com")         # explicit email
    UserFactory(is_superuser=True)                 # superuser path
"""

from __future__ import annotations

from typing import Any

import factory
from django.contrib.auth import get_user_model


class UserFactory(factory.django.DjangoModelFactory):
    """Create ``accounts.User`` instances via the custom manager."""

    class Meta:
        model = get_user_model()
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = "test1234"

    @classmethod
    def _create(cls, model_class: type, *args: Any, **kwargs: Any) -> Any:
        """Route creation through ``create_user`` / ``create_superuser``.

        Default ``DjangoModelFactory._create`` calls ``Model.objects.create``,
        which bypasses our manager — passwords would be stored in cleartext
        and any future manager invariants would not run. Pop ``is_superuser``
        to dispatch to the right manager method; everything else flows through
        as ``**extra_fields``.
        """
        is_superuser = kwargs.pop("is_superuser", False)
        manager = cls._get_manager(model_class)
        if is_superuser:
            return manager.create_superuser(*args, **kwargs)
        return manager.create_user(*args, **kwargs)
