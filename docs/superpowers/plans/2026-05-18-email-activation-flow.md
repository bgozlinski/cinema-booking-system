# Email Activation Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py` views/forms/models/managers, `.html`, `.js`, `.css`, migrations); **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`, mocks). User runs ALL `git`/`gh` commands. App code shown in this plan is a **reference implementation** for the user to study/adapt while typing — not for an agent to paste. Test code is **complete and ready to paste** by Claude. Subagent-driven execution is NOT compatible with this workflow — use inline execution.

**Goal:** Implement email activation flow for user registration — accounts created via the register form are `is_active=False` until the user clicks an activation link delivered by email. Adds register / login / logout / activate / resend views to satisfy US-07 (FR-06) extended scope.

**Architecture:** Django built-in `default_token_generator` (HMAC, stateless — no new DB tables). Console email backend in dev. Resend endpoint with no enumeration leak. Login uses Django default `ModelBackend` (returns generic "invalid credentials" for inactive accounts). Full design in `docs/superpowers/specs/2026-05-18-email-activation-flow-design.md`.

**Tech Stack:** Django 6 (custom `accounts.User` with `USERNAME_FIELD="email"`), pytest-django, factory_boy, freezegun (new dev dep for expired-token tests). PostgreSQL via Docker Compose locally.

**Branch:** `feat/FR-06-email-auth-flow` (as defined in backlog US-07).

---

## Pre-flight checklist (read these first)

- [ ] `docs/superpowers/specs/2026-05-18-email-activation-flow-design.md` — design decisions
- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §3.1 (User model), §4 (current FR-06)
- [ ] `.Claude/backlog.md` US-07 (current AC list)
- [ ] `.Claude/commit_convention.md` — Conventional Commits with FR-06 scope
- [ ] `apps/accounts/{models,managers,admin}.py` — existing User model from US-06
- [ ] `tests/accounts/factories.py` — current `UserFactory` (routes through `create_user`)

---

## File structure (what we'll create/modify)

```
apps/accounts/
├── urls.py                    ★ NEW — app URLs (register, activate, resend, login, logout)
├── forms.py                   ★ NEW — RegistrationForm, ResendActivationForm
├── views.py                   ★ NEW — 5 views (register, activation_sent, activate, activation_invalid, resend)
├── emails.py                  ★ NEW — send_activation_email() helper
├── models.py                  ─ unchanged
├── managers.py                ─ unchanged
├── admin.py                   ─ unchanged
└── templates/accounts/        ★ NEW directory tree
    ├── register.html
    ├── login.html
    ├── activation_sent.html
    ├── activation_invalid.html
    ├── resend.html
    ├── resend_done.html
    └── emails/
        ├── activation_subject.txt
        └── activation_body.txt

settings/
├── base.py                    ✎ + LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL, DEFAULT_FROM_EMAIL
├── dev.py                     ✎ + EMAIL_BACKEND = console
├── prod.py                    ✎ + SMTP placeholder vars
└── urls.py                    ✎ + include("apps.accounts.urls", namespace="accounts")

tests/accounts/
├── factories.py               ✎ + inactive trait
├── test_registration.py       ★ NEW — register view + form tests
├── test_activation.py         ★ NEW — activation view tests (valid/invalid/expired/already-active)
├── test_resend.py             ★ NEW — resend view tests (no enum leak)
├── test_login.py              ★ NEW — login view tests (active/inactive)
├── test_logout.py             ★ NEW — logout view tests
└── test_emails.py             ★ NEW — send_activation_email() tests

pyproject.toml                 ✎ + freezegun in dev deps
.env.example                   ✎ + DEFAULT_FROM_EMAIL + SMTP placeholders
.Claude/KinoMania_wymagania_funkcjonalne.md   ✎ FR-06 extended
.Claude/backlog.md             ✎ US-07 AC expanded, estymata M → L
memory/project_kinomania_bootstrap.md         ✎ after merge — bump to 7/9 done
```

---

## Task 1: Update FR-06 documentation

**Files:**
- Modify: `.Claude/KinoMania_wymagania_funkcjonalne.md` (FR-06 section)

**Why first:** The functional requirements doc is the source of truth for what "FR-06" means. Spec-first, code-second.

- [ ] **Step 1: Locate the current FR-06 section**

Open `.Claude/KinoMania_wymagania_funkcjonalne.md` and find section `## 4. Funkcjonalności (FR)` → `### FR-06 — Authentication` (or similar — find it by searching for `FR-06`).

- [ ] **Step 2: Replace FR-06 body with the extended version**

Replace the FR-06 block with this content (user-written prose — paraphrase to match doc style, **do NOT copy verbatim**):

```markdown
### FR-06 — Authentication (Login / Logout / Register + Email activation)

**Cel:** Użytkownik tworzy konto przez email + hasło. Konto pozostaje
nieaktywne (`is_active=False`) do momentu kliknięcia linku aktywacyjnego
wysłanego na podany adres email. Po aktywacji może się zalogować.

**Wymagania szczegółowe:**

1. **Rejestracja** — formularz `/accounts/register/` zbiera email +
   hasło (2×). Po POST tworzony jest user z `is_active=False`, generowany
   token (Django `default_token_generator` — HMAC bezstanowy) i wysyłany
   email z absolutnym linkiem aktywacyjnym. User NIE jest auto-zalogowany.
   Po sukcesie → redirect na `/accounts/activate/sent/`.

2. **Aktywacja** — link w mailu prowadzi na
   `/accounts/activate/<uidb64>/<token>/`. Po dekodowaniu uidb64 +
   walidacji tokenu ustawiamy `user.is_active=True`, flash sukces,
   redirect na `/accounts/login/`. Expiry tokenu = `PASSWORD_RESET_TIMEOUT`
   (Django default, 3 dni). Drugi klik linku po aktywacji = flash „już
   aktywne" + redirect na login (idempotent UX).

3. **Resend** — `/accounts/activate/resend/` z polem email. Niezależnie
   od stanu konta (istniejące/nieistniejące/aktywne) widok renderuje
   `resend_done.html` — bez ujawniania czy email jest w bazie. Realnie
   email wysyłany jest tylko dla istniejącego konta z `is_active=False`.

4. **Login** — standardowy `django.contrib.auth.views.LoginView` z
   formularzem na email + hasło. `ModelBackend` automatycznie odrzuca
   `is_active=False` z generic „nieprawidłowe dane logowania" (decyzja
   security-first — bez enumeration leak).

5. **Logout** — `django.contrib.auth.views.LogoutView` (POST only,
   Django 5.x default).

**Wykluczone z M1 (follow-up):** rate limiting na resend
(`django-ratelimit` w M5), dedykowany salt dla activation tokenu
(razem z password reset), HTML email template, tłumaczenia PL/EN treści
maili, realny SMTP w prod.
```

