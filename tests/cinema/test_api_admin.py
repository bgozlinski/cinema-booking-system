from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

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


def _image(fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(f"x.{fmt.lower()}", buf.read(), content_type=f"image/{fmt.lower()}")


class TestCinemaAdminPermissions:
    def test_anon_unauthorized(self, api_client):
        assert api_client.get("/api/v1/admin/movies/").status_code == 401

    def test_non_staff_forbidden(self, auth_client):
        assert auth_client(UserFactory()).get("/api/v1/admin/movies/").status_code == 403

    def test_staff_can_list(self, auth_client):
        assert (
            auth_client(UserFactory(is_staff=True)).get("/api/v1/admin/movies/").status_code == 200
        )


class TestCinemaAdminCrud:
    def test_create_genre(self, auth_client):
        resp = auth_client(UserFactory(is_staff=True)).post(
            "/api/v1/admin/genres/", {"name": "Noir"}, format="json"
        )
        assert resp.status_code == 201
        assert resp.data["name"] == "Noir"

    def test_patch_movie_genres(self, auth_client):
        movie = MovieFactory()
        genre = GenreFactory(name="Thriller")
        resp = auth_client(UserFactory(is_staff=True)).patch(
            f"/api/v1/admin/movies/{movie.id}/", {"genres": [genre.id]}, format="json"
        )
        assert resp.status_code == 200
        assert list(movie.genres.values_list("id", flat=True)) == [genre.id]

    def test_create_and_delete_screening(self, auth_client):
        client = auth_client(UserFactory(is_staff=True))
        movie = MovieFactory()
        hall = HallFactory()
        start = (timezone.now() + timedelta(days=5)).isoformat()
        created = client.post(
            "/api/v1/admin/screenings/",
            {"movie": movie.id, "hall": hall.id, "start_time": start, "price": "30.00"},
            format="json",
        )
        assert created.status_code == 201
        deleted = client.delete(f"/api/v1/admin/screenings/{created.data['id']}/")
        assert deleted.status_code == 204


class TestCinemaAdminImageUpload:
    def test_valid_png_accepted(self, auth_client, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path  # isolate the uploaded file from the repo's media/
        resp = auth_client(UserFactory(is_staff=True)).post(
            "/api/v1/admin/actors/",
            {"full_name": "Keanu Reeves", "photo": _image("PNG")},
            format="multipart",
        )
        assert resp.status_code == 201
        assert resp.data["photo"]

    def test_wrong_format_rejected(self, auth_client):
        resp = auth_client(UserFactory(is_staff=True)).post(
            "/api/v1/admin/actors/",
            {"full_name": "Bad Photo", "photo": _image("GIF")},
            format="multipart",
        )
        assert resp.status_code == 400
        assert "photo" in resp.data


class TestAdminCinemaQueryBudget:
    def test_movie_list_is_bounded(self, auth_client, django_assert_max_num_queries):
        for _ in range(8):
            MovieFactory(
                genres=[GenreFactory()], actors=[ActorFactory()], directors=[DirectorFactory()]
            )
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(10):
            resp = client.get("/api/v1/admin/movies/")
        assert resp.status_code == 200
        assert resp.data["count"] == 8

    def test_movie_detail_is_bounded(self, auth_client, django_assert_max_num_queries):
        movie = MovieFactory(
            genres=[GenreFactory() for _ in range(4)],
            actors=[ActorFactory() for _ in range(4)],
            directors=[DirectorFactory() for _ in range(4)],
        )
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(9):
            resp = client.get(f"/api/v1/admin/movies/{movie.id}/")
        assert resp.status_code == 200

    def test_screening_list_is_bounded(self, auth_client, django_assert_max_num_queries):
        for _ in range(8):
            ScreeningFactory()
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(8):
            resp = client.get("/api/v1/admin/screenings/")
        assert resp.status_code == 200
        assert resp.data["count"] == 8

    def test_screening_detail_is_bounded(self, auth_client, django_assert_max_num_queries):
        screening = ScreeningFactory()
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(7):
            resp = client.get(f"/api/v1/admin/screenings/{screening.id}/")
        assert resp.status_code == 200
