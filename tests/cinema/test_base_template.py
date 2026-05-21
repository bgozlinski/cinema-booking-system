import re

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_navbar_repertuar_links_to_home(client):
    response = client.get("/")
    content = response.content.decode()

    match = re.search(r"<a[^>]*>\s*Repertuar\s*</a>", content)
    assert match is not None, "Repertuar nav anchor not found"
    anchor = match.group(0)
    assert 'href="/"' in anchor, f"Repertuar should link to /, got: {anchor}"
    assert "disabled" not in anchor, f"Repertuar should not be disabled, got: {anchor}"


@pytest.mark.django_db
def test_navbar_seanse_links_to_screening_list(client):
    response = client.get("/")
    content = response.content.decode()

    match = re.search(r"<a[^>]*>\s*Seanse\s*</a>", content)
    assert match is not None, "Seanse nav anchor not found"
    anchor = match.group(0)
    assert 'href="/screenings/"' in anchor, f"Seanse should link to /screenings/, got: {anchor}"
    assert "disabled" not in anchor, f"Seanse should not be disabled, got: {anchor}"


@pytest.mark.django_db
def test_base_template_includes_navbar(client):
    response = client.get("/")
    content = response.content.decode()

    assert "<nav" in content
    assert "🎬 KinoMania" in content


@pytest.mark.django_db
def test_base_template_includes_footer(client):
    response = client.get("/")
    content = response.content.decode()

    assert "© 2026 KinoMania" in content
    assert "projekt edukacyjny" in content


@pytest.mark.django_db
def test_navbar_shows_login_for_anon(client):
    response = client.get("/")
    content = response.content.decode()

    assert "Zaloguj" in content
    assert "Zarejestruj" in content
    assert 'action="/accounts/logout/"' not in content


@pytest.mark.django_db
def test_navbar_shows_logout_for_authenticated(client):
    from tests.accounts.factories import UserFactory

    user = UserFactory(email="navbar.test@example.com")
    client.force_login(user)

    response = client.get("/")
    content = response.content.decode()

    assert "navbar.test@example.com" in content
    assert "Wyloguj" in content
    assert 'action="/accounts/logout/"' in content
    assert ">Zaloguj<" not in content