- [ ] **Step 3: Verify no other section references FR-06 in a way that contradicts the extension**

Run: search for "FR-06" across the docs.

```bash
grep -n "FR-06" .Claude/*.md docs/superpowers/specs/*.md
```

If any other place describes FR-06 as "login/logout/register only" (no activation), update it for consistency.

- [ ] **Step 4: Commit**

```bash
git checkout -b feat/FR-06-email-auth-flow
git add .Claude/KinoMania_wymagania_funkcjonalne.md
git commit -m "docs(FR-06): extend functional requirements with email activation flow"
```

---

## Task 2: Update backlog (US-07 AC + estymata)

**Files:**
- Modify: `.Claude/backlog.md` (US-07 card)

- [ ] **Step 1: Replace US-07 AC block with the extended version**

In `.Claude/backlog.md`, replace the US-07 body (everything from `### US-07 —` to before `### US-08 —`) with:

```markdown
### US-07 — Login/Logout/Register flow with email activation (web)
- **FR:** FR-06 | **Branch:** `feat/FR-06-email-auth-flow` | **Estymata:** L
- **Zależy od:** US-06

**Story:**
*Jako użytkownik, chcę zarejestrować się przez email + hasło i potwierdzić
adres przez klik w link aktywacyjny, aby mieć pewność że konto jest
powiązane z moim realnym mailem.*

**Acceptance Criteria (Given/When/Then):**

*Rejestracja:*
- **GIVEN** formularz `/accounts/register/` **WHEN** POST z poprawnym
  emailem + 2× tym samym hasłem **THEN** user utworzony z
  `is_active=False`, email z linkiem aktywacyjnym w `mail.outbox`,
  user NIE zalogowany, redirect na `/accounts/activate/sent/`.
- **GIVEN** próba rejestracji z istniejącym emailem **WHEN** POST
  **THEN** form error przy polu email, status 200, brak nowego usera,
  brak emaila w outboxie.

*Aktywacja:*
- **GIVEN** świeży link aktywacyjny **WHEN** GET
  `/accounts/activate/<uidb64>/<token>/` **THEN** `user.is_active=True`,
  flash sukces, redirect na `/accounts/login/`.
- **GIVEN** link z podrobionym tokenem **WHEN** GET **THEN** redirect
  na `/accounts/activate/invalid/`, user pozostaje `is_active=False`.
- **GIVEN** link starszy niż `PASSWORD_RESET_TIMEOUT` **WHEN** GET
  **THEN** redirect na `/accounts/activate/invalid/`.
- **GIVEN** user już zaktywowany **WHEN** klika link drugi raz
  **THEN** flash „konto już aktywne" + redirect na login (idempotent).

*Resend:*
- **GIVEN** `/accounts/activate/resend/` **WHEN** POST email nieaktywnego
  usera **THEN** nowy email w outboxie, render `resend_done.html`.
- **GIVEN** POST email aktywnego usera **WHEN** **THEN** outbox bez nowych
  maili, render `resend_done.html` (no enum leak).
- **GIVEN** POST email nieistniejącego usera **WHEN** **THEN** outbox bez
  maili, render `resend_done.html` (no enum leak).

*Login/Logout:*
- **GIVEN** active user **WHEN** POST email+password **THEN** sesja
  zalogowana, redirect na `?next=` lub `/`.
- **GIVEN** inactive user z poprawnym hasłem **WHEN** POST **THEN**
  generic „nieprawidłowe dane", brak sesji.
- **GIVEN** zalogowany user **WHEN** POST `/accounts/logout/` **THEN**
  sesja zniszczona, redirect na `/`. GET → 405.

**DoR:** [✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude

**Tests-first (Claude pisze) — `tests/accounts/`:**
- `test_registration.py` — register GET/POST, inactive creation, email
  sent, no auto-login, redirect, walidacje
- `test_activation.py` — valid/invalid/expired/malformed/nonexistent/
  already-active scenarios
- `test_resend.py` — inactive (sends), active (silent), nonexistent
  (silent), always renders `resend_done`
- `test_login.py` — active OK, inactive fails generic, wrong password,
  `?next=` redirect
- `test_logout.py` — POST destroys session, GET 405
- `test_emails.py` — `send_activation_email()` subject/body/from/link
```

- [ ] **Step 2: Update status board (§7) to reflect US-07 in progress**

In §7 (status board), move US-07 from `Ready` to `In Progress`:

```markdown
| **In Progress (WIP=1)** | **US-07** (Login/Logout/Register + email activation) |
| **Ready (DoR ✅)** | _none_ |
```

- [ ] **Step 3: Update §8 estimation table for US-07 size change**

Change M1 row sum from `~6 dni` to `~7 dni` (US-07 went M → L = +0.5 day). Sub-total per US in the table is implicit; if the file shows per-US estimates anywhere, update them.

- [ ] **Step 4: Commit**

```bash
git add .Claude/backlog.md
git commit -m "docs(FR-06): expand US-07 acceptance criteria and tests in backlog"
```

---

## Task 3: Add freezegun + email settings + .env.example

**Files:**
- Modify: `pyproject.toml` (dev-deps)
- Modify: `settings/base.py`
- Modify: `settings/dev.py`
- Modify: `settings/prod.py`
- Modify: `.env.example`

- [ ] **Step 1: Add freezegun to dev dependencies**

Run (user):

```bash
poetry add --group dev freezegun
```

Verify in `pyproject.toml` `[dependency-groups].dev` now contains `"freezegun (>=...)"`.

- [ ] **Step 2: Extend `settings/base.py` with auth URLs + email defaults**

Append to `settings/base.py` (after the `# ─── Auth ───` block):

```python
# ─── Auth URLs ──────────────────────────────────────────────────────────────
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ─── Email ──────────────────────────────────────────────────────────────────
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@kinomania.local")
# Activation tokens use Django's PASSWORD_RESET_TIMEOUT (default 3 days = 259200s).
# No separate setting — single timeout for all token-based auth flows.
```

- [ ] **Step 3: Extend `settings/dev.py` with console email backend**

Append to `settings/dev.py`:

```python
# Emails print to runserver's stdout — copy the activation link from terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

- [ ] **Step 4: Extend `settings/prod.py` with SMTP placeholder**

Replace `settings/prod.py` contents with:

```python
from settings.base import *  # noqa: F401, F403

import environ

env = environ.Env()

DEBUG = False

