# Baseline Templates Extract + Home View Implementation Plan (US-09 — M1 final)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py`, `.html`, settings edits, template moves); **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App/template code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Extract Bootstrap 5 baseline from `apps/accounts/templates/accounts/_base.html` to a global `templates/base.html`, move ALL templates (accounts HTML + emails + new cinema) under the global `templates/<app>/` namespace, and add a home view at `/` rendering a hero + 3 "coming soon" cards. Closes US-09 and completes M1 (9/9 US).

**Architecture:** Global `templates/` dir at repo root, `TEMPLATES.DIRS = [BASE_DIR / "templates"]`. `apps/cinema/` gains `views.py` (HomeView = TemplateView) + `urls.py` (path "" → home). All 6 accounts HTML templates plus emails move to `templates/accounts/`; `accounts/_base.html` is deleted. Repertuar nav link activates (→ `/`); Seanse stays disabled until US-14. Full design in `docs/superpowers/specs/2026-05-20-baseline-templates-and-home-design.md`.

**Tech Stack:** Django 6 templates (DTL), Bootstrap 5 via CDN, pytest-django, factory_boy (`UserFactory` from `tests/accounts/factories.py`).

**Branch:** `feat/M1-baseline-templates` (per backlog US-09, **already created and checked out**).

**Pre-existing working-tree state (CRITICAL — do not redo):** The user has already scaffolded part of the work in the working tree before this plan was written. The following changes exist locally, uncommitted:
- `settings/base.py` — `TEMPLATES.DIRS = [BASE_DIR / "templates"]` already set
- `settings/urls.py` — `path("", include("apps.cinema.urls", namespace="cinema"))` already added
- `apps/cinema/views.py` — `HomeView(TemplateView)` already created (`template_name = "cinema/home.html"`)
- `apps/cinema/urls.py` — `app_name="cinema"`, `path("", HomeView.as_view(), name="home")` already created

Task 1 below bundles this scaffold with the missing `templates/base.html` + stub `templates/cinema/home.html` + backlog DoR into a single initial commit. Do **not** revert the working-tree scaffold; just complete it.

---

## Pre-flight checklist (read these first)

- [ ] `docs/superpowers/specs/2026-05-20-baseline-templates-and-home-design.md` — design decisions
- [ ] `.Claude/backlog.md` US-09 section (around line 246) — current AC list, DoR
- [ ] `.Claude/commit_convention.md` — Conventional Commits with `M1` scope for templates work (no FR-XX prefix for UI/UX baseline)
- [ ] `apps/accounts/templates/accounts/_base.html` — source for the extracted `base.html` (Bootstrap 5 baseline, navbar with disabled Repertuar/Seanse, footer, message alerts)
- [ ] `tests/accounts/factories.py` — `UserFactory` (used in tests requiring authenticated state)
- [ ] `apps/accounts/urls.py` — existing accounts URL patterns (referenced in regression tests)
- [ ] Confirm pre-existing working-tree state (above): `git status` should show the four scaffold files modified/created, no commits yet on the branch beyond `main`.

---

## File structure (what we'll create/modify/move/delete)

```
templates/                                              ★ NEW global dir
├── base.html                                           ★ NEW (Task 1, refined in Task 3)
├── cinema/
│   └── home.html                                       ★ NEW (Task 1 stub, fleshed out in Tasks 7-8)
└── accounts/                                           ★ MOVED here from apps/accounts/templates/accounts/ (Task 6)
    ├── login.html                                      ✎ extends "base.html" (Task 5)
    ├── register.html                                   ✎ extends "base.html" (Task 5)
    ├── activation_invalid.html                         ✎ extends "base.html" (Task 5)
    ├── activation_sent.html                            ✎ extends "base.html" (Task 5)
    ├── resend.html                                     ✎ extends "base.html" (Task 5)
    ├── resend_done.html                                ✎ extends "base.html" (Task 5)
    └── emails/
        ├── activation_subject.txt                      (no content change)
        └── activation_body.txt                         (no content change)

apps/accounts/templates/                                ✗ DELETED entirely (Task 6)
apps/cinema/templates/                                  ✗ NEVER CREATED

apps/cinema/
├── views.py                                            ★ NEW — done in working tree
└── urls.py                                             ★ NEW — done in working tree

settings/
├── base.py                                             ✎ TEMPLATES.DIRS — done in working tree
└── urls.py                                             ✎ cinema include — done in working tree

tests/cinema/                                           (exists from US-08)
├── test_base_template.py                               ★ NEW (Tasks 2-4)
├── test_home.py                                        ★ NEW (Tasks 2, 7, 8)
└── test_accounts_templates_regression.py               ★ NEW (Task 5)

.Claude/backlog.md                                      ✎ DoR + links (Task 1), status board (Task 10)
memory/project_kinomania_bootstrap.md                   ✎ after merge — M1 complete (Task 10)
```

