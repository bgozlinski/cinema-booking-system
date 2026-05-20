import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_login_template_still_renders(client):
    response = client.get("/accounts/login/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "<nav" in content
    assert "🎬 KinoMania" in content


@pytest.mark.django_db
def test_register_template_still_renders(client):
    response = client.get("/accounts/register/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "<nav" in content
    assert "🎬 KinoMania" in content


@pytest.mark.django_db
def test_activation_invalid_template_still_renders(client):
    response = client.get("/accounts/activate/invalid/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "<nav" in content
    assert "🎬 KinoMania" in content


@pytest.mark.django_db
def test_resend_template_still_renders(client):
    response = client.get("/accounts/activate/resend/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "<nav" in content
    assert "🎬 KinoMania" in content
