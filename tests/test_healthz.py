"""Deploy smoke-check probe: /healthz must report DB-backed liveness."""

import pytest


@pytest.mark.django_db
def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