# SMTP — placeholder, configured per environment via .env.
# Not exercised in M1; real deployment work happens post-M5.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
```

- [ ] **Step 5: Extend `.env.example`**

Append to `.env.example`:

```
DEFAULT_FROM_EMAIL=noreply@kinomania.local
# SMTP — used only by prod settings, placeholder for now
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
```

- [ ] **Step 6: Verify Django still boots**

Run (user):

```bash
poetry run python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml poetry.lock settings/ .env.example
git commit -m "chore(FR-06): add freezegun, configure auth urls and email backend"
```

---

## Task 4: Wire `apps.accounts.urls` into the root URLconf

**Files:**
- Modify: `settings/urls.py`
- Create: `apps/accounts/urls.py` (minimal — will be filled in Task 6)

- [ ] **Step 1: Create a placeholder `apps/accounts/urls.py`**

Create `apps/accounts/urls.py` with **just `app_name`** and an empty list — we'll fill patterns in Task 6 once views exist:

```python
from django.urls import path

app_name = "accounts"

urlpatterns: list = []
```

- [ ] **Step 2: Include in `settings/urls.py`**

Modify `settings/urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
]
```

- [ ] **Step 3: Verify Django boots**

Run (user):

```bash
poetry run python manage.py check
```

Expected: clean check (no issues).

- [ ] **Step 4: Commit**

```bash
git add settings/urls.py apps/accounts/urls.py
git commit -m "feat(FR-06): wire accounts urlconf into the root urls"
```

---

## Task 5: Extend `UserFactory` with `inactive` trait

**Files:**
- Modify: `tests/accounts/factories.py`

**Why:** The activation tests need to create inactive users without manually setting `is_active=False` everywhere. A trait keeps test setups expressive: `UserFactory(inactive=True)`.

- [ ] **Step 1: Add `is_active` default and `inactive` trait**

In `tests/accounts/factories.py`, **before** the `_create` classmethod, add `is_active` as a default factory field and a `Params` inner class with the trait:

```python
class UserFactory(factory.django.DjangoModelFactory):
    """Create ``accounts.User`` instances via the custom manager."""

    class Meta:
        model = get_user_model()
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = "test1234"
    is_active = True

    class Params:
        inactive = factory.Trait(is_active=False)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        is_superuser = kwargs.pop("is_superuser", False)
        manager = cls._get_manager(model_class)
        if is_superuser:
            return manager.create_superuser(*args, **kwargs)
        return manager.create_user(*args, **kwargs)
```

`is_active` rides through `**kwargs` → `UserManager.create_user(**extra_fields)` → `self.model(email=..., is_active=False)`. Works because `User` model has `is_active` as a regular field.

- [ ] **Step 2: Write a test to verify the trait works**

Create `tests/accounts/test_factories.py`:

```python
"""Smoke tests for UserFactory traits."""

from __future__ import annotations

import pytest

from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_user_factory_default_is_active() -> None:
    user = UserFactory()
    assert user.is_active is True


@pytest.mark.django_db
def test_user_factory_inactive_trait_creates_inactive_user() -> None:
    user = UserFactory(inactive=True)
    assert user.is_active is False
    assert user.pk is not None, "user should still be persisted"
```

- [ ] **Step 3: Run tests**

Run (user):

```bash
poetry run pytest tests/accounts/test_factories.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Verify existing US-06 tests still pass (regression check)**

Run:

```bash
poetry run pytest tests/accounts/ -v
```

Expected: all existing tests (test_models.py, test_admin.py) still pass.

- [ ] **Step 5: Commit**

```bash
git add tests/accounts/factories.py tests/accounts/test_factories.py
git commit -m "test(FR-06): add inactive trait to UserFactory"
```

---

## Task 6: Build `send_activation_email()` helper (TDD)

**Files:**
- Test: `tests/accounts/test_emails.py`
- Create: `apps/accounts/emails.py`
- Create: `apps/accounts/templates/accounts/emails/activation_subject.txt`
- Create: `apps/accounts/templates/accounts/emails/activation_body.txt`

**Why isolated helper:** Centralizing email composition in one function gives tests a single mockable seam and keeps views slim.

- [ ] **Step 1: Write failing tests (Claude)**

Create `tests/accounts/test_emails.py`:

```python
"""Tests for the activation email helper (FR-06)."""

from __future__ import annotations

import pytest
from django.core import mail
from django.test import RequestFactory
from django.utils.http import urlsafe_base64_decode

from apps.accounts.emails import send_activation_email
from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_send_activation_email_puts_one_message_in_outbox() -> None:
    user = UserFactory(inactive=True, email="alice@example.com")
    request = RequestFactory().get("/accounts/register/")

    send_activation_email(user, request)

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_send_activation_email_uses_default_from_email(settings) -> None:
    settings.DEFAULT_FROM_EMAIL = "noreply@test.local"
    user = UserFactory(inactive=True, email="alice@example.com")
    request = RequestFactory().get("/accounts/register/")

    send_activation_email(user, request)

    sent = mail.outbox[0]
    assert sent.from_email == "noreply@test.local"
    assert sent.to == ["alice@example.com"]


@pytest.mark.django_db
def test_send_activation_email_subject_is_non_empty_single_line() -> None:
    user = UserFactory(inactive=True)
    request = RequestFactory().get("/")

    send_activation_email(user, request)

    subject = mail.outbox[0].subject
    assert subject, "subject must not be empty"
    assert "\n" not in subject, "subject must be a single line (Django enforces)"


@pytest.mark.django_db
def test_send_activation_email_body_contains_absolute_activation_url() -> None:
    user = UserFactory(inactive=True, email="alice@example.com")
    request = RequestFactory().get("/accounts/register/", HTTP_HOST="testserver")

    send_activation_email(user, request)

    body = mail.outbox[0].body
    # Absolute URL — starts with scheme + host, not just "/accounts/..."
    assert "http://testserver/accounts/activate/" in body, (
        f"Body must contain an absolute activation URL anchored at "
        f"/accounts/activate/<uidb64>/<token>/. Body:\n{body}"
    )


@pytest.mark.django_db
def test_send_activation_email_link_encodes_user_pk() -> None:
    """The uidb64 component must decode back to the user's pk."""
    user = UserFactory(inactive=True)
    request = RequestFactory().get("/", HTTP_HOST="testserver")

    send_activation_email(user, request)

    body = mail.outbox[0].body
    # Extract the path: /accounts/activate/<uidb64>/<token>/
    import re

    match = re.search(r"/accounts/activate/([^/]+)/([^/\s]+)/", body)
    assert match, f"could not find activation link in body:\n{body}"
    uidb64 = match.group(1)
    decoded_pk = urlsafe_base64_decode(uidb64).decode()
    assert int(decoded_pk) == user.pk
```

- [ ] **Step 2: Run tests to verify failure**

Run (user):

```bash
poetry run pytest tests/accounts/test_emails.py -v
```

