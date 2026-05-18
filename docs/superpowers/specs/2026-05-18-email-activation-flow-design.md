# Design — KinoMania: Email Activation Flow (rozszerzenie US-07 / FR-06)

**Data:** 2026-05-18
**Status:** Approved (pending final user review of this written spec)
**Autor:** brainstorming session — bartek + Claude (Opus 4.7)
**Powiązany US:** US-07 (`feat/FR-06-email-auth-flow`) — rozszerzenie scope z `M` do `L`
**Powiązany FR:** FR-06 (Authentication) — wymaga aktualizacji o flow aktywacji
**Cel:** Specyfikacja mechanizmu rejestracji z aktywacją konta przez email. Konto utworzone w wyniku rejestracji jest **nieaktywne** (`is_active=False`) do momentu kliknięcia linku aktywacyjnego z wiadomości email. Dokument rozszerza scope US-07 (Login/Logout/Register flow) o flow aktywacji oraz resend. Nie zawiera jeszcze planu implementacyjnego — ten powstanie przez `superpowers:writing-plans` po akceptacji tego specu.

---

## Spis treści
1. [Decyzje brainstorming](#1-decyzje-brainstorming)
2. [Architektura i przepływ](#2-architektura-i-przepływ)
3. [Zmiany w plikach](#3-zmiany-w-plikach)
4. [Edge cases i security](#4-edge-cases-i-security)
5. [Strategia testów](#5-strategia-testów)
6. [Aktualizacje dokumentacji](#6-aktualizacje-dokumentacji)
7. [Plan commitów](#7-plan-commitów)
8. [Out of scope (follow-up)](#8-out-of-scope-follow-up)

---

## 1. Decyzje brainstorming

| # | Pytanie | Decyzja |
|---|---|---|
| Q1 | **Scope względem US-07** | Rozszerzenie US-07 (register + login + logout + activation + resend w jednym US). Estymata `M → L`. Jeden spójny PR. |
| Q2 | **Mechanizm tokenu** | Django built-in `default_token_generator` (HMAC bezstanowy). Brak nowego modelu, brak migracji. Hash zawiera m.in. `is_active` i `password` — po aktywacji token sam się unieważnia. |
| Q3 | **Email backend (dev)** | `django.core.mail.backends.console.EmailBackend` — emaile printują się do stdout `runserver`. Zero infry, link kopiowany z konsoli. |
| Q4 | **Resend flow** | TAK — `/accounts/activate/resend/` z prostym formularzem. Cichy success niezależnie od stanu emaila (no enum leak). |
| Q5 | **Login UX dla `is_active=False`** | Generic „Invalid credentials" (Django default, security-first). Bez ujawniania że konto istnieje ale czeka na aktywację. |

---

## 2. Architektura i przepływ

### 2.1 Wysokopoziomowy flow

```
[register form]
   |  POST email + password ×2
   v
[RegisterView]
   - tworzy User(is_active=False)             ← KLUCZOWE
   - generuje uid (urlsafe_base64_encode pk) + token (default_token_generator)
   - wysyła email (console backend dev) z absolutnym linkiem
   - NIE loguje usera
   - redirect → /accounts/activate/sent/      ("sprawdź swoją skrzynkę")

[email z linkiem: /accounts/activate/<uidb64>/<token>/]
   |  user klika
   v
[ActivateView]
   - dekoduje uidb64 → user.pk
   - sprawdza token przez default_token_generator.check_token
   - jeśli już aktywny → flash "konto już aktywne" → /accounts/login/
   - jeśli OK:  user.is_active = True; user.save(update_fields=["is_active"])
                flash "konto aktywne" → /accounts/login/
   - jeśli expired/invalid → /accounts/activate/invalid/
                              (z linkiem do resend)

[resend form: /accounts/activate/resend/]
   |  POST email
   v
[ResendActivationView]
   - znajdź usera po emailu
   - jeśli istnieje + is_active=False → nowy token, wyślij email
   - w każdym scenariuszu render resend_done.html (no enum leak)

[login form] — standardowy Django LoginView z auth_views
   - is_active=False → ModelBackend.user_can_authenticate() = False
   - generic "Invalid credentials"
```

### 2.2 Komponenty

- **1 widok rejestracji** (`RegisterView`, FormView)
- **4 widoki aktywacji** (`ActivationSentView`, `ActivateView`, `ActivationInvalidView`, `ResendActivationView`)
- **2 widoki auth** — `LoginView`/`LogoutView` z `django.contrib.auth.views` konfigurowane w `urls.py` (zero kustomowego kodu)
- **2 formy** — `RegistrationForm` (oparta o `UserCreationForm`, pole `email` zamiast `username`), `ResendActivationForm` (jedno pole email)
- **1 helper** — `send_activation_email(user, request)` w `apps/accounts/emails.py` (jedno miejsce do mockowania w testach)
- **7 templates** (5 stron + 2 email templates)

**Brak nowych modeli, brak migracji.** Built-in token generator jest stateless.

---

## 3. Zmiany w plikach

### 3.1 Istniejące pliki (modyfikacja)

| Plik | Zmiana |
|---|---|
| `apps/accounts/models.py` | **Bez zmian** — `is_active` zostaje `default=True` na poziomie modelu, semantyka modelu = „user istnieje". Aktywność to stan rejestracji ustawiany przez `RegisterView`. |
| `apps/accounts/managers.py` | **Bez zmian** — `create_user` zostaje jak jest. Test `test_create_user_with_email` z US-06 nie wymaga modyfikacji. |
| `settings/base.py` | + `LOGIN_URL = "accounts:login"`, `LOGIN_REDIRECT_URL = "/"`, `LOGOUT_REDIRECT_URL = "/"`, `DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")`. Używamy istniejącego `PASSWORD_RESET_TIMEOUT` (Django default 259200s = 3 dni) jako expiry dla activation tokenu. |
| `settings/dev.py` | + `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"` |
| `settings/prod.py` | + SMTP config z env (`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_PORT`, `EMAIL_USE_TLS`) — **placeholder, nie testujemy real SMTP w M1**. Realny deployment to follow-up. |
| `settings/urls.py` | + `path("accounts/", include("apps.accounts.urls", namespace="accounts"))` |
| `.env.example` | + `DEFAULT_FROM_EMAIL=noreply@kinomania.local`, placeholder SMTP vars |
| `pyproject.toml` | + `freezegun` w dev deps (do testu expired tokenu) |

### 3.2 Nowe pliki (apps/accounts/)

```
apps/accounts/
├── urls.py                  ← app_name = "accounts" + 7 URL patterns
├── forms.py                 ← RegistrationForm, ResendActivationForm
├── views.py                 ← RegisterView, ActivationSentView, ActivateView,
│                              ActivationInvalidView, ResendActivationView
├── emails.py                ← send_activation_email(user, request) helper
└── templates/accounts/
    ├── register.html
    ├── login.html
    ├── activation_sent.html         ← "sprawdź email"
    ├── activation_invalid.html      ← "link nieważny / wygasł — wyślij ponownie"
    ├── resend.html                  ← form
    ├── resend_done.html             ← "jeśli istnieje, wysłaliśmy" (no enum leak)
    └── emails/
        ├── activation_subject.txt   ← "Aktywuj konto KinoMania"
        └── activation_body.txt      ← powitanie + absolutny URL + 3-day expiry note
```

**Plik `tokens.py` (dedykowany salt) pomijany w MVP** — istotny dopiero gdy dodamy password reset (żeby token z aktywacji nie działał na reset i odwrotnie). `default_token_generator` używa wspólnego salta — wystarczy dla US-07.

### 3.3 URL patterns

```python
# apps/accounts/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("activate/sent/", views.ActivationSentView.as_view(), name="activation_sent"),
    path("activate/invalid/", views.ActivationInvalidView.as_view(), name="activation_invalid"),
    path("activate/resend/", views.ResendActivationView.as_view(), name="activation_resend"),
    path("activate/<uidb64>/<token>/", views.ActivateView.as_view(), name="activate"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
```

---

## 4. Edge cases i security

### 4.1 `ActivateView` — pełna logika

```python
def get(self, request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return redirect("accounts:activation_invalid")

    if user.is_active:                                  # już aktywny
        messages.info(request, _("Konto jest już aktywne. Możesz się zalogować."))
        return redirect("accounts:login")

    if default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, _("Konto aktywowane. Zaloguj się."))
        return redirect("accounts:login")

    return redirect("accounts:activation_invalid")     # invalid/expired
```

### 4.2 Macierz edge cases

| Scenariusz | Reakcja |
|---|---|
| Malformed `uidb64` (śmieci w URL) | `activation_invalid` |
| `uidb64` OK, user nie istnieje (skasowany) | `activation_invalid` |
| Token podrobiony / zły hash | `activation_invalid` |
| Token expired (>`PASSWORD_RESET_TIMEOUT`) | `activation_invalid` (z linkiem do resend) |
| User klika link drugi raz po aktywacji | flash „konto już aktywne" → `/login/` |
| Admin zmienił hasło między registerem a aktywacją | token automatycznie invalid (hash zawiera password) — `activation_invalid` |
| Concurrent klik tego samego linku (2 taby) | idempotent — `user.save(update_fields=["is_active"])` to no-op po pierwszym |
| Register tym samym emailem co istniejący user | standard `UserCreationForm.clean_email()` → `ValidationError("Email already in use")` (enum leak akceptowany — Django default) |
| Resend dla nieistniejącego emaila | cichy success — `resend_done.html` |
| Resend dla aktywnego konta | cichy success — bez wysyłki emaila |
| Resend dla nieaktywnego konta | wygeneruj nowy token, wyślij, cichy success |

### 4.3 Security checklist

| Element | Decyzja |
|---|---|
| **CSRF** | Standardowy `CsrfViewMiddleware` — wszystkie formy z `{% csrf_token %}` |
| **Token salt** | `default_token_generator` (single salt z password reset) — OK dla MVP. Dedykowany salt w `tokens.py` jako follow-up gdy dodamy password reset. |
| **Token expiry** | `PASSWORD_RESET_TIMEOUT` (Django built-in, default 259200s = 3 dni). Nie wprowadzamy osobnego `ACCOUNT_ACTIVATION_TIMEOUT`. |
| **Rate limiting** (resend brute-force / mail bomb) | **Out of scope w M1** — `django-ratelimit` / `django-axes` to osobny package. Follow-up w M5 security review. |
| **Timing attack** w resend (różny czas dla istniejącego/nieistniejącego usera) | **Out of scope** — akceptujemy, MVP. |
| **Enum leak** w register form | Akceptowane — Django default behavior `UserCreationForm`. |
| **Link bezpieczny** | `default_token_generator` hash zawiera: `user.pk`, `password`, `last_login`, `is_active`, timestamp. Każda zmiana któregokolwiek = token invalid. |
| **Email content** | Plain text (`activation_body.txt`) z absolutnym URL przez `request.build_absolute_uri()`. Brak HTML w MVP — prościej, mniejszy XSS surface. |

---

## 5. Strategia testów

### 5.1 Stack

- `pytest-django` + `factory_boy` + `mail.outbox` fixture (pytest-django auto-overrides `EMAIL_BACKEND` na `locmem` w testach)
- **`freezegun`** — nowa dev dep, do testów expired tokenu

### 5.2 Pliki testowe (`tests/accounts/`)

| Plik | Co pokrywa |
|---|---|
| `test_registration.py` | GET/POST register, inactive user creation, email wysłany, no auto-login, redirect na `activation_sent`, walidacje (duplicate email, mismatched passwords, invalid email) |
| `test_activation.py` | valid token → active + redirect login, invalid token, malformed uidb64, nonexistent user, expired token (`freeze_time`), already-active double-click, idempotency |
| `test_resend.py` | resend dla inactive (wysyła email), dla active (cisza), dla nonexistent (cisza), zawsze ten sam render `resend_done` (no enum leak) |
| `test_login.py` | active user loguje się, inactive user nie loguje (generic error), wrong password, `?next=` redirect |
| `test_logout.py` | POST logout niszczy sesję, GET 405 (Django 5.x default) |
| `test_emails.py` | `send_activation_email()`: subject/body/from, link zawiera uid+token, link jest absolute URL |

**Łącznie ~30 testów.** Coverage cel: ≥90% w `apps/accounts/` (gate global = 80% już aktywny).

### 5.3 Factories

`tests/accounts/factories.py` — rozszerzenie istniejącej `UserFactory` o trait `inactive`:

```python
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "test1234")
    is_active = True

    class Params:
        inactive = factory.Trait(is_active=False)

# użycie: UserFactory(inactive=True)
```

### 5.4 Alternatywy dla `freezegun` (odrzucone)

- Monkey-patching `PASSWORD_RESET_TIMEOUT` + `time.sleep()` — brzydkie, wolne (>3s na test)
- Mockowanie `default_token_generator._now()` — kruche (internals Django, łamie się przy upgrade)

`freezegun` jest standardem, mały package, no-op dla pozostałych testów.

---

## 6. Aktualizacje dokumentacji

| Plik | Zmiana |
|---|---|
| `.Claude/KinoMania_wymagania_funkcjonalne.md` | Rozszerzyć **FR-06** (sekcja Authentication): dodać podsekcję o activation flow — register tworzy `is_active=False`, email z linkiem, klik = aktywacja, resend dostępny. W §2 (Aktorzy) wzmianka o stanie `is_active` jako warunku loginu. |
| `.Claude/backlog.md` | US-07: rozszerzone AC (z 5 do ~10 GIVEN/WHEN/THEN), zaktualizowana lista testów-first, **estymata `M` → `L`**, branch bez zmiany. |
| `.env.example` | + `DEFAULT_FROM_EMAIL`, placeholder SMTP vars (`EMAIL_HOST`, etc.) |
| `memory/project_kinomania_bootstrap.md` | Po merge US-07 → update na „7/9 z M1 zmergowane + FR-06 z activation flow" |

---

## 7. Plan commitów

Granulacja per Conventional Commits + scope `FR-06`:

1. `docs(FR-06): extend functional requirements with email activation flow` — `.Claude/KinoMania_wymagania_funkcjonalne.md`
2. `docs(FR-06): expand US-07 acceptance criteria and tests in backlog` — `.Claude/backlog.md`
3. `chore(infra): add freezegun to dev dependencies` — `pyproject.toml`
4. `test(FR-06): add tests for registration and email activation flow` — wszystkie testy (RED przed implementacją)
5. `feat(FR-06): add accounts urls, forms, and registration view` — register + ActivationSent + email helper + settings + templates
6. `feat(FR-06): add activation, resend, login, logout views` — reszta widoków + templates
7. `docs(infra): mark US-07 as done in backlog status board` — finalny po merge

**Faktyczna liczba commitów do ustalenia przy implementacji** — może być 4–7 w zależności od jak wyjdzie diff.

---

## 8. Out of scope (follow-up)

| Element | Kiedy |
|---|---|
| Rate limiting na `/accounts/activate/resend/` (`django-ratelimit`) | M5 — security review (US-42) |
| Dedykowany salt dla activation tokenu (`apps/accounts/tokens.py`) | Razem z password reset (M1+ lub M5) |
| HTML email template | Po M3 — gdy będziemy mieli prawdziwy branding |
| Tłumaczenia PL/EN dla treści maili | US-37/US-38 (M5 i18n) |
| Realny SMTP w prod (test maila przez Mailpit/Mailtrap) | US konfiguracji deployment (poza M1) |
| Password reset flow (analogiczny mechanizm) | Osobny US — nie w US-07 |

---

## 9. Referencje

- Brainstorming session: 2026-05-18 (Claude Opus 4.7 + bartek)
- Powiązany spec: [`2026-05-04-requirements-rework-design.md`](./2026-05-04-requirements-rework-design.md) — wprowadził FR-06 w v3.0 (bez activation flow)
- Funkcjonalne requirements: [`.Claude/KinoMania_wymagania_funkcjonalne.md`](../../../.Claude/KinoMania_wymagania_funkcjonalne.md) §3.1 (User model), §4 (FR-06 do rozszerzenia)
- Backlog: [`.Claude/backlog.md`](../../../.Claude/backlog.md) US-07
- Django docs: [`default_token_generator`](https://docs.djangoproject.com/en/5.0/topics/auth/passwords/#django.contrib.auth.tokens.PasswordResetTokenGenerator)
