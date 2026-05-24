from datetime import timedelta

import pytest
from django.utils import timezone

from tests.accounts.factories import UserFactory
from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    HallFactory,
    MovieFactory,
    ScreeningFactory,
)

pytestmark = pytest.mark.django_db


class TestSimpleResources:
    def test_genres_list_anon(self, api_client):
        GenreFactory(name="Sci-Fi")
        resp = api_client.get("/api/v1/genres/")
        assert resp.status_code == 200
        names = {g["name"] for g in resp.data["results"]}
        assert "Sci-Fi" in names

    def test_halls_list_anon(self, api_client):
        HallFactory(name="IMAX", capacity=300)
        resp = api_client.get("/api/v1/halls/")
        assert resp.status_code == 200
        assert {"id", "name", "description", "capacity"} <= set(resp.data["results"][0])

    def test_actors_list_anon(self, api_client):
        ActorFactory(full_name="Keanu Reeves")
        resp = api_client.get("/api/v1/actors/")
        assert resp.status_code == 200
        assert {"id", "full_name", "photo", "biography"} <= set(resp.data["results"][0])

    def test_directors_list_anon(self, api_client):
        DirectorFactory(full_name="Lana Wachowski")
        resp = api_client.get("/api/v1/directors/")
        assert resp.status_code == 200
        assert any(d["full_name"] == "Lana Wachowski" for d in resp.data["results"])

    def test_write_method_not_allowed_for_authed_user(self, auth_client):
        # Authenticated so we pass IsAuthenticatedOrReadOnly; ReadOnlyModelViewSet
        # has no create handler -> 405 (anon would 401 at the auth wall first).
        resp = auth_client(UserFactory()).post("/api/v1/genres/", {"name": "X"}, format="json")
        assert resp.status_code == 405

    def test_anon_write_unauthorized(self, api_client):
        resp = api_client.post("/api/v1/genres/", {"name": "X"}, format="json")
        assert resp.status_code == 401


class TestMovies:
    def test_list_anon_paginated_full_catalog(self, api_client):
        # 13 movies, none with screenings -> still all listed (full catalog)
        for _ in range(13):
            MovieFactory()
        resp = api_client.get("/api/v1/movies/")
        assert resp.status_code == 200
        assert resp.data["count"] == 13
        assert len(resp.data["results"]) == 12  # PAGE_SIZE

    def test_list_item_shape(self, api_client):
        scifi = GenreFactory(name="Sci-Fi")
        MovieFactory(title="The Matrix", genres=[scifi])
        resp = api_client.get("/api/v1/movies/?search=Matrix")
        assert resp.status_code == 200
        item = resp.data["results"][0]
        assert {"id", "title", "release_date", "duration_minutes", "poster", "genres"} == set(item)
        assert item["genres"][0]["name"] == "Sci-Fi"

    def test_filter_by_genre(self, api_client):
        scifi = GenreFactory(name="Sci-Fi")
        drama = GenreFactory(name="Drama")
        MovieFactory(title="Matrix", genres=[scifi])
        MovieFactory(title="Rain Man", genres=[drama])
        resp = api_client.get(f"/api/v1/movies/?genre={scifi.id}")
        titles = {m["title"] for m in resp.data["results"]}
        assert titles == {"Matrix"}

    def test_filter_by_release_date_range(self, api_client):
        MovieFactory(title="Old", release_date="2000-01-01")
        MovieFactory(title="New", release_date="2025-01-01")
        resp = api_client.get("/api/v1/movies/?release_date_after=2010-01-01")
        titles = {m["title"] for m in resp.data["results"]}
        assert titles == {"New"}

    def test_detail_nested_shape(self, api_client):
        actor = ActorFactory(full_name="Keanu Reeves")
        director = DirectorFactory(full_name="Lana Wachowski")
        scifi = GenreFactory(name="Sci-Fi")
        movie = MovieFactory(title="Matrix", genres=[scifi], actors=[actor], directors=[director])
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=3))
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=3))  # past
        resp = api_client.get(f"/api/v1/movies/{movie.id}/")
        assert resp.status_code == 200
        assert resp.data["title"] == "Matrix"
        assert resp.data["genres"][0]["name"] == "Sci-Fi"
        assert resp.data["actors"][0]["full_name"] == "Keanu Reeves"
        assert resp.data["directors"][0]["full_name"] == "Lana Wachowski"
        assert len(resp.data["upcoming_screenings"]) == 1  # past excluded
        assert "available_seats_count" in resp.data["upcoming_screenings"][0]
