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


@pytest.mark.django_db
def test_home_view_shows_hero_for_anon(client):
    response = client.get("/")
    content = response.content.decode()

    assert "Witaj w KinoMania" in content
    assert "Zaloguj się" in content
    # Hero CTA links to login
    assert 'href="/accounts/login/"' in content


@pytest.mark.django_db
def test_home_view_shows_user_greeting_when_authenticated(client):
    from tests.accounts.factories import UserFactory

    user = UserFactory(email="hero.test@example.com")
    client.force_login(user)

    response = client.get("/")
    content = response.content.decode()

    # Hero shows the user's email (greeting) when logged in
    assert "hero.test@example.com" in content
    # Hero CTA is replaced by greeting — no "Zaloguj się" button in the hero
    # (The navbar still has its own login/logout state, which is tested separately.)
    # Use the hero region marker to scope the assertion:
    hero_start = content.find("Witaj w KinoMania")
    hero_end = content.find("</section>", hero_start)
    assert hero_start != -1
    assert hero_end != -1
    hero_html = content[hero_start:hero_end]
    assert "Zaloguj się" not in hero_html
