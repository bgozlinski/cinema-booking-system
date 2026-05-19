import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_home_view_returns_200(client):
    response = client.get("/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_home_view_uses_correct_template(client):
    response = client.get("/")

    template_names = [t.name for t in response.templates if t.name]
    assert "cinema/home.html" in template_names
    assert "base.html" in template_names
