"""Tests for MovieDetailView (US-13 / FR-03)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.cinema.factories import MovieFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


class TestRouting:
    def test_detail_url_returns_200(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200

    def test_missing_pk_returns_404(self, client):
        response = client.get("/movies/99999/")
        assert response.status_code == 404

    def test_movie_detail_reverses_correctly(self):
        movie = MovieFactory()
        assert reverse("cinema:movie_detail", kwargs={"pk": movie.pk}) == f"/movies/{movie.pk}/"

    def test_detail_uses_movie_detail_template(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_detail.html" in template_names

    def test_anonymous_user_gets_200(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200

    def test_authenticated_user_gets_200(self, client, django_user_model):
        movie = MovieFactory()
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200


class TestMovieGetAbsoluteUrl:
    def test_returns_detail_path(self):
        movie = MovieFactory()
        assert movie.get_absolute_url() == f"/movies/{movie.pk}/"


class TestContext:
    def test_trailer_embed_url_for_youtube(self, client):
        movie = MovieFactory(trailer_url="https://youtu.be/dQw4w9WgXcQ")
        response = client.get(f"/movies/{movie.pk}/")
        assert (
            response.context["trailer_embed_url"]
            == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
        )

    def test_trailer_embed_url_is_none_for_non_youtube(self, client):
        movie = MovieFactory(trailer_url="https://example.com/clip.mp4")
        response = client.get(f"/movies/{movie.pk}/")
        assert response.context["trailer_embed_url"] is None

    def test_trailer_embed_url_is_none_for_blank_trailer(self, client):
        movie = MovieFactory(trailer_url="")
        response = client.get(f"/movies/{movie.pk}/")
        assert response.context["trailer_embed_url"] is None

    def test_upcoming_screenings_includes_future(self, client):
        movie = MovieFactory()
        future = ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        response = client.get(f"/movies/{movie.pk}/")
        assert future in list(response.context["upcoming_screenings"])

    def test_upcoming_screenings_excludes_past(self, client):
        movie = MovieFactory()
        past = ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))
        response = client.get(f"/movies/{movie.pk}/")
        assert past not in list(response.context["upcoming_screenings"])

    def test_upcoming_screenings_sorted_ascending(self, client):
        movie = MovieFactory()
        now = timezone.now()
        s_late = ScreeningFactory(movie=movie, start_time=now + timedelta(days=3))
        s_early = ScreeningFactory(movie=movie, start_time=now + timedelta(days=1))
        s_mid = ScreeningFactory(movie=movie, start_time=now + timedelta(days=2))

        response = client.get(f"/movies/{movie.pk}/")

        listed = list(response.context["upcoming_screenings"])
        assert listed == [s_early, s_mid, s_late]

    def test_upcoming_screenings_empty_for_orphan(self, client):
        movie = MovieFactory()  # no screenings
        response = client.get(f"/movies/{movie.pk}/")
        assert list(response.context["upcoming_screenings"]) == []
