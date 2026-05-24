import pytest

from tests.accounts.factories import UserFactory
from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    HallFactory,
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
