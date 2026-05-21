"""Tests for MovieDetailView (US-13 / FR-03)."""

import pytest
from django.urls import reverse

from tests.cinema.factories import MovieFactory

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
