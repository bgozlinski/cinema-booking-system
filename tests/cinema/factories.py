"""factory_boy factories for the cinema app.

Mirrors tests/accounts/factories.py pattern. Each factory creates a model
instance with sensible defaults. Caller can override any field; M2M
relationships on MovieFactory use post_generation hooks.
"""

from __future__ import annotations

import factory
from factory import Sequence

from apps.cinema.models import Genre


class GenreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Genre
        django_get_or_create = ("name",)

    name = Sequence(lambda n: f"Genre {n}")
