"""Tests for cinema admin registration and ModelAdmin classes."""

import pytest
from django.contrib import admin

from apps.cinema.models import Actor, Director, Genre, Hall, Movie
from tests.cinema.factories import GenreFactory, MovieFactory

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


class TestGenreAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Genre]
        assert ma.list_display == ("name", "movies_count")

    def test_search_fields(self):
        ma = admin.site._registry[Genre]
        assert ma.search_fields == ("name",)

    def test_movies_count_zero_when_no_movies(self):
        genre = GenreFactory()
        ma = admin.site._registry[Genre]
        assert ma.movies_count(genre) == 0

    def test_movies_count_returns_related_movie_count(self):
        genre = GenreFactory()
        m1 = MovieFactory()
        m2 = MovieFactory()
        m1.genres.add(genre)
        m2.genres.add(genre)
        ma = admin.site._registry[Genre]
        assert ma.movies_count(genre) == 2

    def test_movies_count_has_short_description(self):
        ma = admin.site._registry[Genre]
        assert ma.movies_count.short_description == "movies"