---

## Task 1: Bundle the working-tree scaffold + create stub `base.html` and `home.html`

**Files:**
- Already in working tree: `settings/base.py`, `settings/urls.py`, `apps/cinema/views.py`, `apps/cinema/urls.py`
- Create: `templates/base.html` (full Bootstrap 5 baseline — verbatim copy of `apps/accounts/templates/accounts/_base.html`, **Repertuar link unchanged for now**)
- Create: `templates/cinema/home.html` (stub: extends base, `<h1>Home</h1>` content)
- Modify: `.Claude/backlog.md` (US-09 DoR + spec/plan links)

**Why first:** All subsequent tests assume HomeView returns 200. That requires both templates exist. We bundle the working-tree scaffold + the two missing templates + the docs update into ONE commit so the branch's first commit is self-contained ("scaffold + stub").

- [ ] **Step 1: Verify the working-tree scaffold**

```bash
git status
```

Expected output should include:
```
On branch feat/M1-baseline-templates
Changes not staged for commit:
        modified:   settings/base.py
        modified:   settings/urls.py
Untracked files:
        apps/cinema/urls.py
        apps/cinema/views.py
```

If the branch isn't checked out:
```bash
git checkout feat/M1-baseline-templates 2>/dev/null || git checkout -b feat/M1-baseline-templates
```

- [ ] **Step 2: Create `templates/` directory and `templates/cinema/` subdirectory**

Run (Git Bash):
```bash
mkdir -p templates/cinema
```

- [ ] **Step 3: Create `templates/base.html` (reference implementation — user types this)**

Copy the **exact content** of `apps/accounts/templates/accounts/_base.html` into `templates/base.html`. Do NOT modify anything yet — Repertuar/Seanse stay `disabled href="#"`, brand stays `href="/"`, footer/scripts/messages all identical. This is a verbatim copy.

Reference (current `_base.html` content for clarity — paste this into the new file, but type it through PyCharm so the user controls formatting):

```html
{% load static %}
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}KinoMania{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="d-flex flex-column min-vh-100">

<nav class="navbar navbar-expand-lg bg-dark navbar-dark">
    <div class="container">
        <a class="navbar-brand fw-bold" href="/">🎬 KinoMania</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMain">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navMain">
            <ul class="navbar-nav me-auto">
                <li class="nav-item"><a class="nav-link disabled" href="#">Repertuar</a></li>
                <li class="nav-item"><a class="nav-link disabled" href="#">Seanse</a></li>
            </ul>
            <ul class="navbar-nav">
                {% if user.is_authenticated %}
                <li class="nav-item"><span class="navbar-text me-3">{{ user.email }}</span></li>
                <li class="nav-item">
                    <form method="post" action="{% url 'accounts:logout' %}" class="d-inline">
                        {% csrf_token %}
                        <button type="submit" class="btn btn-outline-light btn-sm">Wyloguj</button>
                    </form>
                </li>
                {% else %}
                <li class="nav-item"><a class="nav-link" href="{% url 'accounts:login' %}">Zaloguj</a></li>
                <li class="nav-item"><a class="nav-link" href="{% url 'accounts:register' %}">Zarejestruj</a></li>
                {% endif %}
            </ul>
        </div>
    </div>
</nav>

<main class="container py-4 flex-grow-1">
    {% if messages %}
    {% for message in messages %}
    <div class="alert alert-{{ message.tags|default:'info' }} alert-dismissible fade show" role="alert">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
    {% endfor %}
    {% endif %}
    {% block content %}{% endblock %}
</main>

<footer class="bg-light text-muted py-3 mt-auto">
    <div class="container text-center small">
        © 2026 KinoMania · projekt edukacyjny
    </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create `templates/cinema/home.html` (stub — reference for user)**

```html
{% extends "base.html" %}

