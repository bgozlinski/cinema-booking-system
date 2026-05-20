"""Tests for cinema admin registration and ModelAdmin classes."""

import pytest
from django.contrib import admin

from apps.cinema.models import Actor, Director, Genre, Hall, Movie

pytestmark = pytest.mark.django_db


class TestAdminRegistration:
    """All cinema models must be registered with the admin site (US-15 / FR-11)."""

    def test_genre_is_registered(self):
        assert admin.site.is_registered(Genre)

    def test_hall_is_registered(self):
        assert admin.site.is_registered(Hall)

    def test_actor_is_registered(self):
        assert admin.site.is_registered(Actor)

    def test_director_is_registered(self):
        assert admin.site.is_registered(Director)

    def test_movie_is_registered(self):
        assert admin.site.is_registered(Movie)
