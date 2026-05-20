# KinoMania — Product Backlog

**Wersja:** 1.0
**Data:** 2026-05-04
**Total:** 43 User Stories across 5 milestones (M1..M5 → tags `v0.1.0`..`v1.0.0`)
**Powiązane dokumenty:** `KinoMania_wymagania_funkcjonalne.md`, `workflow_scrum_agile.md`

> **Podział ról (przypomnienie):** kod aplikacji pisze użytkownik. Claude pokazuje szkielet, listę testów, sygnatury — user uzupełnia treść. Pełne reguły w `workflow_scrum_agile.md` §2-3.

---

## 0. Format każdego elementu backlogu

```markdown
### US-XX — <Tytuł>
- **FR:** FR-XX  |  **Milestone:** M2  |  **Branch:** feat/FR-XX-slug
- **Estymata:** M  |  **Zależy od:** US-YY, US-ZZ

**Story:**
*Jako [rola], chcę [funkcja], aby [korzyść].*

**Acceptance Criteria (Given/When/Then):**
- **GIVEN** ... **WHEN** ... **THEN** ...

**DoR:** [✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude

**Tests-first (lista — user pisze):**
- test_…
```

T-shirt sizes: **S** (~2h), **M** (~0.5 dnia), **L** (~1 dzień), **XL** (~2 dni).

---

## 1. M1 — Foundation (`v0.1.0`) — 9 US

### US-01 — Setup projektu i konfiguracja Poetry
- **FR:** infra | **Branch:** `chore/M1-project-setup` | **Estymata:** S
- **Zależy od:** —

**Story:**
*Jako developer, chcę mieć działający szkielet projektu Django z Poetry, aby móc rozpocząć pracę nad funkcjonalnościami.*

**Acceptance Criteria:**
- **GIVEN** czyste repo **WHEN** uruchamiam `poetry install && poetry run python manage.py runserver` **THEN** Django startuje na :8000 bez błędów.
- **GIVEN** plik `.env.example` **WHEN** kopiuję do `.env` i uruchamiam app **THEN** wszystkie zmienne są ładowane przez `django-environ` (`SECRET_KEY`, `DATABASE_URL`, `DEBUG`).
- **GIVEN** struktura `settings/base.py + dev.py + prod.py` **WHEN** uruchamiam z `DJANGO_SETTINGS_MODULE=settings.dev` **THEN** ładuje się dev profile.

**DoR:** [ ] story / [ ] AC / [ ] zależności / [ ] szkielet od Claude

**Tests-first (user pisze):**
- `test_app_starts` — fixture testowa, response na `/` zwraca cokolwiek innego niż 500.
- `test_settings_loads_env_vars` — assertuje że `SECRET_KEY` przeczytany z env.

---

### US-02 — Docker Compose dla PostgreSQL
- **FR:** infra | **Branch:** `chore/M1-docker-postgres` | **Estymata:** S
- **Zależy od:** US-01

**Story:**
*Jako developer, chcę mieć PostgreSQL w Docker Compose, aby dev environment był identyczny z produkcyjnym i `select_for_update` zachowywał się realistycznie.*

**Acceptance Criteria:**
- **GIVEN** `docker compose up -d` **WHEN** uruchamiam `poetry run python manage.py migrate` **THEN** połączenie z Postgres działa, migracje przechodzą.
- **GIVEN** restart kontenera (`docker compose down && docker compose up -d`) **WHEN** wracam **THEN** dane persystują w wolumenie `pg_data`.
- **GIVEN** healthcheck w compose **WHEN** kontener jeszcze się ładuje **THEN** zależne komendy czekają.

**DoR:** [ ] story / [ ] AC / [ ] zależności / [ ] szkielet od Claude

**Tests-first (user pisze):**
- Brak nowych testów — `test_app_starts` z US-01 powinien działać teraz na PG (zmiana DATABASE_URL).

---

### US-03 — Konfiguracja `pyproject.toml` (ruff + mypy + pytest + factory_boy)
- **FR:** infra | **Branch:** `chore/M1-quality-tools` | **Estymata:** S
- **Zależy od:** US-01