Expected: All 5 tests fail with `ModuleNotFoundError: No module named 'apps.accounts.emails'`.

- [ ] **Step 3: Create email subject template**

Create `apps/accounts/templates/accounts/emails/activation_subject.txt` (single line, no trailing newline):

```
Aktywuj konto KinoMania
```

- [ ] **Step 4: Create email body template**

Create `apps/accounts/templates/accounts/emails/activation_body.txt`:

```
Cześć!

Aby aktywować konto KinoMania, kliknij w poniższy link:

{{ activation_url }}

Link jest ważny przez 3 dni. Jeśli to nie Ty zakładałeś/aś konto,
po prostu zignoruj tę wiadomość — bez kliknięcia konto pozostanie
nieaktywne.

— Zespół KinoMania
```

- [ ] **Step 5: Implement `send_activation_email` (user writes — reference below)**

Create `apps/accounts/emails.py`:

```python
"""Email composition helpers for the accounts app.

`send_activation_email` is the single seam for activation emails — views call
this; tests mock or inspect `mail.outbox` after it runs.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def send_activation_email(user, request: HttpRequest) -> None:
    """Send an account-activation email to `user`.

    Composes an absolute URL pointing at the `accounts:activate` view,
    using Django's HMAC-based `default_token_generator` (the same one used
    for password reset). The hash includes `is_active` and `password`, so
    once the user activates or changes their password the token auto-invalidates.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    relative_path = reverse(
        "accounts:activate",
        kwargs={"uidb64": uidb64, "token": token},
    )
    activation_url = request.build_absolute_uri(relative_path)

    subject = render_to_string("accounts/emails/activation_subject.txt").strip()
    body = render_to_string(
        "accounts/emails/activation_body.txt",
        context={"activation_url": activation_url, "user": user},
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
```

**Note for user:** the `reverse("accounts:activate", ...)` call requires the URL pattern `activate` to be registered in `apps/accounts/urls.py`. We don't have it yet — tests will fail with `NoReverseMatch`. Don't run tests yet; we add the URL in Task 7.

- [ ] **Step 6: Commit (deferred — runs together with Task 7)**

The email helper depends on URL patterns we haven't added yet. We'll commit emails.py + urls.py + views.py scaffolding together in Task 7 to keep the tree green.

---

## Task 7: Scaffold all 5 views + URL patterns (TemplateView-only versions)

**Files:**
- Create: `apps/accounts/views.py` (full scaffold — empty TemplateView classes for the simple views, stubs for the rest)
- Modify: `apps/accounts/urls.py` (full URL patterns)
- Test: re-run Task 6 tests

**Why all-at-once:** Django needs every URL name resolvable for `reverse()` to work. We scaffold all views (some as `TemplateView`, some as stubs raising `NotImplementedError`) and fill behavior in Tasks 8–12.

- [ ] **Step 1: Create `apps/accounts/views.py` with scaffolding (user writes — reference below)**

```python
"""Views for the accounts app — registration, activation, login, logout, resend.

FR-06: email-only authentication with email activation flow.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, View

User = get_user_model()


class RegisterView(FormView):
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:activation_sent")

    def get_form_class(self):
        from apps.accounts.forms import RegistrationForm
        return RegistrationForm

    def form_valid(self, form):
        from apps.accounts.emails import send_activation_email

        user = form.save(commit=False)
        user.is_active = False
        user.save()
        send_activation_email(user, self.request)
        return super().form_valid(form)


class ActivationSentView(TemplateView):
    template_name = "accounts/activation_sent.html"


class ActivationInvalidView(TemplateView):
    template_name = "accounts/activation_invalid.html"


class ActivateView(View):
    def get(self, request, uidb64: str, token: str):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return redirect("accounts:activation_invalid")

        if user.is_active:
            messages.info(
                request,
                _("Konto jest już aktywne. Możesz się zalogować."),
            )
            return redirect("accounts:login")

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            messages.success(request, _("Konto aktywowane. Zaloguj się."))
            return redirect("accounts:login")

        return redirect("accounts:activation_invalid")


class ResendActivationView(FormView):
    template_name = "accounts/resend.html"
    success_url = reverse_lazy("accounts:activation_resend")  # re-render done page via GET

    def get_form_class(self):
        from apps.accounts.forms import ResendActivationForm
        return ResendActivationForm

    def form_valid(self, form):
        from apps.accounts.emails import send_activation_email

        email = form.cleaned_data["email"]
        try:
            user = User.objects.get(email__iexact=email, is_active=False)
        except User.DoesNotExist:
            user = None
        if user is not None:
            send_activation_email(user, self.request)
        return render(self.request, "accounts/resend_done.html")
```

- [ ] **Step 2: Replace `apps/accounts/urls.py` with full patterns**

```python
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path(
        "activate/sent/",
        views.ActivationSentView.as_view(),
        name="activation_sent",
    ),
    path(
        "activate/invalid/",
        views.ActivationInvalidView.as_view(),
        name="activation_invalid",
    ),
    path(
        "activate/resend/",
        views.ResendActivationView.as_view(),
        name="activation_resend",
    ),
    path(
        "activate/<uidb64>/<token>/",
        views.ActivateView.as_view(),
        name="activate",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
```

- [ ] **Step 3: Verify Django boots (no template/import errors yet)**

Run (user):

```bash
poetry run python manage.py check
```

Expected: clean check. (Templates don't exist yet but `check` doesn't validate template existence — only at render time.)

- [ ] **Step 4: Verify the email helper tests now pass (reverse() works)**

The `reverse("accounts:activate", ...)` in `send_activation_email` now resolves. But the form imports (`apps.accounts.forms`) will fail because we haven't created the forms module yet. The email tests don't import forms — they only call `send_activation_email` directly. Let's see what happens.

Run:

```bash
poetry run pytest tests/accounts/test_emails.py -v
```

Expected: All 5 tests now pass (the `import apps.accounts.forms` only runs when `RegisterView.get_form_class` is called — not at import time).

- [ ] **Step 5: Commit views + URLs + emails together**

```bash
git add apps/accounts/views.py apps/accounts/urls.py apps/accounts/emails.py apps/accounts/templates/
git add tests/accounts/test_emails.py
git commit -m "feat(FR-06): add activation email helper, views scaffold, and url patterns"
```

---

## Task 8: `RegistrationForm` (TDD)

**Files:**
- Test: `tests/accounts/test_forms.py` (new)
- Create: `apps/accounts/forms.py`

- [ ] **Step 1: Write failing tests (Claude)**

Create `tests/accounts/test_forms.py`:

