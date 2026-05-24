import datetime as dt
from datetime import timedelta

import pytest
from django.utils import timezone

from tests.accounts.factories import UserFactory
from tests.booking.factories import ConfirmedBookingFactory
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


class TestScreenings:
    def test_list_anon_with_available_seats(self, api_client):
        hall = HallFactory(name="A", capacity=10)
        screening = ScreeningFactory(hall=hall, start_time=timezone.now() + timedelta(days=2))
        ConfirmedBookingFactory(screening=screening, seats_count=3)
        resp = api_client.get("/api/v1/screenings/")
        assert resp.status_code == 200
        row = next(s for s in resp.data["results"] if s["id"] == screening.id)
        assert row["available_seats_count"] == 7
        assert row["movie"]["id"] == screening.movie_id
        assert {"id", "name", "capacity", "description"} <= set(row["hall"])

    def test_filter_by_date(self, api_client):
        # Pin to noon local on the target day -> deterministic across TZ/DST
        # (avoids the now()+1day-UTC vs localdate()+1 boundary flakiness).
        target = timezone.localdate() + timedelta(days=1)
        on_time = timezone.make_aware(dt.datetime.combine(target, dt.time(12, 0)))
        on = ScreeningFactory(start_time=on_time)
        ScreeningFactory(start_time=on_time + timedelta(days=9))
        resp = api_client.get(f"/api/v1/screenings/?date={target.isoformat()}")
        ids = {s["id"] for s in resp.data["results"]}
        assert on.id in ids
        assert len(ids) == 1

    def test_filter_by_movie_and_hall(self, api_client):
        hall = HallFactory(name="H1")
        s1 = ScreeningFactory(hall=hall)
        ScreeningFactory()  # different movie + hall
        resp = api_client.get(f"/api/v1/screenings/?movie={s1.movie_id}&hall={hall.id}")
        ids = {s["id"] for s in resp.data["results"]}
        assert ids == {s1.id}

    def test_detail(self, api_client):
        screening = ScreeningFactory()
        resp = api_client.get(f"/api/v1/screenings/{screening.id}/")
        assert resp.status_code == 200
        assert "available_seats_count" in resp.data

    def test_list_query_budget(self, api_client, django_assert_max_num_queries):
        for _ in range(8):
            ScreeningFactory(start_time=timezone.now() + timedelta(days=2))
        with django_assert_max_num_queries(6):
            api_client.get("/api/v1/screenings/")
