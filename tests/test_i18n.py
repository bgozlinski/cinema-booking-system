import re

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import ngettext


def test_languages_setting():
    codes = {code for code, _label in settings.LANGUAGES}
    assert codes == {"pl", "en"}  # our restricted set, not Django's full default list


@pytest.mark.django_db
def test_default_language_polish(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Repertuar" in resp.content  # pl falls back to the Polish msgid


@pytest.mark.django_db
def test_switcher_rendered(client):
    resp = client.get("/")
    content = resp.content.decode()
    assert reverse("set_language") in content  # /i18n/setlang/
    assert 'value="pl"' in content
    assert 'value="en"' in content


@pytest.mark.django_db
def test_switch_to_english(client):
    resp = client.post(reverse("set_language"), {"language": "en", "next": "/"})
    assert resp.status_code == 302
    home = client.get("/")
    # Navbar "Repertuar" -> "Now Showing" (needs the compiled en .mo). We assert the
    # translated string is present rather than "Repertuar" absent — the page body has other
    # not-yet-translated Polish (that's US-38), so an absence check would be brittle.
    assert b"Now Showing" in home.content


# --- US-38: exhaustive-translation guards ---------------------------------------------------


def _po_blocks(path):
    """Yield raw line-lists for each entry in a .po file (entries are blank-line separated)."""
    raw = path.read_text(encoding="utf-8")
    for chunk in raw.split("\n\n"):
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if lines:
            yield lines


def _msgstr_empty(lines, idx):
    """True if the msgstr starting at lines[idx] (incl. multi-line continuation) is empty."""
    m = re.match(r'^msgstr(?:\[\d+\])? "(.*)"$', lines[idx])
    if m and m.group(1):
        return False
    j = idx + 1
    while j < len(lines) and lines[j].startswith('"'):
        if lines[j].strip('"'):
            return False
        j += 1
    return True


def test_en_catalog_has_no_empty_msgstr():
    """Approach-C gate: every en entry is translated and non-fuzzy.

    Goes red the moment `makemessages` extracts a new string that isn't translated yet, so a
    future template/view that forgets a translation fails CI.
    """
    po = settings.BASE_DIR / "locale" / "en" / "LC_MESSAGES" / "django.po"
    assert po.exists(), "run makemessages + translate the en catalog"
    problems = []
    for lines in _po_blocks(po):
        # The header entry has an empty msgid (msgid ""); skip it (comment/`#, fuzzy` lines may
        # precede the msgid line in a freshly generated catalog, so find the msgid explicitly).
        msgid_line = next((ln for ln in lines if ln.startswith("msgid ")), "")
        is_header = msgid_line.strip() == 'msgid ""' and not any(
            ln.startswith("msgid_plural") for ln in lines
        )
        if is_header:
            continue
        if any(ln.startswith("#,") and "fuzzy" in ln for ln in lines):
            problems.append(("fuzzy", msgid_line))
            continue
        for idx, ln in enumerate(lines):
            if ln.startswith("msgstr") and _msgstr_empty(lines, idx):
                problems.append(("empty", msgid_line))
                break
    assert not problems, f"untranslated/fuzzy en entries: {problems}"


def test_seat_count_plural_display():
    """Seat-count blocktrans: EN has 2 forms, PL has 3 (guards the pl plural fill)."""
    singular, plural = "%(counter)s miejsce", "%(counter)s miejsc"
    with translation.override("en"):
        assert ngettext(singular, plural, 1) % {"counter": 1} == "1 seat"
        assert ngettext(singular, plural, 2) % {"counter": 2} == "2 seats"
        assert ngettext(singular, plural, 5) % {"counter": 5} == "5 seats"
    with translation.override("pl"):
        assert ngettext(singular, plural, 1) % {"counter": 1} == "1 miejsce"
        assert ngettext(singular, plural, 2) % {"counter": 2} == "2 miejsca"
        assert ngettext(singular, plural, 5) % {"counter": 5} == "5 miejsc"


@pytest.mark.django_db
def test_catalog_page_translated_en(client):
    """A real public page renders US-38 strings in English after switching to en."""
    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    body = client.get("/").content.decode()
    assert "Now Showing" in body  # navbar (US-37)
    assert "Search" in body  # filter label (US-38)
    assert "Filter" in body  # filter button (US-38)
    assert "Szukaj" not in body  # Polish source no longer leaking on this page