```python
"""Tests for accounts.forms (FR-06)."""

from __future__ import annotations

import pytest

from apps.accounts.forms import RegistrationForm, ResendActivationForm
from tests.accounts.factories import UserFactory


# ─── RegistrationForm ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_registration_form_creates_user_with_email_and_hashed_password() -> None:
    form = RegistrationForm(
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert form.is_valid(), form.errors
    user = form.save()

    assert user.pk is not None
    assert user.email == "newbie@example.com"
    assert user.check_password("Str0ngP@ssw0rd")


@pytest.mark.django_db
def test_registration_form_rejects_mismatched_passwords() -> None:
    form = RegistrationForm(
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "different-pw",
        }
    )

    assert not form.is_valid()
    assert "password2" in form.errors


@pytest.mark.django_db
def test_registration_form_rejects_duplicate_email() -> None:
    UserFactory(email="existing@example.com")

    form = RegistrationForm(
        data={
            "email": "existing@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert not form.is_valid()
    assert "email" in form.errors


@pytest.mark.django_db
def test_registration_form_rejects_invalid_email_syntax() -> None:
    form = RegistrationForm(
        data={
            "email": "not-an-email",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert not form.is_valid()
    assert "email" in form.errors


@pytest.mark.django_db
def test_registration_form_requires_email() -> None:
    form = RegistrationForm(
        data={
            "email": "",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        }
    )

    assert not form.is_valid()
    assert "email" in form.errors


# ─── ResendActivationForm ───────────────────────────────────────────────────


def test_resend_activation_form_valid_with_email() -> None:
    form = ResendActivationForm(data={"email": "anyone@example.com"})
    assert form.is_valid(), form.errors


def test_resend_activation_form_rejects_invalid_email() -> None:
    form = ResendActivationForm(data={"email": "not-an-email"})
    assert not form.is_valid()
    assert "email" in form.errors


def test_resend_activation_form_requires_email() -> None:
    form = ResendActivationForm(data={"email": ""})
    assert not form.is_valid()
    assert "email" in form.errors
```

- [ ] **Step 2: Run tests to verify failure**

Run (user):

```bash
poetry run pytest tests/accounts/test_forms.py -v
```

Expected: All 8 tests fail with `ModuleNotFoundError: No module named 'apps.accounts.forms'`.

- [ ] **Step 3: Create `apps/accounts/forms.py` (user writes — reference below)**

```python
"""Forms for the accounts app (FR-06)."""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class RegistrationForm(UserCreationForm):
    """User registration form — email + 2× password.

    Inherits from `UserCreationForm` which auto-uses the model's
    `USERNAME_FIELD` (= "email") and applies Django's password validators.
    """

    class Meta:
        model = User
        fields = ("email",)


class ResendActivationForm(forms.Form):
    """Single-field form for the resend-activation flow."""

    email = forms.EmailField(label=_("Email"), required=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
poetry run pytest tests/accounts/test_forms.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/accounts/test_forms.py apps/accounts/forms.py
git commit -m "feat(FR-06): add RegistrationForm and ResendActivationForm"
```

---

## Task 9: `RegisterView` (TDD)

**Files:**
- Test: `tests/accounts/test_registration.py`

(Views already scaffolded in Task 7 — this task just tests the behavior end-to-end.)

- [ ] **Step 1: Write failing tests (Claude)**

Create `tests/accounts/test_registration.py`:

```python
"""Tests for the registration view (FR-06)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from tests.accounts.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
def test_register_get_renders_form(client) -> None:
    response = client.get(reverse("accounts:register"))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_register_post_valid_creates_inactive_user(client) -> None:
    response = client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    user = User.objects.get(email="newbie@example.com")
    assert user.is_active is False, (
        "Newly registered user must be inactive until they click the "
        "activation link in their email."
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_sent")


@pytest.mark.django_db
def test_register_post_valid_sends_activation_email(client) -> None:
    client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == ["newbie@example.com"]
    assert "/accounts/activate/" in sent.body


@pytest.mark.django_db
def test_register_post_valid_does_not_log_user_in(client) -> None:
    client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    # session should have no auth user
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_register_post_rejects_duplicate_email(client) -> None:
    UserFactory(email="existing@example.com")

    response = client.post(
        reverse("accounts:register"),
        data={
            "email": "existing@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "Str0ngP@ssw0rd",
        },
    )

    assert response.status_code == 200, "re-renders form on validation error"
    assert "email" in response.context["form"].errors
    assert User.objects.filter(email="existing@example.com").count() == 1
    assert len(mail.outbox) == 0, "no email should be sent on validation failure"


@pytest.mark.django_db
def test_register_post_rejects_mismatched_passwords(client) -> None:
    response = client.post(
        reverse("accounts:register"),
        data={
            "email": "newbie@example.com",
            "password1": "Str0ngP@ssw0rd",
            "password2": "different",
        },
    )

    assert response.status_code == 200
    assert "password2" in response.context["form"].errors
    assert not User.objects.filter(email="newbie@example.com").exists()
    assert len(mail.outbox) == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
poetry run pytest tests/accounts/test_registration.py -v
```

Expected: All 6 tests fail (template `accounts/register.html` not found → `TemplateDoesNotExist`).

- [ ] **Step 3: Create minimal `register.html` to make tests pass**

(User writes — reference below — covered in detail in Task 13. For now, a minimal version sufficient for tests:)

Create `apps/accounts/templates/accounts/register.html`:

```html
{% extends "accounts/_base.html" %}
{% block content %}
<form method="post">{% csrf_token %}{{ form.as_p }}<button type="submit">Zarejestruj</button></form>
{% endblock %}
```

And the parent `_base.html`:

Create `apps/accounts/templates/accounts/_base.html`:

```html
<!DOCTYPE html><html><body>{% block content %}{% endblock %}</body></html>
```

(Full styling deferred to Task 13 / US-09 baseline templates.)

- [ ] **Step 4: Create stub `activation_sent.html` (the redirect target)**

Create `apps/accounts/templates/accounts/activation_sent.html`:

```html
{% extends "accounts/_base.html" %}
{% block content %}<p>Sprawdź swój email, aby aktywować konto.</p>{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
poetry run pytest tests/accounts/test_registration.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/accounts/test_registration.py apps/accounts/templates/accounts/_base.html apps/accounts/templates/accounts/register.html apps/accounts/templates/accounts/activation_sent.html
git commit -m "feat(FR-06): register view creates inactive user and sends activation email"
```

---

## Task 10: `ActivateView` (TDD)

**Files:**
- Test: `tests/accounts/test_activation.py`

(View already scaffolded — this task tests valid/invalid/expired/already-active scenarios.)

- [ ] **Step 1: Write failing tests (Claude)**

Create `tests/accounts/test_activation.py`:

