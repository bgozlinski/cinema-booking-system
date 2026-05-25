# US-37 — i18n setup + language switcher (design)

**Milestone:** M5 — Polish (`v1.0.0`)
**User story:** US-37 — i18n: makemessages/compilemessages + language switcher
**Branch:** `feat/FR-15-i18n-setup`
**FR refs:** FR-15 (i18n PL/EN), §6 (navbar switcher)
**Date:** 2026-05-25
**Type:** mixed — standard Django i18n wiring + one UX decision (switcher).
**Predecessor:** M4 ✅ complete.

---

## 1. Goal

Stand up the i18n machinery end-to-end: settings + `LocaleMiddleware` + `set_language`
endpoint + a navbar language switcher, and prove it by translating a **demonstrable slice**
(the navbar) into English. Exhaustive string translation is US-38.

**Definition of done:**
1. Default Polish; switching to English via the navbar switcher flips the navbar strings and
   persists (cookie/session).
2. `makemessages`/`compilemessages` pipeline works; `locale/{pl,en}/LC_MESSAGES/` exist.
3. The `set_language` POST flow round-trips and stays on the current page (`next`).

## 2. Scope boundary

**In scope:** settings (`LANGUAGES`, `LOCALE_PATHS`, `LocaleMiddleware`), the `i18n/` URL, the
navbar switcher, `{% trans %}` on the **navbar strings only**, the `en` translations for that
slice, compiled `.mo`, and tests.

**Out of scope:** exhaustive string marking/translation across models/forms/all
templates/messages → **US-38**; error pages → US-39; `i18n_patterns` on URLs (FR-15: URLs
stay English, only content is translated).

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Switcher UX | `<select name="language">` (PL/EN) in a POST form, **auto-submit** via inline `onchange="this.form.submit()"`; hidden `next = request.get_full_path`. |
| Marking slice | **Navbar only** in US-37 (proves the pipeline); the rest is US-38. |
| `.mo` in git | **Committed** (not gitignored) — CI/tests get the compiled English catalog with no `compilemessages`/gettext step on the runner. |
| `pl` catalog | `msgstr` left empty — source strings are Polish, so Django falls back to the msgid for `pl`. Only `en` gets real translations. |
| URLs | Not translated (`i18n_patterns` unused) — FR-15. |

## 4. Settings (`settings/base.py`)

