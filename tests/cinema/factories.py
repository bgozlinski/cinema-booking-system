"""factory_boy factories for the cinema app.

Mirrors tests/accounts/factories.py pattern. Each factory creates a model
instance with sensible defaults. Caller can override any field; M2M
relationships on MovieFactory use post_generation hooks.
"""

from __future__ import annotations

import factory
from factory import Faker as FactoryFaker
from factory import Sequence, post_generation


class GenreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "cinema.Genre"  # lazy string lookup via Django apps registry
        django_get_or_create = ("name",)

    name = Sequence(lambda n: f"Genre {n}")


class ActorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "cinema.Actor"

    full_name = FactoryFaker("name", locale="pl_PL")
    # photo: blank by default (ImageField with blank=True)
    # biography: blank by default


class DirectorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "cinema.Director"

    full_name = FactoryFaker("name", locale="pl_PL")


class HallFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "cinema.Hall"
        django_get_or_create = ("name",)

    name = Sequence(lambda n: f"Sala {n}")
    capacity = 100


class MovieFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "cinema.Movie"
        skip_postgeneration_save = True

    title = Sequence(lambda n: f"Film {n}")
    description = FactoryFaker("paragraph")
    release_date = FactoryFaker("date_this_year")
    duration_minutes = 120
    # poster blank, trailer_url blank by default

    @post_generation
    def genres(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for genre in extracted:
            self.genres.add(genre)

    @post_generation
    def actors(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for actor in extracted:
            self.actors.add(actor)

    @post_generation
    def directors(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for director in extracted:
            self.directors.add(director)