```python
"""Tests for the activation view (FR-06).

Covers: valid token, invalid token, malformed uidb64, nonexistent user,
expired token (freezegun), already-active user double-click, idempotency.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from freezegun import freeze_time

from tests.accounts.factories import UserFactory

User = get_user_model()


def _activation_url_for(user) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return reverse("accounts:activate", kwargs={"uidb64": uidb64, "token": token})


@pytest.mark.django_db
def test_activate_with_valid_token_activates_user(client) -> None:
    user = UserFactory(inactive=True)
    url = _activation_url_for(user)

    response = client.get(url)

    user.refresh_from_db()
    assert user.is_active is True
    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


@pytest.mark.django_db
def test_activate_with_valid_token_shows_success_flash(client) -> None:
    user = UserFactory(inactive=True)
    url = _activation_url_for(user)

    response = client.get(url, follow=True)

    messages_list = [str(m) for m in response.context["messages"]]
    assert any("aktyw" in m.lower() for m in messages_list), (
        f"Expected a success flash mentioning activation. Got: {messages_list}"
    )


@pytest.mark.django_db
def test_activate_with_invalid_token_redirects_to_invalid_page(client) -> None:
    user = UserFactory(inactive=True)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    url = reverse(
        "accounts:activate",
        kwargs={"uidb64": uidb64, "token": "totally-fake-token"},
    )

    response = client.get(url)

    user.refresh_from_db()
    assert user.is_active is False
    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


@pytest.mark.django_db
def test_activate_with_malformed_uidb64_redirects_to_invalid_page(client) -> None:
    url = reverse(
        "accounts:activate",
        kwargs={"uidb64": "!!!not-base64!!!", "token": "anything"},
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


@pytest.mark.django_db
def test_activate_for_nonexistent_user_redirects_to_invalid_page(client) -> None:
    uidb64 = urlsafe_base64_encode(force_bytes(99999))  # no user with this pk
    url = reverse(
        "accounts:activate",
        kwargs={"uidb64": uidb64, "token": "anything"},
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


@pytest.mark.django_db
def test_activate_with_expired_token_redirects_to_invalid_page(client, settings) -> None:
    """Token older than PASSWORD_RESET_TIMEOUT (default 3 days) must be rejected."""
    with freeze_time("2026-05-18 12:00:00"):
        user = UserFactory(inactive=True)
        url = _activation_url_for(user)

    # Move 4 days into the future
    with freeze_time("2026-05-22 12:00:00"):
        response = client.get(url)

    user.refresh_from_db()
    assert user.is_active is False
    assert response.status_code == 302
    assert response.url == reverse("accounts:activation_invalid")


@pytest.mark.django_db
def test_activate_already_active_user_redirects_to_login_with_info(client) -> None:
    """If user clicks the link a second time after activation,
    we should NOT show 'invalid token' — show 'already active' instead."""
    user = UserFactory()  # already active
    url = _activation_url_for(user)

    response = client.get(url, follow=True)

    user.refresh_from_db()
    assert user.is_active is True
    assert response.redirect_chain[-1][0] == reverse("accounts:login")
    messages_list = [str(m) for m in response.context["messages"]]
    assert any("już aktyw" in m.lower() or "already" in m.lower() for m in messages_list), (
        f"Expected an info flash about account already being active. "
        f"Got: {messages_list}"
    )


@pytest.mark.django_db
def test_activate_is_idempotent_on_second_click(client) -> None:
    """First click activates; second click does not crash and still ends at login."""
    user = UserFactory(inactive=True)
    url = _activation_url_for(user)

    client.get(url)  # first click — activates
    response = client.get(url)  # second click — should not 500

    user.refresh_from_db()
    assert user.is_active is True
    assert response.status_code == 302
    assert response.url == reverse("accounts:login")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
poetry run pytest tests/accounts/test_activation.py -v
```

Expected: 8 tests fail — some on missing templates (`activation_invalid.html`), some on flash messages.

- [ ] **Step 3: Create minimal `activation_invalid.html`**

Create `apps/accounts/templates/accounts/activation_invalid.html`:

```html
{% extends "accounts/_base.html" %}
{% block content %}
<p>Link aktywacyjny jest nieprawidłowy lub wygasł.</p>
<p><a href="{% url 'accounts:activation_resend' %}">Wyślij link ponownie</a></p>
{% endblock %}
```

- [ ] **Step 4: Create minimal `login.html` (the redirect target for activated users)**

Create `apps/accounts/templates/accounts/login.html`:

```html
{% extends "accounts/_base.html" %}
{% block content %}
{% for message in messages %}<p>{{ message }}</p>{% endfor %}
<form method="post">{% csrf_token %}{{ form.as_p }}<button type="submit">Zaloguj</button></form>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
poetry run pytest tests/accounts/test_activation.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/accounts/test_activation.py apps/accounts/templates/accounts/activation_invalid.html apps/accounts/templates/accounts/login.html
git commit -m "feat(FR-06): activation view handles valid, invalid, expired, and double-click cases"
```

---

## Task 11: `ResendActivationView` (TDD)

**Files:**
- Test: `tests/accounts/test_resend.py`

- [ ] **Step 1: Write failing tests (Claude)**

Create `tests/accounts/test_resend.py`:

```python
"""Tests for the resend-activation view (FR-06).

The resend endpoint must NOT leak whether an email is registered:
all three scenarios (inactive user / active user / nonexistent email)
must render the same `resend_done.html` template. Real email is sent
only in the inactive-user scenario.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse

from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_resend_get_renders_form(client) -> None:
    response = client.get(reverse("accounts:activation_resend"))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_resend_for_inactive_user_sends_email(client) -> None:
    user = UserFactory(inactive=True, email="dormant@example.com")

    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "dormant@example.com"},
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["dormant@example.com"]
    # body should contain an activation link
    assert "/accounts/activate/" in mail.outbox[0].body


@pytest.mark.django_db
def test_resend_for_active_user_sends_no_email(client) -> None:
    UserFactory(email="active@example.com")  # is_active=True by default

    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "active@example.com"},
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_resend_for_nonexistent_user_sends_no_email(client) -> None:
    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "nobody@example.com"},
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_resend_renders_the_same_template_in_all_scenarios(client) -> None:
    """No enumeration leak: inactive / active / nonexistent all render
    the same `resend_done.html` template (verified via response body
    not depending on which scenario)."""
    UserFactory(inactive=True, email="dormant@example.com")
    UserFactory(email="active@example.com")

    bodies = []
    for email in ["dormant@example.com", "active@example.com", "nobody@example.com"]:
        response = client.post(
            reverse("accounts:activation_resend"),
            data={"email": email},
        )
        # decode body, strip CSRF token differences if any
        bodies.append(response.content)

    # All three should render the same template — the same response body
    # modulo CSRF token differences. Since resend_done.html has no form,
    # there's no CSRF token, so bodies should be exactly equal.
    assert bodies[0] == bodies[1] == bodies[2], (
        "All three resend scenarios must render identical responses "
        "(no enumeration leak)."
    )


@pytest.mark.django_db
def test_resend_with_invalid_email_re_renders_form(client) -> None:
    response = client.post(
        reverse("accounts:activation_resend"),
        data={"email": "not-an-email"},
    )

    assert response.status_code == 200
    assert "form" in response.context
    assert "email" in response.context["form"].errors
    assert len(mail.outbox) == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
poetry run pytest tests/accounts/test_resend.py -v
```

