"""Tests for cinema admin registration and ModelAdmin classes."""

import pytest
from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.safestring import SafeString

from apps.cinema.models import Actor, Director, Genre, Hall, Movie
from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    HallFactory,
    MovieFactory,
    ScreeningFactory,
)

pytestmark = pytest.mark.django_db


# Smallest valid PNG (1x1 transparent) — paste-ready bytes for ImageField tests.
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc"
    b"\xff\xff?\x03\x00\x06\x00\x02\x00\x01\xa5\xc8\x7f\xb1\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)


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


class TestHallAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Hall]
        assert ma.list_display == ("name", "capacity", "screenings_count")

    def test_search_fields(self):
        ma = admin.site._registry[Hall]
        assert ma.search_fields == ("name",)

    def test_screenings_count_zero_when_no_screenings(self):
        hall = HallFactory()
        ma = admin.site._registry[Hall]
        assert ma.screenings_count(hall) == 0

    def test_screenings_count_returns_related_screening_count(self):
        hall = HallFactory()
        ScreeningFactory.create_batch(3, hall=hall)
        ma = admin.site._registry[Hall]
        assert ma.screenings_count(hall) == 3

    def test_screenings_count_has_short_description(self):
        ma = admin.site._registry[Hall]
        assert ma.screenings_count.short_description == "screenings"


class TestActorAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Actor]
        assert ma.list_display == ("full_name", "photo_thumbnail", "movies_count")

    def test_search_fields(self):
        ma = admin.site._registry[Actor]
        assert ma.search_fields == ("full_name",)

    def test_photo_thumbnail_returns_dash_when_no_photo(self):
        actor = ActorFactory(photo="")
        ma = admin.site._registry[Actor]
        assert ma.photo_thumbnail(actor) == "—"

    def test_photo_thumbnail_returns_img_tag_when_photo_set(self):
        actor = ActorFactory()
        actor.photo = SimpleUploadedFile("a.png", PNG_1X1, content_type="image/png")
        actor.save()
        ma = admin.site._registry[Actor]
        result = ma.photo_thumbnail(actor)
        assert isinstance(result, SafeString)
        assert "<img" in result
        assert actor.photo.url in result

    def test_movies_count_zero_when_no_movies(self):
        actor = ActorFactory()
        ma = admin.site._registry[Actor]
        assert ma.movies_count(actor) == 0

    def test_movies_count_returns_related_movie_count(self):
        actor = ActorFactory()
        m1 = MovieFactory()
        m2 = MovieFactory()
        m1.actors.add(actor)
        m2.actors.add(actor)
        ma = admin.site._registry[Actor]
        assert ma.movies_count(actor) == 2

    def test_thumbnail_and_count_have_short_descriptions(self):
        ma = admin.site._registry[Actor]
        assert ma.photo_thumbnail.short_description == "photo"
        assert ma.movies_count.short_description == "movies"


class TestDirectorAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Director]
        assert ma.list_display == ("full_name", "photo_thumbnail", "movies_count")

    def test_search_fields(self):
        ma = admin.site._registry[Director]
        assert ma.search_fields == ("full_name",)

    def test_photo_thumbnail_returns_dash_when_no_photo(self):
        director = DirectorFactory(photo="")
        ma = admin.site._registry[Director]
        assert ma.photo_thumbnail(director) == "—"

    def test_photo_thumbnail_returns_img_tag_when_photo_set(self):
        director = DirectorFactory()
        director.photo = SimpleUploadedFile("d.png", PNG_1X1, content_type="image/png")
        director.save()
        ma = admin.site._registry[Director]
        result = ma.photo_thumbnail(director)
        assert isinstance(result, SafeString)
        assert "<img" in result
        assert director.photo.url in result

    def test_movies_count_returns_related_movie_count(self):
        director = DirectorFactory()
        m = MovieFactory()
        m.directors.add(director)
        ma = admin.site._registry[Director]
        assert ma.movies_count(director) == 1
