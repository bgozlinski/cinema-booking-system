import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_languages_setting():
    codes = {code for code, _label in settings.LANGUAGES}
    assert codes == {"pl", "en"}  # our restricted set, not Django's full default list


def test_default_language_polish(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Repertuar" in resp.content  # pl falls back to the Polish msgid


def test_switcher_rendered(client):
    resp = client.get("/")
    content = resp.content.decode()
    assert reverse("set_language") in content  # /i18n/setlang/
    assert 'value="pl"' in content
    assert 'value="en"' in content


def test_switch_to_english(client):
    resp = client.post(reverse("set_language"), {"language": "en", "next": "/"})
    assert resp.status_code == 302
    home = client.get("/")
    # Navbar "Repertuar" -> "Now Showing" (needs the compiled en .mo). We assert the
    # translated string is present rather than "Repertuar" absent — the page body has other
    # not-yet-translated Polish (that's US-38), so an absence check would be brittle.
    assert b"Now Showing" in home.content