Expected: 6 tests fail — missing `resend.html`, `resend_done.html`.

- [ ] **Step 3: Create minimal `resend.html`**

Create `apps/accounts/templates/accounts/resend.html`:

```html
{% extends "accounts/_base.html" %}
{% block content %}
<form method="post">{% csrf_token %}{{ form.as_p }}<button type="submit">Wyślij ponownie</button></form>
{% endblock %}
```

- [ ] **Step 4: Create minimal `resend_done.html`**

Create `apps/accounts/templates/accounts/resend_done.html`:

```html
{% extends "accounts/_base.html" %}
{% block content %}
<p>Jeśli konto o podanym adresie email istnieje i nie zostało jeszcze aktywowane, wysłaliśmy nowy link aktywacyjny.</p>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
poetry run pytest tests/accounts/test_resend.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/accounts/test_resend.py apps/accounts/templates/accounts/resend.html apps/accounts/templates/accounts/resend_done.html
git commit -m "feat(FR-06): resend activation email without enumeration leak"
```

---

## Task 12: Login/Logout (auth_views config only — TDD)

**Files:**
- Test: `tests/accounts/test_login.py`
- Test: `tests/accounts/test_logout.py`

Views already configured in `urls.py` Task 7 — these tests verify Django's stock `LoginView` / `LogoutView` behave correctly with our custom user.

- [ ] **Step 1: Write failing login tests (Claude)**

Create `tests/accounts/test_login.py`:

```python
"""Tests for the login view (FR-06).

We use Django's stock `auth_views.LoginView` — no custom view code.
Behavior verified: active users log in, inactive users get a generic
"invalid credentials" error (security-first — no enumeration leak),
wrong password fails, `?next=` redirects work.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_login_renders_form(client) -> None:
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_active_user_can_log_in(client) -> None:
    UserFactory(email="alice@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login"),
        data={"username": "alice@example.com", "password": "test1234"},
    )

    assert response.status_code == 302
    assert response.url == "/"
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_inactive_user_cannot_log_in(client) -> None:
    """Inactive user with correct password must NOT be logged in.
    The generic "invalid credentials" error is returned — no leak that
    the account exists but is pending activation."""
    UserFactory(inactive=True, email="dormant@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login"),
        data={"username": "dormant@example.com", "password": "test1234"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_with_wrong_password_fails(client) -> None:
    UserFactory(email="alice@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login"),
        data={"username": "alice@example.com", "password": "wrong"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_redirects_to_next_param(client) -> None:
    UserFactory(email="alice@example.com", password="test1234")

    response = client.post(
        reverse("accounts:login") + "?next=/protected/",
        data={"username": "alice@example.com", "password": "test1234"},
    )

    assert response.status_code == 302
    assert response.url == "/protected/"
```

**Note:** Django's `AuthenticationForm` uses field name `username` even when `USERNAME_FIELD = "email"` — the field is renamed semantically but keeps the form field name `username`. The form template will show "Email" as the label automatically (because the model field has `verbose_name`-like behavior).

- [ ] **Step 2: Write failing logout tests (Claude)**

Create `tests/accounts/test_logout.py`:

```python
"""Tests for the logout view (FR-06)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory


@pytest.mark.django_db
def test_logout_post_destroys_session(client) -> None:
    user = UserFactory(email="alice@example.com", password="test1234")
    client.force_login(user)
    assert "_auth_user_id" in client.session

    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_logout_get_returns_405(client) -> None:
    """Django 5+ LogoutView only accepts POST — GET returns 405."""
    user = UserFactory(email="alice@example.com", password="test1234")
    client.force_login(user)

    response = client.get(reverse("accounts:logout"))

    assert response.status_code == 405
```

- [ ] **Step 3: Run all auth tests to verify failure**

Run:

```bash
poetry run pytest tests/accounts/test_login.py tests/accounts/test_logout.py -v
```

Expected: most fail — `login.html` may already exist (from Task 10) but login may fail because `UserFactory` stores plaintext `password = "test1234"` field but `_create` calls `manager.create_user(password="test1234")` which hashes it.

**Verify by reading factories.py:** the factory does pass `password` as a kwarg to `_create`, which forwards to `manager.create_user(email=..., password=...)`. The manager calls `user.set_password(password)` → hash. ✅ Login should work.