- Add `from django.utils.translation import gettext_lazy as _` (top of file).
- `LANGUAGES = [("pl", _("Polski")), ("en", _("English"))]`
- `LOCALE_PATHS = [BASE_DIR / "locale"]`
- `MIDDLEWARE`: insert `"django.middleware.locale.LocaleMiddleware"` **after**
  `SessionMiddleware`, **before** `CommonMiddleware` (Django's required ordering).
- `USE_I18N = True` and `LANGUAGE_CODE = "pl"` are already configured (no change).

## 5. URL (`settings/urls.py`)

Add `path("i18n/", include("django.conf.urls.i18n"))` to `urlpatterns` → provides
`set_language` at `/i18n/setlang/` (URL name `set_language`).

## 6. `templates/base.html` (the demonstrable slice)

- `{% load i18n %}` at the top (after `{% load static %}`).
- `{% get_current_language as LANGUAGE_CODE %}`; `<html lang="{{ LANGUAGE_CODE }}">`
  (was hardcoded `lang="pl"`).
- Wrap the navbar strings in `{% trans %}` — **one tag per line** (PyCharm hard-wrap breaks
  `{% %}`, dev pitfall #6): `Repertuar`, `Seanse`, `Moje rezerwacje`, `Wyloguj`, `Zaloguj`,
  `Zarejestruj`.
- **Language switcher** in the right-side `ul` (before/after the auth links):
  ```html
  <li class="nav-item ms-lg-2">
    <form method="post" action="{% url 'set_language' %}" class="d-inline">
      {% csrf_token %}
      <input type="hidden" name="next" value="{{ request.get_full_path }}">
      <select name="language" onchange="this.form.submit()"
              class="form-select form-select-sm" aria-label="{% trans 'Język' %}">
        <option value="pl" {% if LANGUAGE_CODE == 'pl' %}selected{% endif %}>PL</option>
        <option value="en" {% if LANGUAGE_CODE == 'en' %}selected{% endif %}>EN</option>
      </select>
    </form>
  </li>
  ```

## 7. Locale files

- `python manage.py makemessages -l en -l pl --ignore=.venv` → `locale/pl/LC_MESSAGES/django.po`
  + `locale/en/LC_MESSAGES/django.po` (containing the navbar msgids).
- Fill **`en/django.po`** msgstrs (apostrophe-free, to avoid HTML-escaping fragility in the
  test): `Repertuar`→"Now Showing", `Seanse`→"Screenings", `Moje rezerwacje`→"My Bookings",
  `Wyloguj`→"Log out", `Zaloguj`→"Log in", `Zarejestruj`→"Sign up", `Polski`→"Polish",
  `English`→"English", `Język`→"Language".
  Leave `pl/django.po` msgstrs empty (msgid fallback).
- `python manage.py compilemessages` → `.mo` files (commit them).

**Execution prerequisite:** `makemessages`/`compilemessages` need the gettext tools
(`xgettext`/`msgfmt`) on PATH — install before these steps (the #1 M5 risk on Windows).

## 8. Testing (Claude writes — `tests/test_i18n.py`)

`@pytest.mark.django_db` where the request hits the DB (movie list query on `/`).
- **`test_default_language_polish`** — `GET /` → response contains "Repertuar".
- **`test_switch_to_english`** — `POST /i18n/setlang/ {language: "en", next: "/"}` → 302;
  re-`GET /` → response contains "Now Showing" (proves the switch + the compiled `en`
  catalog). Uses the test client's cookie persistence.
- **`test_switcher_rendered`** — `GET /` → the navbar contains
  `action="/i18n/setlang/"` (or `reverse("set_language")`) and both PL/EN options.
- **`test_languages_setting`** — `settings.LANGUAGES` has `pl` and `en` (guards the config).

The English-switch test depends on the compiled `en` `.mo` — so it (and CI) require the
committed `.mo`. Locally the engineer must `compilemessages` first.

## 9. Coverage / migration

Small settings/template/locale changes + tests. No `apps/` Python logic added → coverage
threshold unaffected. **No migration.**

## 10. Risks

1. **gettext tools on Windows** (#1 M5 risk) — `makemessages`/`compilemessages` need
   `xgettext`/`msgfmt`. Install + verify before §7. Doesn't block this spec/plan.
2. **PyCharm hard-wrap** breaks `{% trans %}` tags (dev pitfall #6) — keep them single-line.
3. **`.mo` must be present for the English test/CI** — committing `.mo` (§3) handles this;
   if a teammate edits `.po` they must re-`compilemessages`.
4. **`LocaleMiddleware` ordering** — must sit after Session, before Common, or language
   detection misbehaves.
5. **Decimal/TZ formatting in i18n tests** (dev pitfalls #4/#5) — assert on translated UI
   strings, not locale-formatted numbers/dates.

## 11. Build order (for the plan)

1. Settings (`LANGUAGES`/`LOCALE_PATHS`/`LocaleMiddleware`) + `i18n/` URL.
2. `base.html`: `{% load i18n %}`, `lang`, navbar `{% trans %}`, switcher.
3. `makemessages` → translate `en` slice → `compilemessages` (needs gettext).
4. Tests (`tests/test_i18n.py`): default PL, switch EN, switcher rendered, LANGUAGES.
5. Quality gate (pytest cov ≥ 80%, ruff, mypy).

First branch commit folds in the untracked `.Claude/m5_planning.md` (like `m4_planning.md`
did for US-29).
