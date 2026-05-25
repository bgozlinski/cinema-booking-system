# US-39 — custom 403/404/500 pages + flash polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Django's default error responses with themed, translated 403/404/500 pages, and fix + polish flash-message rendering (error→danger styling + per-level icons).

**Architecture:** A shared `errors/_error_base.html` (extends `base.html`) backs `404.html`/`403.html`; `500.html` is standalone (the `handler500` renders with no request/context). Django's default handlers auto-discover the root templates — no handler wiring. One settings line maps the `error` message level to Bootstrap `danger`; the `base.html` messages block gains per-level icons.

**Tech Stack:** Django default error handlers + templates, `MESSAGE_TAGS`, Django i18n (`{% trans %}`), pytest / pytest-django (`@override_settings(DEBUG=False)`).

---

## Role division

- **User** writes app files (`templates/**`, `settings/*.py`, `locale/**`) and runs all `git`/`pytest`/`manage.py` commands.
- **Claude** writes all test code (`tests/**`).

## Spec

`docs/superpowers/specs/2026-05-25-us39-error-pages-design.md`

## File structure

| File | Action | Responsibility | Author |
|------|--------|----------------|--------|
| `tests/test_error_pages.py` | create | 404/403/500 render + flash error→danger+icon | Claude |
| `templates/errors/_error_base.html` | create | shared error shell (extends base.html) + home CTA | User |
| `templates/404.html` | create | extends `_error_base` | User |
| `templates/403.html` | create | extends `_error_base` | User |
| `templates/500.html` | create | **standalone** minimal themed page | User |
| `settings/base.py` | modify | `MESSAGE_TAGS = {ERROR: "danger"}` | User |
| `templates/base.html` | modify | messages block → `level_tag` class + per-level icon | User |
| `locale/{en,pl}/LC_MESSAGES/django.{po,mo}` | modify | 7 new error strings (en filled, pl empty) | User |
| `.Claude/backlog.md` | modify | status board → US-39 In Progress | User |