If a test still fails, debug the factory.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
poetry run pytest tests/accounts/test_login.py tests/accounts/test_logout.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/accounts/test_login.py tests/accounts/test_logout.py
git commit -m "test(FR-06): cover login and logout (active vs inactive, POST-only logout)"
```

---

## Task 13: Templates polish (no new behavior, no new tests)

**Files:**
- Modify: all `apps/accounts/templates/accounts/*.html` (replace minimal stubs with proper Bootstrap-aware versions)

US-09 (M1) will introduce the real baseline templates (`cinema/templates/cinema/base.html` with navbar+footer). Until then, our `_base.html` is a thin shim. This task polishes the auth templates so they're presentable for manual smoke-testing.

- [ ] **Step 1: User polishes templates to taste**

User reviews each template (`register.html`, `login.html`, `activation_sent.html`, `activation_invalid.html`, `resend.html`, `resend_done.html`, `_base.html`) and replaces the minimal markup with:
- Bootstrap 5 CDN link (or skip if US-09 isn't done yet)
- Polish-language labels
- Proper page headings
- Flash message rendering on every page that has `{% block content %}`

- [ ] **Step 2: Re-run all account tests to ensure nothing regressed**

Run:

```bash
poetry run pytest tests/accounts/ -v
```

Expected: all tests still pass.

- [ ] **Step 3: Commit**

```bash
git add apps/accounts/templates/accounts/
git commit -m "feat(FR-06): polish account templates (registration, activation, resend, login)"
```

---

## Task 14: Manual smoke test (end-to-end, no automated tests)

**Files:** none — manual verification only.

- [ ] **Step 1: Start docker compose + runserver**

```bash
docker compose up -d
poetry run python manage.py migrate
poetry run python manage.py runserver
```

- [ ] **Step 2: Walk through the happy path in a browser**

In a private window:
1. Visit `http://localhost:8000/accounts/register/`
2. Submit email + password
3. Verify the email appears in the runserver terminal (console backend)
4. Copy the activation link from the terminal
5. Paste into the address bar — should redirect to `/accounts/login/` with a flash
6. Log in with the same credentials — should succeed and redirect to `/`
7. Click logout (or POST to `/accounts/logout/` via a form button) — should redirect to `/` and clear session

- [ ] **Step 3: Walk through the resend flow**

1. Register another user
2. Without clicking the email link, visit `/accounts/activate/resend/`
3. Submit the email — verify a new activation email appears in the terminal
4. Click the new link — should activate

- [ ] **Step 4: Walk through the negative flows**

1. Visit a malformed activation URL (e.g. `/accounts/activate/garbage/garbage/`) — should redirect to `/accounts/activate/invalid/`
2. Click an old activation link after the user is already active — should show "already active" flash on the login page

- [ ] **Step 5: Run the full pytest suite + coverage**

```bash
poetry run pytest tests/accounts/ --cov=apps.accounts --cov-report=term-missing
```

Expected: all tests pass, coverage in `apps/accounts/` ≥90%.

- [ ] **Step 6: Run lint + type-check**

```bash
poetry run ruff check apps/ tests/
poetry run ruff format --check apps/ tests/
poetry run mypy apps/
```

Expected: all clean.

- [ ] **Step 7: Verify pre-commit passes**

```bash
poetry run pre-commit run --all-files
```

Expected: all hooks pass.

---

## Task 15: Update status board + memory after PR merge

**Files:**
- Modify: `.Claude/backlog.md` (move US-07 from "In Progress" to "Done")
- Modify: `memory/project_kinomania_bootstrap.md` (bump to 7/9 done)

**Run after PR is merged into `main`** (not before — status board reflects merged state).

- [ ] **Step 1: Move US-07 in the status board**

In `.Claude/backlog.md` §7:

```markdown
| **In Progress (WIP=1)** | _none_ |
| **Ready (DoR ✅)** | **US-08** (seed_db initial — Genres + Halls + Users) |
| **Backlog** | US-09..US-43 |
| **Done** | **US-01..US-07** ✅✅✅✅✅✅✅ |
```

Update the milestone summary line below the table to: "7/9 US zmergowanych. Kolejny task: US-08 (seed_db initial)."

- [ ] **Step 2: Commit the status board update**

```bash
git checkout main
git pull
git add .Claude/backlog.md
git commit -m "docs(infra): mark US-07 as done in backlog status board"
git push
```

- [ ] **Step 3: Update project memory (Claude updates)**

Claude updates `memory/project_kinomania_bootstrap.md`:
- Bump "Current state" line to `7 z 9 US z M1 zmergowanych (US-01..US-07; US-07 = PR #X merged YYYY-MM-DD)`
- Add to "Local dev pitfalls" if anything new emerged (e.g. freezegun gotchas, console email backend quirks)
- Update "Następny task" to `US-08 (seed_db initial — Genres + Halls + Users)`

---

## Self-review (run before handing off)

**Spec coverage check** — does every spec requirement have a task?

| Spec section | Implemented in |
|---|---|
| §1 Q1 — extended US-07 scope | Task 2 (backlog AC) |
| §1 Q2 — `default_token_generator` | Task 6 (`send_activation_email`), Task 10 (`ActivateView`) |
| §1 Q3 — console backend | Task 3 step 3 |
| §1 Q4 — resend flow | Task 11 |
| §1 Q5 — generic login UX | Task 12 (relies on Django default) |
| §2.1 Register flow | Tasks 8 + 9 |
| §2.1 Activation flow | Tasks 7 + 10 |
| §2.1 Resend flow | Task 11 |
| §2.1 Login UX | Task 12 |
| §2.2 5 views + 2 forms + 1 helper + 8 templates | Tasks 6 (helper), 7 (views), 8 (forms), 9/10/11/13 (templates) |
| §3 Settings + .env + pyproject | Task 3 |
| §3.2 Files structure | Task 7 |
| §3.3 URL patterns | Task 7 step 2 |
| §4.2 Edge cases (full matrix) | Task 10 (8 scenarios), Task 11 (no enum leak) |
| §4.3 Security checklist | Task 12 (generic login msg), Task 11 (no enum leak), no rate limiting (out of scope) |
| §5 Testing strategy | Tasks 5–12 |
| §5.3 UserFactory inactive trait | Task 5 |
| §5.4 freezegun | Task 3 step 1, Task 10 expired token test |
| §6 Docs updates (FR, backlog, .env, memory) | Tasks 1, 2, 3, 15 |
| §7 Commit plan | Tasks 1, 2, 3, 5, 7, 8, 9, 10, 11, 12, 13, 15 (one commit each) |

All spec requirements mapped. No gaps.

**Placeholder scan** — no "TODO/TBD" left in this plan. Every step has either the test code (Claude provides) or the reference application code (user types from).

**Type/name consistency check:**
- `accounts:register`, `accounts:activate`, `accounts:activation_sent`, `accounts:activation_invalid`, `accounts:activation_resend`, `accounts:login`, `accounts:logout` — used consistently across Tasks 7, 9–12.
- `RegistrationForm`, `ResendActivationForm` — Task 8 defines; Task 7 imports lazily inside `get_form_class` (deferred import to avoid circular).
- `send_activation_email(user, request)` signature — defined Task 6, called Task 7 in `RegisterView.form_valid` and `ResendActivationView.form_valid`.
- `UserFactory(inactive=True)` — defined Task 5, used throughout Tasks 6, 9, 10, 11.
- `UserFactory(email=..., password="test1234")` — login tests rely on `password` being hashed by the factory's `_create` which routes through `UserManager.create_user`. Confirmed in Task 12 step 3.

No inconsistencies.

---

## Estimated effort

- Task 1 (FR docs): 15 min
- Task 2 (backlog): 15 min
- Task 3 (settings + freezegun): 20 min
- Task 4 (wire URLs): 5 min
- Task 5 (factory trait): 10 min
- Task 6 (email helper): 30 min
- Task 7 (views scaffold): 30 min
- Task 8 (forms): 25 min
- Task 9 (register view tests): 30 min
- Task 10 (activate view tests): 45 min (8 scenarios, freezegun)
- Task 11 (resend view tests): 25 min
- Task 12 (login/logout tests): 20 min
- Task 13 (templates polish): 30 min
- Task 14 (manual smoke test): 30 min
- Task 15 (after merge): 10 min

**Total: ~5h** — aligns with US-07 estimate L (~1 dzień = 4–6h aktywnej pracy).