{% block title %}KinoMania — Twoje kino online{% endblock %}

{% block content %}
<h1>Home</h1>
{% endblock %}
```

This is intentionally minimal; Tasks 7-8 add hero + cards under TDD.

- [ ] **Step 5: Update `.Claude/backlog.md` US-09 section**

Around line 261, replace:
```markdown
**DoR:** [ ] story / [ ] AC / [ ] zależności / [ ] szkielet od Claude
```

With:
```markdown
**DoR:** [✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude (spec + plan)
```

Then directly after the **Tests-first** block (around line 269, after the last bullet `test_accounts_templates_still_extend_base_correctly`), add:

```markdown
- **Spec:** [`docs/superpowers/specs/2026-05-20-baseline-templates-and-home-design.md`](../docs/superpowers/specs/2026-05-20-baseline-templates-and-home-design.md)
- **Plan:** [`docs/superpowers/plans/2026-05-20-baseline-templates-and-home.md`](../docs/superpowers/plans/2026-05-20-baseline-templates-and-home.md)
```

Update the status board (§7) — replace the table with:

```markdown
| Status | US |
|---|---|
| **In Progress (WIP=1)** | **US-09** (baseline templates extract + home view) |
| **Ready (DoR ✅)** | _none_ |
| **Backlog** | US-10..US-43 |
| **Done** | **US-01..US-08** ✅✅✅✅✅✅✅✅ |
```

Update milestone-summary line below the table:

```markdown
**Bieżący milestone:** M1 — Foundation (`v0.1.0`). 8/9 US zmergowanych, US-09 in progress (ostatni task M1). Po merge → `v0.1.0` tag + M2 planning.
```

- [ ] **Step 6: Sanity check — Django can find the templates**

```bash
poetry run python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

```bash
poetry run python -c "from django.template.loader import get_template; t = get_template('base.html'); print('base.html OK')"
poetry run python -c "from django.template.loader import get_template; t = get_template('cinema/home.html'); print('cinema/home.html OK')"
```

Both should print "OK".

- [ ] **Step 7: Quick smoke — start runserver and curl `/`**

```bash
poetry run python manage.py runserver 8001 &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/
kill %1 2>/dev/null
```

Expected: `200`. If 500, check that both templates were created in correct locations.

- [ ] **Step 8: Commit the bundled scaffold**

```bash
git add settings/base.py settings/urls.py apps/cinema/views.py apps/cinema/urls.py templates/base.html templates/cinema/home.html .Claude/backlog.md
git commit -m "$(cat <<'EOF'
feat(M1): scaffold global templates/ + HomeView at /

- TEMPLATES.DIRS = [BASE_DIR / "templates"]
- New apps/cinema/views.py (HomeView extends TemplateView)
- New apps/cinema/urls.py (cinema:home → "")
- Wire cinema include in settings/urls.py
- templates/base.html: verbatim copy of accounts/_base.html (Repertuar still
  disabled — activated in Task 3)
- templates/cinema/home.html: minimal stub (hero + cards landed in Tasks 7-8)

Backlog US-09 DoR satisfied; spec + plan linked.
EOF
)"
```

---

## Task 2: Tests for HomeView (regression coverage — green from start)

**Files:**
- Create: `tests/cinema/test_home.py` (first 2 of 5 tests; the other 3 come in Tasks 7-8)

**Why:** HomeView is already returning 200 after Task 1. We formalize the contract before iterating on home.html content. These tests stay green throughout the rest of the plan.

- [ ] **Step 1: Write the first 2 home view tests (Claude — paste verbatim)**

Create `tests/cinema/test_home.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect PASS**

```bash
poetry run pytest tests/cinema/test_home.py -v
```

Expected: 2 PASSED. (Not classic red-first TDD — the implementation already exists from Task 1's bundled scaffold. These tests formalize the existing behavior.)

- [ ] **Step 3: Quality gates**

```bash
poetry run ruff check tests/cinema && poetry run ruff format --check tests/cinema && poetry run mypy tests/cinema
```

Expected: all clean.

- [ ] **Step 4: Commit**

```bash
git add tests/cinema/test_home.py
git commit -m "test(M1): cover HomeView returns 200 and uses base.html"
```

---

## Task 3: Activate the Repertuar nav link (TDD)

**Files:**
- Create: `tests/cinema/test_base_template.py` (first test)
- Modify: `templates/base.html` (Repertuar link)

**Why:** The first behavior change. Repertuar currently `nav-link disabled href="#"`; spec calls for `nav-link href="{% url 'cinema:home' %}"` (no `disabled`). Classic red→green.

- [ ] **Step 1: Write the failing test (Claude — paste verbatim)**

Create `tests/cinema/test_base_template.py`:

```python
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
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
poetry run pytest tests/cinema/test_base_template.py::test_navbar_repertuar_links_to_home -v
```

Expected: FAIL. The current Repertuar anchor is `<a class="nav-link disabled" href="#">Repertuar</a>`.

- [ ] **Step 3: Update `templates/base.html` (reference for user)**

Find the Repertuar `<li>` and change:

```html
<li class="nav-item"><a class="nav-link disabled" href="#">Repertuar</a></li>
```

To:

```html
<li class="nav-item"><a class="nav-link" href="{% url 'cinema:home' %}">Repertuar</a></li>
```

Leave the Seanse line unchanged (`disabled href="#"`) — it activates in US-14.

- [ ] **Step 4: Run test — expect PASS**

```bash
poetry run pytest tests/cinema/test_base_template.py::test_navbar_repertuar_links_to_home -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html tests/cinema/test_base_template.py
git commit -m "feat(M1): activate Repertuar nav link (points to /)"
```

---

## Task 4: Add remaining base.html navbar/footer tests (regression coverage)

**Files:**
- Modify: `tests/cinema/test_base_template.py` (append 4 more tests)

**Why:** The base.html behaviors (navbar brand, footer, auth-aware login/logout) already work from Task 1's verbatim copy. Add tests that formalize the contract and serve as guards during the accounts-template refactor (Tasks 5-6).

- [ ] **Step 1: Append 4 tests (Claude — paste verbatim, append to existing file)**

```python
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
```

- [ ] **Step 2: Run tests — expect PASS**

```bash
poetry run pytest tests/cinema/test_base_template.py -v
```

Expected: 5 PASSED (4 new + 1 from Task 3).

- [ ] **Step 3: Quality gates**

```bash
poetry run ruff check tests/cinema && poetry run ruff format --check tests/cinema && poetry run mypy tests/cinema
```

- [ ] **Step 4: Commit**

```bash
git add tests/cinema/test_base_template.py
git commit -m "test(M1): cover base.html navbar (brand, footer, auth-aware)"
```

---

## Task 5: Refactor 6 accounts templates: extends "accounts/_base.html" → "base.html"

**Files:**
- Create: `tests/cinema/test_accounts_templates_regression.py` (4 tests)
- Modify: 6 templates in `apps/accounts/templates/accounts/`:
  - `login.html`
  - `register.html`
  - `activation_invalid.html`
  - `activation_sent.html`
  - `resend.html`
  - `resend_done.html`

**Why:** Decouple accounts from `accounts/_base.html` so the latter can be deleted in Task 6. Regression tests guard the refactor — they pass BEFORE the edit (current `accounts/_base.html` exists and works) and continue to PASS after (templates extend the global `base.html` which has the same nav).

- [ ] **Step 1: Write regression tests (Claude — paste verbatim)**

Create `tests/cinema/test_accounts_templates_regression.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect PASS (baseline before refactor)**

```bash
poetry run pytest tests/cinema/test_accounts_templates_regression.py -v
```

Expected: 4 PASSED. These pass because the templates currently extend `accounts/_base.html` which still exists and has the same `<nav>` markup.

- [ ] **Step 3: Edit each of 6 accounts templates (reference for user)**

For each file in `apps/accounts/templates/accounts/`:
- `login.html`
- `register.html`
- `activation_invalid.html`
- `activation_sent.html`
- `resend.html`
- `resend_done.html`

Change line 1 from:
```django
{% extends "accounts/_base.html" %}
```

To:
```django
{% extends "base.html" %}
```

No other changes — just the extends statement.

- [ ] **Step 4: Run regression tests + full accounts suite — expect PASS**

```bash
poetry run pytest tests/cinema/test_accounts_templates_regression.py tests/accounts/ -v
```

Expected: 4 + (all existing accounts tests) PASSED. No regressions.

- [ ] **Step 5: Quality gates**

```bash
poetry run ruff check apps/accounts tests/cinema && poetry run ruff format --check apps/accounts tests/cinema && poetry run mypy apps/accounts tests/cinema
```

Expected: all clean. (Note: ruff/mypy don't process `.html`; the gate runs on the test file only.)

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/templates/accounts/ tests/cinema/test_accounts_templates_regression.py
git commit -m "$(cat <<'EOF'
refactor(M1): accounts templates extend global base.html

Decouple six accounts templates (login, register, activation_invalid,
activation_sent, resend, resend_done) from accounts/_base.html. They now
extend the global templates/base.html. accounts/_base.html still exists
on disk but is no longer referenced; it gets deleted in the next commit
along with the physical move to templates/accounts/.

Regression tests in tests/cinema/test_accounts_templates_regression.py
guard the refactor — green before and after the extends switch.
EOF
)"
```

---

## Task 6: Move accounts templates to global `templates/accounts/`

**Files:**
- `git mv` 6 HTML files + `emails/` subdir from `apps/accounts/templates/accounts/` to `templates/accounts/`
- Delete: `apps/accounts/templates/accounts/_base.html`
- Delete (empty dirs): `apps/accounts/templates/accounts/`, `apps/accounts/templates/`

**Why:** Physical move now that nothing references the old location. `accounts/login.html` namespace stays the same — Django finds it via `TEMPLATES.DIRS = [BASE_DIR / "templates"]` looking up `templates/accounts/login.html`.

- [ ] **Step 1: Create destination directory**

```bash
mkdir -p templates/accounts
```

- [ ] **Step 2: Move the 6 HTML templates with `git mv`**

```bash
git mv apps/accounts/templates/accounts/login.html templates/accounts/login.html
git mv apps/accounts/templates/accounts/register.html templates/accounts/register.html
git mv apps/accounts/templates/accounts/activation_invalid.html templates/accounts/activation_invalid.html
git mv apps/accounts/templates/accounts/activation_sent.html templates/accounts/activation_sent.html
git mv apps/accounts/templates/accounts/resend.html templates/accounts/resend.html
git mv apps/accounts/templates/accounts/resend_done.html templates/accounts/resend_done.html
```

- [ ] **Step 3: Move the `emails/` subdirectory**

```bash
git mv apps/accounts/templates/accounts/emails templates/accounts/emails
```

- [ ] **Step 4: Delete `_base.html`**

```bash
git rm apps/accounts/templates/accounts/_base.html
```

- [ ] **Step 5: Clean up now-empty directories**

```bash
rmdir apps/accounts/templates/accounts 2>/dev/null || true
rmdir apps/accounts/templates 2>/dev/null || true
```

If those `rmdir` calls fail because the directories aren't empty, run `ls apps/accounts/templates/accounts/` to see what's left and delete it manually.

- [ ] **Step 6: Verify the layout**

```bash
ls templates/
ls templates/accounts/
ls templates/accounts/emails/
ls -la apps/accounts/ | grep templates  # should produce no output
```

Expected:
- `templates/` contains: `accounts/`, `base.html`, `cinema/`
- `templates/accounts/` contains: 6 HTML files + `emails/` subdir
- `templates/accounts/emails/` contains: `activation_body.txt`, `activation_subject.txt`
- `apps/accounts/templates/` no longer exists

- [ ] **Step 7: Run the full test suite — expect PASS**

```bash
poetry run pytest -v
```

Expected: all tests pass. The accounts regression suite + base template suite + home tests all hit the new template locations transparently (Django's `accounts/login.html` lookup now resolves to `templates/accounts/login.html` via DIRS).

- [ ] **Step 8: Manual smoke — render each accounts page**

```bash
poetry run python manage.py runserver 8001 &
sleep 2
for path in "/" "/accounts/login/" "/accounts/register/" "/accounts/activate/invalid/" "/accounts/activate/resend/" "/accounts/activate/sent/"; do
  echo "$path: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001$path)"
done
kill %1 2>/dev/null
```

Expected: all return `200`.

- [ ] **Step 9: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(M1): move all templates to global templates/ directory

All HTML templates and email templates move from apps/accounts/templates/
to templates/accounts/. accounts/_base.html is deleted (its content lives
in templates/base.html since Task 1). apps/accounts/templates/ subtree
removed entirely.

Lookup names are unchanged (still "accounts/login.html",
"accounts/emails/activation_body.txt", etc.) — TEMPLATES.DIRS picks them up.
APP_DIRS=True stays as harmless no-op.

After this commit: every template in the project lives under the global
templates/ tree; apps/ contains only Python code.
EOF
)"
```

---

## Task 7: Build home.html hero + auth-aware CTA (TDD)

**Files:**
- Modify: `tests/cinema/test_home.py` (append 2 tests)
- Modify: `templates/cinema/home.html` (add hero section)

**Why:** First piece of real home page content. Hero displays welcome + auth-aware CTA. Tests fail against the current stub (`<h1>Home</h1>`); user adds hero to make them pass.

- [ ] **Step 1: Write the 2 hero tests (Claude — paste verbatim, append to test_home.py)**

```python
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
    assert hero_start != -1 and hero_end != -1
    hero_html = content[hero_start:hero_end]
    assert "Zaloguj się" not in hero_html
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
poetry run pytest tests/cinema/test_home.py::test_home_view_shows_hero_for_anon tests/cinema/test_home.py::test_home_view_shows_user_greeting_when_authenticated -v
```

Expected: both FAIL — current `home.html` has only `<h1>Home</h1>`.

- [ ] **Step 3: Update `templates/cinema/home.html` to add hero (reference for user)**

Replace the entire `{% block content %}` body with:

```django
{% block content %}
<section class="bg-primary text-white py-5 rounded mb-4">
  <div class="container text-center">
    <h1 class="display-4 fw-bold">Witaj w KinoMania</h1>
    <p class="lead">Twoje kino online — rezerwuj seanse w kilka kliknięć.</p>
    {% if user.is_authenticated %}
      <p class="mb-0">Zalogowany jako <strong>{{ user.email }}</strong></p>
    {% else %}
      <a href="{% url 'accounts:login' %}" class="btn btn-light btn-lg">Zaloguj się</a>
    {% endif %}
  </div>
</section>
{% endblock %}
```

(Cards row comes in Task 8.)

- [ ] **Step 4: Run tests — expect PASS**

```bash
poetry run pytest tests/cinema/test_home.py -v
```

Expected: 4 PASSED (2 from Task 2 + 2 new). No regressions on other suites.

- [ ] **Step 5: Commit**

```bash
git add templates/cinema/home.html tests/cinema/test_home.py
git commit -m "feat(M1): home view hero with auth-aware CTA"
```

---

## Task 8: Build home.html coming-soon cards (TDD)

**Files:**
- Modify: `tests/cinema/test_home.py` (append 1 test)
- Modify: `templates/cinema/home.html` (add cards row after hero)

**Why:** Three placeholder cards (Repertuar/Seanse/Konto) hint at M2/M3 features. Repertuar/Seanse show a "Wkrótce" badge; Konto is active.

- [ ] **Step 1: Write the cards test (Claude — paste verbatim, append to test_home.py)**

```python
@pytest.mark.django_db
def test_home_view_shows_coming_soon_cards(client):
    response = client.get("/")
    content = response.content.decode()

    # Three card titles
    assert ">Repertuar<" in content
    assert ">Seanse<" in content
    assert ">Konto<" in content
    # Coming-soon badge on Repertuar + Seanse (twice)
    assert content.count("Wkrótce") >= 2
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
poetry run pytest tests/cinema/test_home.py::test_home_view_shows_coming_soon_cards -v
```

Expected: FAIL — no cards in home.html yet.

- [ ] **Step 3: Append cards row to `templates/cinema/home.html` (reference for user)**

After the closing `</section>` of the hero, before `{% endblock %}`, add:

```django
<div class="row row-cols-1 row-cols-md-3 g-4">
  <div class="col">
    <div class="card h-100 opacity-75">
      <div class="card-body">
        <h5 class="card-title">Repertuar</h5>
        <p class="card-text">Pełna lista filmów na ten tydzień.</p>
        <span class="badge bg-secondary">Wkrótce</span>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="card h-100 opacity-75">
      <div class="card-body">
        <h5 class="card-title">Seanse</h5>
        <p class="card-text">Harmonogram dzisiejszych seansów.</p>
        <span class="badge bg-secondary">Wkrótce</span>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="card h-100">
      <div class="card-body">
        <h5 class="card-title">Konto</h5>
        {% if user.is_authenticated %}
          <p class="card-text">Zalogowany jako {{ user.email }}.</p>
          <form method="post" action="{% url 'accounts:logout' %}">
            {% csrf_token %}
            <button type="submit" class="btn btn-outline-primary btn-sm">Wyloguj się</button>
          </form>
        {% else %}
          <p class="card-text">Załóż konto, aby rezerwować seanse.</p>
          <a href="{% url 'accounts:register' %}" class="btn btn-primary btn-sm">Zarejestruj się</a>
          <a href="{% url 'accounts:login' %}" class="btn btn-outline-secondary btn-sm">Zaloguj się</a>
        {% endif %}
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
poetry run pytest tests/cinema/test_home.py -v
```

Expected: 5 PASSED (all home tests).

- [ ] **Step 5: Quality gates**

```bash
poetry run ruff check tests/cinema && poetry run ruff format --check tests/cinema && poetry run mypy tests/cinema
```

- [ ] **Step 6: Commit**

```bash
git add templates/cinema/home.html tests/cinema/test_home.py
git commit -m "feat(M1): home view coming-soon cards (Repertuar, Seanse, Konto)"
```

---

## Task 9: Full project quality gates + manual smoke

**Files:** none modified.

**Why:** Belt-and-suspenders verification before opening PR. Confirms coverage threshold holds globally, all tests pass together, and templates work end-to-end in a real browser.

- [ ] **Step 1: Full pytest with coverage**

```bash
poetry run pytest --cov=apps --cov=tests --cov-report=term-missing
```

Expected:
- All tests pass (accounts + cinema)
- `apps/cinema/views.py` and `apps/cinema/urls.py` at 100% coverage
- Global threshold `--cov-fail-under=80` from CI config still holds (currently we're well above)

- [ ] **Step 2: Project-wide quality gates**

```bash
poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .
```

Expected: all green.

- [ ] **Step 3: Manual smoke — home page end-to-end**

```bash
docker compose up -d db
poetry run python manage.py migrate
poetry run python manage.py seed_db --flush  # ensure clean seed users from US-08
poetry run python manage.py runserver
```

Open in browser:
- `http://localhost:8000/` — verify navbar (Repertuar active → `/`, Seanse still disabled), hero with "Zaloguj się" CTA (anon), 3 cards (Repertuar/Seanse "Wkrótce", Konto with register/login)
- Click "Zaloguj się" in hero → goes to `/accounts/login/`
- Login as `seed.user1@kinomania.local` / `test1234` → redirects to `/` (per `LOGIN_REDIRECT_URL` in settings)
- `/` now shows user email in hero greeting + Konto card with logout button
- Logout from navbar → back to anonymous home
- Verify `/accounts/register/`, `/accounts/activate/resend/` still render with same navbar/footer (regression check that the move worked)

- [ ] **Step 4: Visual regression check (manual)**

Compare home page against the original `_base.html` design (Bootstrap 5 navbar + footer):
- Navbar dark with white text ✓
- "🎬 KinoMania" brand bold ✓
- Auth-aware right-side buttons ✓
- Footer light gray ✓
- Message alerts work (try invalid login to trigger Django messages framework)

- [ ] **Step 5: No commit needed** (verification only).

---

## Task 10: Mark US-09 done, update memory, push, PR

**Files:**
- Modify: `.Claude/backlog.md` (status board §7)
- Modify (after merge — Claude proposes): `memory/project_kinomania_bootstrap.md`

**Why:** Close M1. After this PR merges, the project ships `v0.1.0` and pivots to M2 planning.

- [ ] **Step 1: Update `.Claude/backlog.md` §7 status board**

Replace the table with:

```markdown
| Status | US |
|---|---|
| **In Progress (WIP=1)** | _none_ |
| **Ready (DoR ✅)** | _none_ (M2 planning po release `v0.1.0`) |
| **Backlog** | US-10..US-43 |
| **Done** | **US-01..US-09** ✅✅✅✅✅✅✅✅✅ |
```

Update milestone-summary line:

```markdown
**Bieżący milestone:** M1 — Foundation (`v0.1.0`) **COMPLETE** ✅. Wszystkie 9 US zmergowane. US-09 dostarczyło globalny `templates/` katalog + `HomeView` przy `/` z hero + coming-soon cards. Następny krok: release tag `v0.1.0` + M2 planning (rozpisanie kart US-10..US-17).
```

- [ ] **Step 2: Commit on the feature branch**

```bash
git add .Claude/backlog.md
git commit -m "docs(M1): mark US-09 done, M1 milestone complete"
```

- [ ] **Step 3: Push branch and open PR**

```bash
git push -u origin feat/M1-baseline-templates
gh pr create --title "feat(M1): baseline templates + home view (US-09, M1 complete)" --body "$(cat <<'EOF'
## Summary
- Extracts Bootstrap 5 baseline from `apps/accounts/templates/accounts/_base.html` to a global `templates/base.html`
- Moves ALL templates (6 accounts HTML + 2 email templates + new cinema home) under the global `templates/<app>/` namespace; `apps/<x>/templates/` subtrees deleted
- Adds `HomeView` (`TemplateView`) at `/` with hero + 3 coming-soon cards (Repertuar/Seanse "Wkrótce", Konto auth-aware)
- Activates Repertuar nav link → `/` (Seanse stays disabled until US-14)
- 14 new tests in `tests/cinema/` covering base.html navbar/footer, home view hero/cards, and regression smoke on the 6 moved accounts templates
- Closes **US-09**, completes **M1 Foundation milestone** (9/9 US merged → ready for `v0.1.0` release tag)

## Closes
US-09 (M1)

## Spec & Plan
- `docs/superpowers/specs/2026-05-20-baseline-templates-and-home-design.md`
- `docs/superpowers/plans/2026-05-20-baseline-templates-and-home.md`

## Test plan
- [x] `pytest -v` — all tests pass (cinema + accounts)
- [x] `pytest --cov-fail-under=80` — global coverage threshold holds
- [x] `ruff check . && ruff format --check . && mypy .` — quality gates green
- [x] Manual: `/` renders hero + cards (anon shows Zaloguj CTA; authenticated shows user email + logout)
- [x] Manual: all 6 accounts pages (login/register/activation_*/resend/resend_done) still render with the new global base.html
- [x] Manual: login → redirects to `/`; logout from navbar → back to anonymous home
EOF
)"
```

- [ ] **Step 4: After merge — Claude updates memory**

Claude proposes a single-line edit to `memory/project_kinomania_bootstrap.md`:
- Bump M1 progress: `8/9 → 9/9 US done (M1 complete)`
- Update "Następny task" → "M2 planning (v0.1.0 tag + US-10..US-17 cards)"
- Note structural addition: globalny `templates/` katalog istnieje; wszystkie template'y żyją pod globalną ścieżką; `apps/<x>/templates/` nie używamy.

This is Claude's job per role-division — Claude edits memory directly, user reviews.

---

## Out-of-band notes

- **`APP_DIRS=True` flip:** Spec marks this as out-of-scope. After US-09, no app has a `templates/` subdir, so `APP_DIRS=True` is a vestigial harmless no-op. Don't change in US-09.
- **`LOGIN_REDIRECT_URL = "/"`:** Already set in `settings/base.py` (line 93) — `/` is now a real page, so the redirect works seamlessly after Task 1.
- **Email template names unchanged:** `apps/accounts/emails.py` calls `render_to_string("accounts/emails/activation_body.txt")`. The lookup name doesn't change — only the physical path. Existing `tests/accounts/test_emails.py` covers this without modification.
- **Coverage on `apps/cinema/`:** `views.py` and `urls.py` are simple enough that 100% line coverage falls out for free; `seed_db.py` from US-08 stays at ~96%.
- **Test client `fixture`:** Each `test_*.py` defines a local `client` fixture instead of relying on `pytest-django`'s built-in `client` — matches the pattern used in `tests/accounts/` test files. Could be promoted to `conftest.py` in a future cleanup; out of scope here.
- **Why no `re` import in cards test:** The cards test uses plain substring matching (`">Repertuar<"`) because the structure is stable enough. The Repertuar nav link test needs regex because the brand also has `href="/"` and we need to disambiguate.

---

**Done criteria:** All 14 tests pass. Manual smoke green (anon + authenticated). PR merged. US-09 + M1 ticked in backlog. Memory updated. `v0.1.0` tag ready to cut.
