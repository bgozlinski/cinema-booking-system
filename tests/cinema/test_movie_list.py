"""Tests for MovieListView (US-11 / FR-01)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.cinema.factories import MovieFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


class TestRouting:
    def test_root_url_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_movies_url_returns_200(self, client):
        response = client.get("/movies/")
        assert response.status_code == 200

    def test_cinema_home_reverses_to_root(self):
        assert reverse("cinema:home") == "/"

    def test_cinema_movie_list_reverses_to_movies(self):
        assert reverse("cinema:movie_list") == "/movies/"

    def test_root_uses_movie_list_template(self, client):
        response = client.get("/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_list.html" in template_names

    def test_movies_uses_movie_list_template(self, client):
        response = client.get("/movies/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_list.html" in template_names

    def test_anonymous_user_gets_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_authenticated_user_gets_200(self, client, django_user_model):
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get("/")
        assert response.status_code == 200


class TestQueryset:
    def test_movie_with_future_screening_is_visible(self, client):
        movie = MovieFactory(title="Future Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")

        assert movie in response.context["movies"]

    def test_movie_with_only_past_screening_is_hidden(self, client):
        movie = MovieFactory(title="Past Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))

        response = client.get("/")

        assert movie not in response.context["movies"]

    def test_movie_with_no_screenings_is_hidden(self, client):
        movie = MovieFactory(title="Orphan Movie")

        response = client.get("/")

        assert movie not in response.context["movies"]

    def test_movie_with_past_and_future_screenings_uses_future_as_next(self, client):
        """Regression: Min() must include filter=Q(start_time>=now), otherwise
        next_screening_at picks up the past screening's date."""
        movie = MovieFactory(title="Mixed Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=3))
        future = timezone.now() + timedelta(days=2)
        ScreeningFactory(movie=movie, start_time=future)

        response = client.get("/")

        listed = list(response.context["movies"])
        assert movie in listed
        # The annotation rounds to microseconds; allow 1-second tolerance.
        rendered = next(m for m in listed if m.pk == movie.pk)
        assert abs((rendered.next_screening_at - future).total_seconds()) < 1

    def test_movies_are_sorted_by_next_screening_ascending(self, client):
        now = timezone.now()
        movie_late = MovieFactory(title="Late")
        movie_early = MovieFactory(title="Early")
        movie_mid = MovieFactory(title="Mid")
        ScreeningFactory(movie=movie_late, start_time=now + timedelta(days=3))
        ScreeningFactory(movie=movie_early, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=movie_mid, start_time=now + timedelta(days=2))

        response = client.get("/")

        titles = [m.title for m in response.context["movies"]]
        assert titles == ["Early", "Mid", "Late"]
