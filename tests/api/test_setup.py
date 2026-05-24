import pytest

from tests.accounts.factories import UserFactory


def test_schema_endpoint(api_client):
    resp = api_client.get("/api/v1/schema/?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["info"]["title"] == "KinoMania API"
    assert data["openapi"].startswith("3.1")


def test_swagger_ui(api_client):
    resp = api_client.get("/api/v1/docs/")
    assert resp.status_code == 200
    assert b"swagger" in resp.content.lower()


def test_redoc(api_client):
    resp = api_client.get("/api/v1/redoc/")
    assert resp.status_code == 200
    assert b"redoc" in resp.content.lower()


@pytest.mark.django_db
def test_auth_client_mints_bearer_token(auth_client):
    client = auth_client(UserFactory())
    auth_header = client._credentials["HTTP_AUTHORIZATION"]
    assert auth_header.startswith("Bearer ")


def test_schema_exposes_jwt_bearer_scheme(api_client):
    data = api_client.get("/api/v1/schema/?format=json").json()
    schemes = data["components"]["securitySchemes"]
    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemes.values())