No migration. No new Python (Django's default handlers used).

## TDD note

Tests go first (Task 1) and red: 404/403/500 (no templates yet → debug/default response), flash (error renders `alert-error`, no `✗`). Templates + the settings/`base.html` flash edit (Tasks 2–3) turn them green. The error-page text assertions use the **Polish** msgid (default language → msgid fallback), so they pass as soon as the templates exist, before the catalog. Task 4 (catalog) keeps the existing US-38 `test_en_catalog_has_no_empty_msgstr` gate green. Run with `--no-cov` during the loop.

---

### Task 1: Write the error-page + flash tests (red)

**Files:**
- Create: `tests/test_error_pages.py`

- [ ] **Step 1 [Claude]: Write the tests**

Create `tests/test_error_pages.py`:
```python
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import translation
from django.views.defaults import server_error

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
@pytest.mark.django_db
def test_404_renders_custom_template(client):
    resp = client.get("/no-such-url-xyz/")
    assert resp.status_code == 404
    content = resp.content.decode()
    assert "404" in content
    assert "Nie znaleziono strony" in content  # pl default (msgid fallback)


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
@pytest.mark.django_db
def test_403_renders_custom_template(client):
    booking = BookingFactory()  # owned by a fresh user
    client.force_login(UserFactory())  # a different, non-staff user
    resp = client.get(reverse("booking:detail", kwargs={"pk": booking.pk}))
    assert resp.status_code == 403
    assert "Brak dostępu" in resp.content.decode()


def test_500_renders_custom_template():
    # server_error renders 500.html with NO request/context — proves the standalone design.
    with translation.override("pl"):
        resp = server_error(RequestFactory().get("/"))
    assert resp.status_code == 500
    content = resp.content.decode()
    assert "500" in content
    assert "Coś poszło nie tak" in content


def test_error_flash_renders_danger_with_icon():
    # No DB: render base.html directly with an ERROR-level message.
    req = RequestFactory().get("/")
    req.user = AnonymousUser()
    req.resolver_match = SimpleNamespace(url_name="home")
    msg = Message(message_constants.ERROR, "Coś się nie powiodło")
    html = render_to_string("base.html", {"messages": [msg]}, request=req)
    assert "alert-danger" in html  # MESSAGE_TAGS maps ERROR -> danger
    assert "alert-error" not in html  # the old broken class is gone
    assert "✗" in html  # per-level icon
```

- [ ] **Step 2 [User]: Run to confirm FAIL**

Run: `poetry run pytest tests/test_error_pages.py -q --no-cov`
Expected: all 4 FAIL — 404/403/500 render Django's default (no custom template → no "Nie znaleziono strony"/"Brak dostępu"/"Coś poszło nie tak"); flash renders `alert-error` (so `alert-danger`/`✗` absent).

---

### Task 2: Error templates

**Files:**
- Create: `templates/errors/_error_base.html`, `templates/404.html`, `templates/403.html`, `templates/500.html`

> Keep every `{% %}` tag single-line (PyCharm hard-wrap, pitfall #6 — it broke `base.html` in US-38). Parse-check after editing (Task 4 Step 1 or `manage.py shell`).

- [ ] **Step 1 [User]: `templates/errors/_error_base.html`**

```html
{% extends "base.html" %}
{% load i18n %}

{% block content %}
<div class="text-center py-5">
    <p class="display-1 fw-bold mb-2" style="color: var(--accent);">{% block error_code %}{% endblock %}</p>
    <h1 class="h3 mb-3">{% block error_title %}{% endblock %}</h1>
    <p class="text-muted mb-4">{% block error_text %}{% endblock %}</p>
    <a href="/" class="btn btn-primary">{% trans "Wróć na stronę główną" %}</a>
</div>
{% endblock %}
```

- [ ] **Step 2 [User]: `templates/404.html`**

```html
{% extends "errors/_error_base.html" %}
{% load i18n %}
{% block title %}404 — KinoMania{% endblock %}
{% block error_code %}404{% endblock %}
{% block error_title %}{% trans "Nie znaleziono strony" %}{% endblock %}
{% block error_text %}{% trans "Strona, której szukasz, nie istnieje lub została przeniesiona." %}{% endblock %}
```

- [ ] **Step 3 [User]: `templates/403.html`**

```html
{% extends "errors/_error_base.html" %}
{% load i18n %}
{% block title %}403 — KinoMania{% endblock %}
{% block error_code %}403{% endblock %}
{% block error_title %}{% trans "Brak dostępu" %}{% endblock %}
{% block error_text %}{% trans "Nie masz uprawnień, aby zobaczyć tę stronę." %}{% endblock %}
```

- [ ] **Step 4 [User]: `templates/500.html` (standalone — no base.html)**

```html
{% load static i18n %}
{% get_current_language as LANGUAGE_CODE %}
<!DOCTYPE html>
<html lang="{{ LANGUAGE_CODE }}" data-bs-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>500 — KinoMania</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="{% static 'css/theme.css' %}">
</head>
<body class="d-flex flex-column min-vh-100" style="background: var(--bg);">
<main class="container py-5 flex-grow-1 text-center">
    <p class="display-1 fw-bold mb-2" style="color: var(--accent);">500</p>
    <h1 class="h3 mb-3">{% trans "Coś poszło nie tak" %}</h1>
    <p class="text-muted mb-4">{% trans "Wystąpił błąd po naszej stronie. Spróbuj ponownie za chwilę." %}</p>
    <a href="/" class="btn btn-primary">{% trans "Wróć na stronę główną" %}</a>
</main>
</body>
</html>
```

> Why standalone: `django.views.defaults.server_error` renders `500.html` via `template.render()` with **no request and no context processors** — `base.html` needs `request`/`user`/`messages`/`csrf`, which aren't there. `{% static %}`/`{% trans %}`/`{% get_current_language %}` all work without a request.

---

### Task 3: Flash polish (settings + base.html)

**Files:**
- Modify: `settings/base.py`, `templates/base.html`

- [ ] **Step 1 [User]: `settings/base.py` — map ERROR → danger**

Add the import near the top (with the other imports):
```python
from django.contrib.messages import constants as message_constants
```
Add (near the `TEMPLATES`/messages config):
```python
# Bootstrap uses "danger", Django's error level tags as "error" — map it so
# error flashes render with the red alert style.
MESSAGE_TAGS = {message_constants.ERROR: "danger"}
```

- [ ] **Step 2 [User]: `templates/base.html` — messages block**

Replace the existing messages loop (inside `<main>`) with this — note the icon `{% if %}` stays **one line** (PyCharm will try to wrap it; don't let it):
```html
    {% if messages %}
    {% for message in messages %}
    <div class="alert alert-{{ message.level_tag|default:'info' }} alert-dismissible fade show" role="alert">
        <span aria-hidden="true" class="me-1">{% if message.level_tag == 'success' %}✓{% elif message.level_tag == 'danger' %}✗{% elif message.level_tag == 'warning' %}⚠{% else %}ℹ{% endif %}</span>{{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="{% trans 'Zamknij' %}"></button>
    </div>
    {% endfor %}
    {% endif %}
```
(`message.level_tag` respects `MESSAGE_TAGS`, so `error` → `danger`. The project uses no `extra_tags`, so `level_tag` is the right source for the class.)

- [ ] **Step 3 [User]: Run the error+flash tests — should pass (pre-catalog)**

Run: `poetry run pytest tests/test_error_pages.py -q --no-cov`
Expected: 4 passed (Polish msgid fallback makes the title assertions pass without the catalog).

---

### Task 4: Catalog (translate the new strings)

**Files:**
- Modify: `locale/en/LC_MESSAGES/django.{po,mo}`, `locale/pl/LC_MESSAGES/django.{po,mo}`

- [ ] **Step 1 [User]: makemessages**

Run: `poetry run python manage.py makemessages -l en -l pl --no-wrap --ignore=.venv`
Expected: 7 new msgids appear in both `django.po` (the error-page strings; `Zamknij` already exists from US-38).

- [ ] **Step 2 [User]: Translate `en/django.po`**

Fill each new `msgstr` (leave `pl/django.po` empty — Polish source falls back to the msgid). De-fuzz any entry `makemessages` flags `#, fuzzy`:
```
"Wróć na stronę główną"  -> "Back to home"
"Nie znaleziono strony"  -> "Page not found"
"Strona, której szukasz, nie istnieje lub została przeniesiona." -> "The page you're looking for doesn't exist or has moved."
"Brak dostępu"           -> "Access denied"
"Nie masz uprawnień, aby zobaczyć tę stronę." -> "You don't have permission to view this page."
"Coś poszło nie tak"     -> "Something went wrong"
"Wystąpił błąd po naszej stronie. Spróbuj ponownie za chwilę." -> "Something went wrong on our side. Please try again in a moment."
```

- [ ] **Step 3 [User]: compilemessages + verify**

Run: `poetry run python manage.py compilemessages`
Run: `poetry run pytest tests/test_error_pages.py tests/test_i18n.py -q --no-cov`
Expected: all pass — including the US-38 `test_en_catalog_has_no_empty_msgstr` gate (proves the 7 new strings are translated, no empty/fuzzy).

- [ ] **Step 4 [User]: Status board + commit**

In `.Claude/backlog.md` §7, move US-39 to **In Progress** (and US-40 to Ready).
```bash
git add templates/ settings/base.py locale/ tests/test_error_pages.py .Claude/backlog.md
git commit -m "feat(FR-12): custom 403/404/500 pages + flash polish (US-39)"
```
(Spec + plan are committed separately up front as `docs(M5): US-39 error pages spec + plan`.)

---

### Task 5: Quality gate

- [ ] **Step 1 [User]: Full suite with coverage**

Run: `poetry run pytest`
Expected: PASS, coverage ≥ 80%. The error-page tests run under `@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])`; the rest of the suite is unaffected (default Polish render of every page is unchanged — new templates only appear on error responses).

- [ ] **Step 2 [User]: Lint + format + type-check**

Run: `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .`
Expected: clean. (`message_constants` import is used by `MESSAGE_TAGS`; `locale/` is ruff-excluded.)

- [ ] **Step 3 [User]: Manual smoke (optional)**

Temporarily set `DEBUG=False` (+ ensure `ALLOWED_HOSTS` has your host) and `runserver`: hit an unknown URL → themed 404 with navbar + "back to home"; hit another user's booking → 403; switch language → error pages render EN. Flash an error (e.g. cancel a non-cancellable booking) → red `alert-danger` with `✗`.

---

## Out of scope

Auto-dismiss/toast JS · other status codes (400/405) · custom handler functions · real static serving / deployment.

## Test plan summary

- `tests/test_error_pages.py` (new): 404 (unknown URL), 403 (reuse US-21 cross-user booking), 500 (`server_error()` direct — no-context render), flash (`error` → `alert-danger` + `✗`, DB-free `base.html` render). 404/403 need `DEBUG=False` + `ALLOWED_HOSTS=["testserver"]`.
- `tests/test_i18n.py::test_en_catalog_has_no_empty_msgstr` (existing) gates the 7 new strings.
- Coverage ≥ 80% (templates + 1 settings line; no new app logic); no migration.

## Risks (from spec §9)

1. **500 has no context** → standalone template; the `server_error()` test proves it.
2. **`DEBUG=False` test host** → `ALLOWED_HOSTS=["testserver"]` or 400 `DisallowedHost`.
3. **`DEBUG=False` static** → `<link>` 404s in tests; harmless (assert on text, not CSS).
4. **PyCharm hard-wrap** → single-line `{% %}` tags; parse-check templates.
5. **en-coverage gate** → forgetting a translation fails the suite (gate working as intended).