**Story:**
*Jako developer, chcę mieć skonfigurowane ruff, mypy, pytest, coverage i factory_boy, aby quality bramki były egzekwowane od początku i nie trzeba było wracać do tego później.*

**Acceptance Criteria:**
- **GIVEN** sekcje `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, `[tool.coverage.*]` w `pyproject.toml` **WHEN** uruchamiam każde z narzędzi **THEN** kończy się sukcesem na pustym projekcie.
- **GIVEN** `pytest` skonfigurowany z `--cov-fail-under=80` **WHEN** uruchamiam bez testów **THEN** `pytest` zwraca exit code 5 (no tests collected) bez błędów konfiguracyjnych.
- **GIVEN** `django-stubs` i `djangorestframework-stubs` w deps **WHEN** uruchamiam `mypy` **THEN** wykrywa Django settings (brak warningów o nieznajomych typach `models.Model`).

**DoR:** [ ] story / [ ] AC / [ ] zależności / [ ] szkielet od Claude

**Tests-first (user pisze):**
- Brak — to konfiguracja narzędzi, nie kod.

---

### US-04 — Pre-commit hooks
- **FR:** infra | **Branch:** `chore/M1-pre-commit` | **Estymata:** S
- **Zależy od:** US-03

**Story:**
*Jako developer, chcę mieć pre-commit hooks blokujące zły kod lokalnie, aby CI nie był pierwszą linią obrony.*

**Acceptance Criteria:**
- **GIVEN** `.pre-commit-config.yaml` zainstalowany (`pre-commit install`) **WHEN** próbuję commitnąć plik z błędem ruff **THEN** commit zostaje zablokowany z komunikatem od ruff.
- **GIVEN** ruff fix w hookach **WHEN** plik ma drobny problem (whitespace) **THEN** ruff sam fixuje i prosi o re-add.
- **GIVEN** `pytest` w hookach `pre-push` (nie `pre-commit`) **WHEN** push z failującym testem **THEN** push zablokowany; commit nadal szybki.

**DoR:** [ ] story / [ ] AC / [ ] zależności / [ ] szkielet od Claude

**Tests-first (user pisze):**
- Brak — narzędzie, nie kod aplikacji.

---

### US-05 — GitHub Actions CI
- **FR:** infra | **Branch:** `ci/M1-github-actions` | **Estymata:** M
- **Zależy od:** US-03, US-04

**Story:**
*Jako developer, chcę mieć CI na GitHub uruchamiający quality gates na każdym PR, aby `main` zawsze był zielony.*

**Acceptance Criteria:**
- **GIVEN** `.github/workflows/ci.yml` z 2 jobami (`quality`, `test`) **WHEN** otwieram PR **THEN** oba jobs uruchamiają się i kończą sukcesem dla pustego projektu.
- **GIVEN** PG service w `test` job **WHEN** `pytest` próbuje połączyć z bazą **THEN** połączenie działa.
- **GIVEN** `--cov-fail-under=80` w `pytest` **WHEN** coverage spadnie poniżej 80% **THEN** CI fails.
- **GIVEN** raport coverage HTML **WHEN** CI kończy **THEN** artifact `coverage-html` jest dostępny w PR.

**DoR:** [ ] story / [ ] AC / [ ] zależności / [ ] szkielet od Claude

**Tests-first (user pisze):**
- Brak — config CI.

---

### US-06 — Custom User model (`accounts.User`)
- **FR:** FR-05 + FR-11 (UserAdmin) | **Branch:** `feat/FR-05-custom-user-model` | **Estymata:** M
- **Zależy od:** US-01, US-02, US-03

**Story:**
*Jako użytkownik, chcę logować się przez email zamiast username, aby nie musieć pamiętać dodatkowej nazwy użytkownika.*

> **KRYTYCZNE:** wykonać `makemigrations accounts` i `migrate` PRZED utworzeniem jakiegokolwiek innego modelu odwołującego się do `settings.AUTH_USER_MODEL`. Zmiana po pierwszej migracji wymaga resetu bazy.

**Acceptance Criteria:**
- **GIVEN** `AUTH_USER_MODEL = "accounts.User"` w settings **WHEN** `poetry run python manage.py createsuperuser` **THEN** prosi o email + hasło (nie username), superuser ma `is_staff=True`, `is_superuser=True`.
- **GIVEN** istniejący user z emailem `a@b.com` **WHEN** tworzę drugiego z tym samym emailem **THEN** `IntegrityError` (unique constraint).
- **GIVEN** custom `UserAdmin` zarejestrowany **WHEN** otwieram `/admin/` **THEN** brak pola `username` w formularzach, login pyta o email.
- **GIVEN** `UserManager.create_user` **WHEN** wywołuję bez emaila **THEN** `ValueError("Email is required")`.

**DoR:** [ ] story / [ ] AC / [ ] zależności / [ ] szkielet od Claude

**Tests-first (user pisze) — `accounts/tests/test_models.py`:**
- `test_create_user_with_email` — utworzenie usera z emailem i hasłem.
- `test_create_user_without_email_raises` — pusty email → `ValueError`.
- `test_create_superuser_sets_flags` — `is_staff` i `is_superuser` = True.
- `test_email_is_username_field` — sprawdzenie `User.USERNAME_FIELD == "email"`.
- `test_email_unique` — drugi user z tym samym emailem → `IntegrityError`.

---

### US-07 — Login/Logout/Register flow with email activation (web)
- **FR:** FR-05, FR-06 | **Branch:** `feat/FR-06-email-auth-flow` | **Estymata:** L
- **Zależy od:** US-06
- **Spec:** [`docs/superpowers/specs/2026-05-18-email-activation-flow-design.md`](../docs/superpowers/specs/2026-05-18-email-activation-flow-design.md)
- **Plan:** [`docs/superpowers/plans/2026-05-18-email-activation-flow.md`](../docs/superpowers/plans/2026-05-18-email-activation-flow.md)

**Story:**
*Jako użytkownik, chcę zarejestrować się przez email + hasło i potwierdzić adres przez klik w link aktywacyjny, aby mieć pewność że konto jest powiązane z moim realnym mailem.*

**Acceptance Criteria (Given/When/Then):**

*Rejestracja:*
- **GIVEN** formularz `/accounts/register/` **WHEN** POST z poprawnym emailem + 2× tym samym hasłem **THEN** user utworzony z `is_active=False`, email z linkiem aktywacyjnym w `mail.outbox`, user NIE zalogowany, redirect na `/accounts/activate/sent/`.
- **GIVEN** próba rejestracji z istniejącym emailem **WHEN** POST **THEN** form error przy polu email, status 200, brak nowego usera, brak emaila w outboxie.
- **GIVEN** mismatched passwords **WHEN** POST **THEN** form error przy `password2`, status 200, brak nowego usera, brak emaila.

*Aktywacja:*
- **GIVEN** świeży link aktywacyjny **WHEN** GET `/accounts/activate/<uidb64>/<token>/` **THEN** `user.is_active=True`, flash sukcesu, redirect na `/accounts/login/`.
- **GIVEN** link z podrobionym tokenem **WHEN** GET **THEN** redirect na `/accounts/activate/invalid/`, user pozostaje `is_active=False`.
- **GIVEN** malformed `uidb64` (śmieci w URL) **WHEN** GET **THEN** redirect na `/accounts/activate/invalid/`.
- **GIVEN** uidb64 dla nieistniejącego usera **WHEN** GET **THEN** redirect na `/accounts/activate/invalid/`.
- **GIVEN** link starszy niż `PASSWORD_RESET_TIMEOUT` (3 dni) **WHEN** GET **THEN** redirect na `/accounts/activate/invalid/`.
- **GIVEN** user już zaktywowany **WHEN** klika link drugi raz **THEN** flash „konto już aktywne" + redirect na `/accounts/login/` (idempotent).

*Resend:*
- **GIVEN** `/accounts/activate/resend/` **WHEN** POST email nieaktywnego usera **THEN** nowy email w outboxie, render `resend_done.html`.
- **GIVEN** POST email aktywnego usera **THEN** outbox bez nowych maili, render `resend_done.html` (no enum leak).
- **GIVEN** POST email nieistniejącego usera **THEN** outbox bez maili, render `resend_done.html` (no enum leak).

*Login/Logout:*
- **GIVEN** active user **WHEN** POST email+password na `/accounts/login/` **THEN** sesja zalogowana, redirect na `?next=` lub `/`.
- **GIVEN** inactive user z poprawnym hasłem **WHEN** POST **THEN** generic „nieprawidłowe dane", brak sesji (decyzja security-first — no enum leak).
- **GIVEN** zły password **WHEN** POST **THEN** generic „nieprawidłowe dane", brak sesji.
- **GIVEN** zalogowany user **WHEN** POST `/accounts/logout/` **THEN** sesja zniszczona, redirect na `/`. GET `/accounts/logout/` → 405 (Django 5+ default).

**DoR:** [✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude (spec + plan)

**Tests-first (Claude pisze) — `tests/accounts/`:**
- `test_registration.py` — register GET/POST, inactive user creation, email sent, no auto-login, redirect, walidacje (duplicate email, mismatched passwords, invalid email)
- `test_activation.py` — valid/invalid/expired/malformed/nonexistent/already-active scenarios (8 cases, `freezegun` na expired)
- `test_resend.py` — inactive (sends), active (silent), nonexistent (silent), zawsze render `resend_done`
- `test_login.py` — active OK, inactive fails generic, wrong password, `?next=` redirect
- `test_logout.py` — POST destroys session, GET 405
- `test_emails.py` — `send_activation_email()` subject/body/from, link absolute z uidb64+token
- `test_forms.py` — RegistrationForm + ResendActivationForm walidacje
- `test_factories.py` — UserFactory `inactive` trait smoke

---

### US-08 — Komenda `seed_db` (initial — Users only)
- **FR:** FR-13 (zawężone do M1) | **Branch:** `feat/FR-13-seed-db-initial` | **Estymata:** M
- **Zależy od:** US-06
- **Spec:** [`docs/superpowers/specs/2026-05-19-seed-db-initial-design.md`](../docs/superpowers/specs/2026-05-19-seed-db-initial-design.md)
- **Plan:** [`docs/superpowers/plans/2026-05-19-seed-db-initial.md`](../docs/superpowers/plans/2026-05-19-seed-db-initial.md)

**Story:**
*Jako developer, chcę mieć komendę zasiewającą bazę testowymi danymi, aby ręcznie testować widoki bez klikania w admin.*

**Zakres M1:** Tylko Users (10 = 8 active + 2 inactive, deterministyczne emaile). Genres+Halls przeniesione do US-16 razem z Movies/Screenings (modele Genre/Hall nie istnieją do US-10).

**Acceptance Criteria:**
- **GIVEN** `poetry run python manage.py seed_db` **WHEN** baza jest pusta **THEN** tworzy 10 users (8 active + 2 inactive) z hasłem `test1234`, emaile `seed.user{i}@kinomania.local` dla i=1..10, inactive na indeksach 9-10.
- **GIVEN** `--flush` **WHEN** istnieją non-superuser users **THEN** usuwa ich wszystkich (zachowując superuserów), potem tworzy seed.
- **GIVEN** `--append` **WHEN** istnieją niektórzy seed userzy **THEN** brakujący są tworzeni, istniejący skip z info do stdout.
- **GIVEN** `--flush --append` razem **THEN** `CommandError("--flush and --append are mutually exclusive")`.
- **GIVEN** non-empty DB bez `--flush` i `--append` **THEN** `CommandError("Database not empty...")` z instrukcją.
- **GIVEN** `DEBUG=False` w env **WHEN** uruchamiam bez `--force` **THEN** `CommandError("seed_db is disabled when DEBUG=False...")`.
- **GIVEN** `--force` **WHEN** `DEBUG=False` **THEN** ostrzeżenie na stderr + kontynuuje.
- **GIVEN** `--users 0` lub ujemny **THEN** `CommandError("--users must be >= 1")`.

**DoR:** [✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude (spec + plan)

**Tests-first (Claude pisze) — `tests/cinema/test_seed_db.py`:**
- `test_seed_db_creates_default_counts` — empty DB → 10 users (8 active + 2 inactive)
- `test_seed_db_emails_are_deterministic` — emails seed.user1..10@kinomania.local, inactive at 9-10
- `test_seed_db_password_is_hashed` — `check_password("test1234")` + PBKDF2 prefix
- `test_seed_db_no_staff_no_super` — is_staff=False, is_superuser=False for all
- `test_seed_db_blocked_when_debug_false_without_force` — CommandError, DB unchanged
- `test_seed_db_force_bypasses_production_guard` — DEBUG=False + --force → 10 users + warning
- `test_seed_db_flush_and_append_mutually_exclusive` — CommandError on both flags
- `test_seed_db_blocks_on_non_empty_db_without_flags` — pre-existing user → CommandError, untouched
- `test_seed_db_flush_preserves_superuser_wipes_others` — superuser stays, non-supers replaced
- `test_seed_db_append_idempotent_skip_existing` — pre-seed 3 → total 10 (3 skipped + 7 new)

---

### US-09 — Baseline templates: extract to global + home view
- **FR:** UI/UX (sekcja 6) | **Branch:** `feat/M1-baseline-templates` | **Estymata:** S
- **Zależy od:** US-07, US-08

> **Scope zmieniony po US-07 (PR #7):** Bootstrap 5 baseline (`_base.html` z navbar + footer + message rendering jako alerts) został już zaimplementowany w `apps/accounts/templates/accounts/_base.html` jako side effect Task 13 z planu US-07. US-09 teraz fokusuje się na: (1) **ekstrakcji** _base.html z accounts do globalnego location (`templates/base.html` + `TEMPLATES.DIRS = [BASE_DIR / "templates"]` w settings/base.py), (2) refactor accounts templates żeby extendowały `base.html` (nie `accounts/_base.html`), (3) **home view** (`/`) renderujący baseline strona z placeholder content + linkami do US-10/US-11 (które dochodzą w M2).

**Story:**
*Jako użytkownik, chcę widzieć spójny layout na każdej podstronie + landing page pod `/`, aby aplikacja wyglądała profesjonalnie od dnia pierwszego.*

**Acceptance Criteria:**
- **GIVEN** `templates/base.html` na globalnym poziomie + `TEMPLATES.DIRS` ustawione **WHEN** dowolna app extenduje `base.html` **THEN** layout dziedziczy poprawnie.
- **GIVEN** wszystkie 6 accounts templates **WHEN** sprawdzam `{% extends %}` **THEN** dziedziczą z `base.html` (NIE z `accounts/_base.html`), `accounts/_base.html` usunięty.
- **GIVEN** home view `/` (np. `TemplateView` z `templates/home.html`) **WHEN** GET **THEN** 200 + render z navbar/footer z `base.html`.
- **GIVEN** istniejące testy accounts (np. login.html messages flash) **WHEN** uruchamiam pytest po refactor **THEN** wszystkie zielone (regression check).

**DoR:** [✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude (spec + plan)

**Tests-first (Claude pisze) — `tests/cinema/test_base_template.py` + `tests/cinema/test_home.py` + `tests/cinema/test_accounts_templates_regression.py`:**
- `test_base_template_includes_navbar` — render `/`, sprawdź `<nav>` i linki.
- `test_navbar_shows_login_for_anon` — anon klient, link Login obecny.
- `test_navbar_shows_logout_for_authenticated` — zalogowany klient, form Logout obecny.
- `test_home_view_returns_200_and_extends_base` — `/` zwraca 200, response zawiera markery z `base.html`.
- `test_accounts_templates_still_extend_base_correctly` — smoke: GET `/accounts/register/` zwraca 200 z navbar (po refactor _base.html → base.html).

- **Spec:** [`docs/superpowers/specs/2026-05-20-baseline-templates-and-home-design.md`](../docs/superpowers/specs/2026-05-20-baseline-templates-and-home-design.md)
- **Plan:** [`docs/superpowers/plans/2026-05-20-baseline-templates-and-home.md`](../docs/superpowers/plans/2026-05-20-baseline-templates-and-home.md)

---

## 2. M2 — Catalog web (`v0.2.0`) — 8 US

| US | Tytuł | FR | Estym. | Branch |
|---|---|---|---|---|
| US-10 | Modele Genre, Actor, Director, Hall, Movie, Screening + migracje | FR-3.2..3.7 | M | `feat/FR-3.2-cinema-models` |
| US-11 | MovieList view + szablon (repertuar) | FR-01 | M | `feat/FR-01-movie-list` |
| US-12 | Filtrowanie i wyszukiwanie filmów | FR-02 | M | `feat/FR-02-movie-filters` |
| US-13 | MovieDetail view + szablon (z embedded YouTube) | FR-03 | M | `feat/FR-03-movie-detail` |
| US-14 | ScreeningList view (harmonogram dnia) | FR-04 | S | `feat/FR-04-screening-list` |
| US-15 | Admin: MovieAdmin, ActorAdmin, DirectorAdmin, GenreAdmin, HallAdmin | FR-11 (parts) | M | `feat/FR-11-cinema-admin` |
| US-16 | Rozbudowa `seed_db` — Genres, Halls, Movies, Screenings | FR-13 | M | `feat/FR-13-seed-db-movies` |
| US-17 | Performance: `prefetch_related` na M2M w listingach | NFR | S | `perf/FR-01-prefetch` |

> Pełne karty US-10..US-17 zostaną rozpisane przy planowaniu M2 (po release `v0.1.0`).

---

## 3. M3 — Booking web + Stripe (`v0.3.0`) — 11 US

| US | Tytuł | FR | Estym. | Branch |
|---|---|---|---|---|
| US-18 | Model Booking + StripeEvent + migracje | FR-3.8 + FR-3.9 | M | `feat/FR-3.8-booking-model` |
| US-19 | BookingForm + validation logic | FR-07 | M | `feat/FR-07-booking-form` |
| US-20 | Booking create view (PENDING + transakcja + select_for_update) | FR-07 | L | `feat/FR-07-booking-create` |
| US-21 | Booking detail view + permissions (403 dla obcych) | FR-08 | S | `feat/FR-08-booking-detail` |
| US-22 | My bookings panel (taby Nadchodzące/Historia) | FR-09 | M | `feat/FR-09-my-bookings` |
| US-23 | Cancel booking flow (web) | FR-10 | M | `feat/FR-10-cancel-booking` |
| US-24 | Stripe Checkout integration (web) | FR-21 | L | `feat/FR-21-stripe-checkout` |
| US-25 | Stripe webhook handler + idempotency | FR-22 | L | `feat/FR-22-stripe-webhook` |
| US-26 | `expire_pending_bookings` management command | FR-23 | S | `feat/FR-23-expire-pending` |
| US-27 | Refund flow przy cancel CONFIRMED | FR-24 | M | `feat/FR-24-refund-flow` |
| US-28 | Admin: BookingAdmin, ScreeningAdmin (z badge dostępności) | FR-11 (parts) | M | `feat/FR-11-booking-admin` |

> Pełne karty US-18..US-28 zostaną rozpisane przy planowaniu M3.

---

## 4. M4 — REST API (`v0.4.0`) — 8 US

| US | Tytuł | FR | Estym. | Branch |
|---|---|---|---|---|
| US-29 | DRF setup + JWT (simplejwt) + drf-spectacular config | FR-16 + infra | M | `chore/M4-drf-setup` |
| US-30 | Auth API: register/token/refresh/me + throttling | FR-16 | M | `feat/FR-16-auth-api` |
| US-31 | Public read-only API: movies/screenings/genres/halls/actors/directors | FR-17 | L | `feat/FR-17-public-api` |
| US-32 | Booking API (list/create/retrieve/cancel) | FR-18 | L | `feat/FR-18-booking-api` |
| US-33 | Stripe Checkout endpoint w API + webhook unified | FR-21, FR-22 | M | `feat/FR-21-checkout-api` |
| US-34 | Admin/staff write API (IsAdminUser) | FR-19 | M | `feat/FR-19-admin-api` |
| US-35 | OpenAPI schema review + Swagger UI + ReDoc + przykłady | FR-20 | S | `feat/FR-20-openapi-docs` |
| US-36 | API throttling per scope + testy throttli | NFR | S | `feat/FR-16-api-throttling` |

> Pełne karty US-29..US-36 zostaną rozpisane przy planowaniu M4.

---

## 5. M5 — Polish (`v1.0.0`) — 7 US

| US | Tytuł | FR | Estym. | Branch |
|---|---|---|---|---|
| US-37 | i18n: makemessages, compilemessages, language switcher w navbarze | FR-15 | L | `feat/FR-15-i18n-setup` |
| US-38 | Tłumaczenia PL/EN — wszystkie user-facing stringi | FR-15 | M | `feat/FR-15-translations` |
| US-39 | Custom 403/404/500 templates + flash messages polish | FR-12 | S | `feat/FR-12-error-pages` |
| US-40 | Performance audit (Django Debug Toolbar, query count assertions) | NFR | S | `perf/M5-query-audit` |
| US-41 | README rewrite (setup full, troubleshooting, architecture) | infra | M | `docs/M5-readme-rewrite` |
| US-42 | Security review (bandit run, csrf coverage, secrets audit) | NFR | S | `chore/M5-security-review` |
| US-43 | Final demo data + screenshots do README | infra | S | `docs/M5-demo-screenshots` |

> Pełne karty US-37..US-43 zostaną rozpisane przy planowaniu M5.

---

## 6. Konwencja branchy

> **Uwaga:** branch names używają **slashy**, nie parentez ani dwukropków (te są tylko w commit/PR title). Slug = snake-case-with-dashes po angielsku.

- `feat/FR-XX-<slug>` — feature branche
- `fix/FR-XX-<slug>` — bugfixy
- `chore/M1-<slug>` — infra/configi (M1, M2, M3, M4, M5)
- `ci/M1-<slug>` — CI/CD
- `perf/FR-XX-<slug>` lub `perf/M5-<slug>` — optymalizacje
- `docs/M5-<slug>` — dokumentacja samodzielna (bez kodu)
- `release/M1`, `release/M2`, ... — release branche per milestone

---

## 7. Status board (live)

> Claude aktualizuje tę tabelę przy każdej zmianie statusu US. WIP limit = 1.

| Status | US |
|---|---|
| **In Progress (WIP=1)** | _none_ |
| **Ready (DoR ✅)** | **US-16** (`seed_db` extension — Genres/Halls/Movies/Screenings) — next per `.Claude/m2_planning.md` |
| **Backlog** | US-11..US-43 |
| **Done** | **US-01..US-10, US-15** ✅✅✅✅✅✅✅✅✅✅✅ |

**Bieżący milestone:** M2 — Catalog web (`v0.2.0`). 2/8 US zmergowanych. US-15 dostarczyło 5 ModelAdminów (Genre/Hall/Actor/Director/Movie) w `apps/cinema/admin.py` z custom display helperami (poster_thumbnail, photo_thumbnail, screenings_count, movies_count, genres_list) + ~34 testów. ScreeningAdmin/BookingAdmin/inlines deferred do US-28 (M3). Następny task: **US-16** (rozbudowa `seed_db` o Genres/Halls/Movies/Screenings) per ordering w `.Claude/m2_planning.md`.

---

## 8. Estymacja całości

| Milestone | US | Suma estymat | Szacunek (3-4h/dzień) |
|---|---|---|---|
| M1 | 9 | ~7 dni | ~1 tydzień |
| M2 | 8 | ~6 dni | ~1 tydzień |
| M3 | 11 | ~9 dni | ~1.5 tygodnia |
| M4 | 8 | ~9 dni | ~1.5 tygodnia |
| M5 | 7 | ~5 dni | ~1 tydzień |
| **Suma** | **43** | **~36 dni** | **~5-6 tygodni** |

> Estymaty są wskazówkami, nie deadlinami. Solo + AI workflow nie ma sprintów ani burndown chartów — milestone-based znaczy „kończymy gdy milestone jest done", nie „kończymy 31 maja".
