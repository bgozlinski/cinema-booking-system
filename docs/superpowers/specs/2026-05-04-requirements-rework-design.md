# Design — KinoMania: Requirements Rework v3 + Process Bootstrapping

**Data:** 2026-05-04
**Status:** Approved (pending final user review of this written spec)
**Autor:** brainstorming session — bartek + Claude (Opus 4.7)
**Cel:** Aktualizacja istniejącego dokumentu wymagań (`.Claude/KinoMania_wymagania_funkcjonalne.md` v2.0) o REST API (DRF), Stripe sandbox payments oraz pełen proces SCRUM/AGILE adresowany pod pracę solo + AI assistant. Niniejszy dokument jest **specyfikacją zmian** — nie zawiera jeszcze planu implementacyjnego (ten powstanie przez `superpowers:writing-plans` po akceptacji tego specu).

---

## Spis treści
1. [Decyzje architektoniczne](#1-decyzje-architektoniczne)
2. [Zmiany w dokumencie wymagań](#2-zmiany-w-dokumencie-wymagań)
3. [Workflow SCRUM/AGILE](#3-workflow-scrumagile)
4. [Backlog i User Stories](#4-backlog-i-user-stories)
5. [Tooling stack](#5-tooling-stack)
6. [Commit & PR convention](#6-commit--pr-convention)
7. [Pierwsze kroki i plan startu](#7-pierwsze-kroki-i-plan-startu)
8. [Otwarte ryzyka i decyzje na przyszłość](#8-otwarte-ryzyka-i-decyzje-na-przyszłość)

---

## 1. Decyzje architektoniczne

Decyzje podjęte podczas brainstorming session (Q1–Q8):

| Pytanie | Decyzja |
|---|---|
| **Q1 — Zakres DRF** | Pełne równoległe API `/api/v1/...` dla wszystkich modeli, mirror całej funkcjonalności web (CRUD wg uprawnień) |
| **Q2 — Auth API** | JWT (`djangorestframework-simplejwt`) — access + refresh, tokens self-contained |
| **Q3 — Model procesu** | Hybryda Kanban + miesięczne milestones z release tagami, brak sztywnych sprintów |
| **Q4 — Test stack + TDD** | `pytest-django` + `factory_boy` + `pytest-cov`; rygor TDD-2 (test-first w obrębie taska) |
| **Q5 — Code quality + coverage** | `ruff` + `mypy` + `pre-commit` + GitHub Actions CI; coverage threshold 80% |
| **Q6 — Commit + branche** | Conventional Commits z scope FR (`feat(FR-07): ...`) + GitHub Flow z release branchami per milestone |
| **Q7 — CSS / DB / API docs** | Bootstrap 5 / PostgreSQL via docker-compose (dev+prod) / `drf-spectacular` (OpenAPI 3.1) |
| **Q8 — Stripe** | Stripe Checkout (hosted) — sandbox dla całego projektu; webhook handler unified dla web i API |

---

## 2. Zmiany w dokumencie wymagań

### 2.1 Struktura plików

Zamiast jednego rozdętego dokumentu, dzielimy na pięć:

```
.Claude/
├── KinoMania_wymagania_funkcjonalne.md   (v3.0 — UPDATE: DRF + Stripe + drobne fixy)
├── workflow_scrum_agile.md               (NEW)
├── backlog.md                            (NEW: User Stories per FR + nowe US dla API/Stripe)
├── tooling_stack.md                      (NEW)
└── commit_convention.md                  (NEW)
```

### 2.2 Aktualizacja `KinoMania_wymagania_funkcjonalne.md` do v3.0

#### Sekcja 1.2 — założenia technologiczne (rozszerzenie)

- Django REST Framework + `djangorestframework-simplejwt` + `drf-spectacular`
- **Stripe** (`stripe` Python SDK) — tryb **Checkout (hosted)** + Stripe CLI dla webhooków lokalnie
- PostgreSQL via `docker-compose` (dev + prod)
- Python **3.13** (fix niespójności z `pyproject.toml` — było 3.11+)
- CSS: **Bootstrap 5** (jednoznacznie, bez „lub Tailwind")
- Test stack: `pytest-django` + `factory_boy` + `pytest-cov` (zamiast `django.test.TestCase`)
- Code quality: `ruff` + `mypy` + `pre-commit` + GitHub Actions CI
- API docs: `drf-spectacular` (OpenAPI 3.1) + Swagger UI + ReDoc

#### Nowe FR — REST API (sekcja 4)

- **FR-16** — REST API auth: `/api/v1/auth/register/`, `/auth/token/`, `/auth/token/refresh/`, `/auth/me/`
- **FR-17** — Public read-only API: `/api/v1/movies/`, `/genres/`, `/halls/`, `/actors/`, `/directors/`, `/screenings/` (filtry, paginacja, search)
- **FR-18** — Booking API: `/api/v1/bookings/` (list/create/retrieve/cancel) z tą samą logiką transakcyjną co FR-07
- **FR-19** — Admin/staff write API (`IsAdminUser`) dla wszystkich modeli
- **FR-20** — OpenAPI/Swagger: `/api/v1/schema/` + `/api/v1/docs/` + `/api/v1/redoc/`

#### Nowe FR — Stripe (Checkout hosted)

- **FR-21** — Stripe Checkout integration:
  - Web: `POST /bookings/<id>/checkout/` → `redirect()` do Stripe Checkout Session
  - API: `POST /api/v1/bookings/<id>/checkout/` → zwraca `{checkout_url, session_id}` (klient sam robi redirect)
  - `success_url = /bookings/<id>/?stripe=success`, `cancel_url = /bookings/<id>/?stripe=cancelled`
  - Idempotency key per Booking
- **FR-22** — Stripe webhooks: `POST /webhooks/stripe/`
  - Signature verification (`STRIPE_WEBHOOK_SECRET`)
  - Obsługa eventów: `checkout.session.completed` → `CONFIRMED`, `checkout.session.expired` → `CANCELLED`, `payment_intent.payment_failed` → `CANCELLED`
  - Idempotency: persystujemy `stripe_event_id` (tabela `StripeEvent`), odrzucamy duplikaty
- **FR-23** — Auto-expiration PENDING: management command `expire_pending_bookings`
  - Booking starsze niż 15 min ze statusem `PENDING` → `CANCELLED`
  - Wywoływane z cron (dev: ręcznie, prod: cron systemowy / Celery beat — out of scope MVP)
- **FR-24** — Refund flow przy cancel (FR-10):
  - Anulowanie `CONFIRMED` bookingu → Stripe `Refund.create(payment_intent=...)` → status `CANCELLED`
  - Pole `Booking.refund_id`, `Booking.refunded_at`

#### Zmiany w istniejących FR

- **FR-07 (Rezerwacja)** — flow przebudowany:
  ```
  POST /bookings/  → Booking PENDING (zarezerwowane miejsca, expire_at = now + 15min)
                   → redirect/zwrot URL do Stripe Checkout
                   → po sukcesie webhook ustawia CONFIRMED
  ```
- **Model `Booking`** (sekcja 3.8) — dodać pola:
  - `expires_at` DateTimeField (null=True) — dla `PENDING`
  - `stripe_session_id` CharField(255, blank=True)
  - `stripe_payment_intent_id` CharField(255, blank=True)
  - `refund_id` CharField(255, blank=True)
  - `refunded_at` DateTimeField(null=True)
  - **`BookingStatus`**: zostawiamy `PENDING` (ma teraz uzasadnienie — Stripe), domyślny status zmienia się z `CONFIRMED` na `PENDING`
- **`Screening.available_seats_count()`** — liczy `CONFIRMED` + `PENDING` (te które jeszcze nie wygasły) jako zajęte
- **Nowy model `StripeEvent`** (idempotency log):
  - `event_id` CharField unique, `event_type`, `received_at`, `processed_at`, `payload` JSONField
- **FR-13 (seed_db)** — dodać generowanie `PENDING` bookingów do testowania expiration (~5% wszystkich)
- **FR-14 (testy)** — przepisać pod pytest, dodać:
  - testy webhook signature verification
  - testy idempotency (ten sam event 2× → tylko 1 zmiana stanu)
  - testy `expire_pending_bookings` command
  - testy refund flow przy cancel
  - mocking Stripe API (`pytest-mock` + helper fixtures w `conftest.py`)
- **Sekcja 7 (niefunkcjonalne)** — dodać:
  - Throttling DRF: anon 100/h, user 1000/h, auth endpoints 20/h
  - Webhook endpoint zwolniony z CSRF (sygnatura Stripe to weryfikuje)
  - Sekrety Stripe wyłącznie w `.env`, `.env.example` ze wzorcem `sk_test_...`/`whsec_...`
- **Sekcja 8 (struktura projektu)** — dodać:
  - `cinema/api/` (serializers, viewsets, permissions, schema)
  - `accounts/api/` (auth views, serializers)
  - `payments/` (nowa app: stripe service, webhook view, models `StripeEvent`)
  - `docker-compose.yml`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`

---

## 3. Workflow SCRUM/AGILE

Zawartość pliku `.Claude/workflow_scrum_agile.md`.

### 3.1 Model procesu — Hybrid Kanban + Milestones

```
Backlog → Ready → In Progress (WIP=1) → Review → Done
```

- **WIP limit = 1** task `In Progress` jednocześnie
- **Brak sprintów** ze sztywnymi datami; miesięczne **milestone'y** są jedynymi „przystankami"
- Każdy milestone zakończony **release tagiem** w git (`v0.1.0`, `v0.2.0`...) i krótką notatką retro

### 3.2 Role

| Rola | Kto | Zakres |
|---|---|---|
| **Product Owner** | użytkownik | priorytetyzacja, akceptacja DoD, decyzje biznesowe, merge do `main` |
| **Developer** | Claude | implementacja, testy, code review własnego kodu, propozycje commitów i PR-ów |
| **Scrum Master / Tech Lead** | Claude | rozbicie FR na User Stories + AC, refinement, prowadzenie procesu, milestone retros |

### 3.3 Obowiązki Claude

1. **Określanie wymagań SCRUM/AGILE** — każdy FR rozbity na User Stories („As a …, I want …, so that …") + AC w Given/When/Then
2. **TDD per task (TDD-2)** — testy przed implementacją w obrębie taska
3. **Code quality verification** — przed każdym commitem: `ruff check && ruff format --check && mypy && pytest --cov`. Wynik raportowany przed propozycją commita
4. **Propozycje commitów** — Conventional Commits z scope FR, gotowe do skopiowania
5. **Propozycje PR-ów** — tytuł + opis (Summary / Test plan / Linked FR / DoD checklist) gotowe pod `gh pr create`

### 3.4 Definition of Ready (DoR)

Task gotowy do `In Progress`:
- [ ] User Story zapisana w `backlog.md` z linkiem do FR
- [ ] Acceptance criteria w Given/When/Then
- [ ] Lista zależności (które inne tasks/FR muszą być done)
- [ ] Estymacja w T-shirt size (S/M/L/XL)
- [ ] Branch name ustalony (`feat/FR-XX-slug`)

### 3.5 Definition of Done (DoD)

Task gotowy do merge:
- [ ] Implementacja zgodna z AC
- [ ] Testy napisane i przechodzące (`pytest`)
- [ ] Coverage globalne ≥ 80% (CI nie failuje)
- [ ] `ruff check`, `ruff format --check`, `mypy` — bez błędów
- [ ] Migracje OK na czystej bazie
- [ ] i18n: nowe stringi w `gettext_lazy`, `makemessages` uruchomione, tłumaczenia uzupełnione PL/EN
- [ ] OpenAPI schemat aktualny (jeśli dotyczy API)
- [ ] Dokumentacja zaktualizowana (README jeśli setup się zmienił, docstring dla nowych public methods)
- [ ] PR review: użytkownik zaakceptował zmiany
- [ ] Branch zmergowany do `main`, branch usunięty

### 3.6 Ceremonie (lightweight)

| Ceremonia | Częstotliwość | Format | Output |
|---|---|---|---|
| **Backlog refinement** | przed każdym taskiem | Claude proponuje rozbicie FR → US, użytkownik zatwierdza | wpisy w `backlog.md` |
| **Task kickoff** | start każdego taska | Claude tworzy plan w `docs/superpowers/plans/`, użytkownik zatwierdza | plan implementacji |
| **Daily check-in** | co sesja Claude Code | Claude streszcza stan na początku sesji | wiadomość w czacie |
| **Milestone planning** | start każdego milestone | wybór FR-ek, ułożenie kolejności | sekcja w `backlog.md` |
| **Milestone review/demo** | koniec milestone | Claude pokazuje działające features, ostrzega o niedoróbkach | release notes w `CHANGELOG.md` |
| **Milestone retro** | koniec milestone | 3 sekcje: Wnioski / Co poprawić / Co zatrzymać | `docs/retros/MX-retro.md` |

### 3.7 Milestone overview

| Milestone | Cel | FR-ki | Tag | Szacunkowy zakres |
|---|---|---|---|---|
| **M1 — Foundation** | Setup, custom User, Docker, CI, baseline | infra, FR-05, FR-06, FR-13 (initial) | `v0.1.0` | ~1 tydzień |
| **M2 — Catalog (web)** | Repertuar, szczegóły filmu, harmonogram | FR-01, FR-02, FR-03, FR-04, FR-11 (read parts) | `v0.2.0` | ~1 tydzień |
| **M3 — Booking (web + Stripe)** | Rezerwacja, panel usera, anulowanie, Stripe | FR-07, FR-08, FR-09, FR-10, FR-21..FR-24 | `v0.3.0` | ~1.5 tygodnia |
| **M4 — REST API** | DRF API mirror całej funkcjonalności + auth + Stripe | FR-16..FR-20 | `v0.4.0` | ~1.5 tygodnia |
| **M5 — Polish** | i18n PL/EN, error pages, UX, README, performance | FR-12, FR-15, FR-11 (admin polish), nfr | `v1.0.0` | ~1 tydzień |

### 3.8 Eskalacja decyzji

Claude pyta zamiast działać sam, gdy:
- Wybór między 2+ równowartościowymi rozwiązaniami architektonicznymi
- Modyfikacje już zaakceptowanych specyfikacji
- Operacje destruktywne (drop migration, force-push, rebase, `git reset --hard`)
- Dodanie nowej zależności spoza zatwierdzonego stacku
- Zmiana strategii testów lub coverage threshold
- Operacje wymagające zewnętrznych usług (Stripe live keys, deploy)

---

## 4. Backlog i User Stories

Zawartość pliku `.Claude/backlog.md`.

### 4.1 Format każdego elementu backlogu

```markdown
### US-XX — <Tytuł>
- **FR:** FR-XX  |  **Milestone:** M2  |  **Branch:** feat/FR-XX-slug
- **Estymata:** M  |  **Zależy od:** US-YY, US-ZZ

**Story:**
*Jako [rola], chcę [funkcja], aby [korzyść].*

**Acceptance Criteria (Given/When/Then):**
- **GIVEN** ... **WHEN** ... **THEN** ...

**DoR:** [✅] story zapisana / [✅] AC / [✅] zależności

**Tests-first (lista):**
- test_...
```

### 4.2 M1 — Foundation (`v0.1.0`) — 9 US (szczegółowo)

#### US-01 — Setup projektu i konfiguracja Poetry
- FR: infra | Branch: `chore/M1-project-setup` | Estymata: S
- Story: *Jako developer, chcę mieć działający szkielet projektu Django z Poetry, aby móc rozpocząć pracę nad fakturami.*
- AC:
  - **GIVEN** czyste repo **WHEN** uruchamiam `poetry install && poetry run python manage.py runserver` **THEN** Django startuje na :8000 bez błędów
  - **GIVEN** plik `.env.example` **WHEN** kopiuję do `.env` i uruchamiam app **THEN** wszystkie zmienne są ładowane przez `django-environ`
- Tests-first: `test_app_starts`, `test_settings_loads_env_vars`

#### US-02 — Docker Compose dla PostgreSQL
- FR: infra | Branch: `chore/M1-docker-postgres` | Estymata: S
- Story: *Jako developer, chcę mieć PostgreSQL w Docker Compose, aby dev environment był identyczny z produkcyjnym.*
- AC:
  - **GIVEN** `docker-compose up -d` **WHEN** uruchamiam `manage.py migrate` **THEN** połączenie z Postgres działa
  - **GIVEN** restart kontenera **WHEN** wracam **THEN** dane persystują w wolumenie

#### US-03 — Konfiguracja `pyproject.toml` (ruff + mypy + pytest)
- FR: infra | Branch: `chore/M1-quality-tools` | Estymata: S
- AC: `ruff check .` i `mypy .` działają na pustym projekcie bez błędów; `pytest` zwraca „no tests collected" bez błędów konfiguracyjnych

#### US-04 — Pre-commit hooks
- FR: infra | Branch: `chore/M1-pre-commit` | Estymata: S
- AC: commit z błędem ruff/mypy/test → blokowany lokalnie z komunikatem

#### US-05 — GitHub Actions CI
- FR: infra | Branch: `ci/M1-github-actions` | Estymata: M
- AC: na push/PR uruchamia ruff + mypy + pytest + coverage; coverage <80% → fail; raport coverage publikowany jako artifact

#### US-06 — Custom User model (FR-05, części z FR-11)
- FR: FR-05 + FR-11 (UserAdmin) | Branch: `feat/FR-05-custom-user-model` | Estymata: M
- Story: *Jako użytkownik, chcę logować się przez email zamiast username, aby nie musieć pamiętać dodatkowej nazwy.*
- AC:
  - **GIVEN** `python manage.py createsuperuser` **WHEN** podaję email + hasło **THEN** superuser utworzony, `is_staff=True`
  - **GIVEN** drugi user z tym samym emailem **WHEN** próbuję zapisać **THEN** `IntegrityError`
  - **GIVEN** custom UserAdmin **WHEN** otwieram /admin/ **THEN** brak pola `username`, formularz logowania pyta o email
- Tests-first: 5 testów z FR-14 sekcja `accounts/tests/test_models.py`

#### US-07 — Login/Logout/Register flow (FR-05, FR-06)
- FR: FR-05, FR-06 | Branch: `feat/FR-06-email-auth-flow` | Estymata: M
- AC: Given/When/Then dla login z email + dla nieprawidłowego hasła + dla rejestracji + auto-login po rejestracji
- Tests-first: 4 testy z FR-14 `accounts/tests/test_views.py`

#### US-08 — Komenda `seed_db` (initial)
- FR: FR-13 (zawężone) | Branch: `feat(FR-13): seed-db-initial` | Estymata: M
- Zakres M1: tylko Genres + Halls + Users (modele cinema jeszcze nie istnieją); pełen seed po M2

#### US-09 — Baseline templates (base.html, navbar, footer)
- FR: UI/UX (sekcja 6) | Branch: `feat/M1-baseline-templates` | Estymata: S
- AC: Bootstrap 5 zalinkowany; navbar z placeholder linkami; flash messages obszar; placeholder dla i18n switcher

### 4.3 M2 — Catalog web (`v0.2.0`) — 8 US

| US | Tytuł | FR | Estym. |
|---|---|---|---|
| US-10 | Modele Genre, Actor, Director, Hall, Movie, Screening + migracje | FR-3.2..3.7 | M |
| US-11 | MovieList view + szablon (repertuar) | FR-01 | M |
| US-12 | Filtrowanie i wyszukiwanie filmów | FR-02 | M |
| US-13 | MovieDetail view + szablon (z embedded YouTube) | FR-03 | M |
| US-14 | ScreeningList view (harmonogram dnia) | FR-04 | S |
| US-15 | Admin: MovieAdmin, ActorAdmin, DirectorAdmin, GenreAdmin, HallAdmin | FR-11 (parts) | M |
| US-16 | Rozbudowa `seed_db` — Movies, Screenings | FR-13 | S |
| US-17 | Performance: `prefetch_related` na M2M w listingach | NFR | S |

### 4.4 M3 — Booking web + Stripe (`v0.3.0`) — 11 US

| US | Tytuł | FR | Estym. |
|---|---|---|---|
| US-18 | Model Booking + StripeEvent + migracje | FR-3.8 + Stripe | M |
| US-19 | BookingForm + validation logic | FR-07 | M |
| US-20 | Booking create view (PENDING + transakcja + select_for_update) | FR-07 | L |
| US-21 | Booking detail view (FR-08) + permissions (403 dla obcych) | FR-08 | S |
| US-22 | My bookings panel (taby Nadchodzące/Historia) | FR-09 | M |
| US-23 | Cancel booking flow (web) | FR-10 | M |
| US-24 | Stripe Checkout integration (web) | FR-21 | L |
| US-25 | Stripe webhook handler + idempotency | FR-22 | L |
| US-26 | `expire_pending_bookings` management command | FR-23 | S |
| US-27 | Refund flow przy cancel CONFIRMED | FR-24 | M |
| US-28 | Admin: BookingAdmin, ScreeningAdmin (z badge dostępności) | FR-11 (parts) | M |

### 4.5 M4 — REST API (`v0.4.0`) — 8 US

| US | Tytuł | FR | Estym. |
|---|---|---|---|
| US-29 | DRF setup + JWT (simplejwt) + drf-spectacular config | FR-16 + infra | M |
| US-30 | Auth API: register/token/refresh/me + throttling | FR-16 | M |
| US-31 | Public read-only API: movies/screenings/genres/halls/actors/directors | FR-17 | L |
| US-32 | Booking API (list/create/retrieve/cancel) | FR-18 | L |
| US-33 | Stripe Checkout endpoint w API + webhook unified | FR-21, FR-22 | M |
| US-34 | Admin/staff write API (IsAdminUser) | FR-19 | M |
| US-35 | OpenAPI schema review + Swagger UI + ReDoc + przykłady | FR-20 | S |
| US-36 | API throttling per scope + testy throttli | NFR | S |

### 4.6 M5 — Polish (`v1.0.0`) — 7 US

| US | Tytuł | FR | Estym. |
|---|---|---|---|
| US-37 | i18n: makemessages, compilemessages, language switcher w navbarze | FR-15 | L |
| US-38 | Tłumaczenia PL/EN — wszystkie user-facing stringi | FR-15 | M |
| US-39 | Custom 403/404/500 templates + flash messages polish | FR-12 | S |
| US-40 | Performance audit (Django Debug Toolbar, query count assertions) | NFR | S |
| US-41 | README rewrite (setup full, troubleshooting, architecture) | infra | M |
| US-42 | Security review (bandit run, csrf coverage, secrets audit) | NFR | S |
| US-43 | Final demo data + screenshots do README | infra | S |

### 4.7 Statystyki

**43 User Stories**, ~5–6 tygodni przy pracy ~3–4 h/dzień.

### 4.8 Konwencja branchy (przypomnienie)

> **Uwaga:** branch names używają **slashy**, nie parentez ani dwukropków (te są tylko w commit/PR title). Slug = snake-case-with-dashes po angielsku.

- `feat/FR-XX-<slug>` — feature branche
- `fix/FR-XX-<slug>` — bugfixy
- `chore/M1-<slug>` — infra/configi
- `ci/M1-<slug>` — CI/CD
- `release/M1`, `release/M2`, ... — release branche per milestone

---

## 5. Tooling stack

Zawartość pliku `.Claude/tooling_stack.md`.

### 5.1 Zależności (Poetry)

**`pyproject.toml`** — `[tool.poetry.dependencies]`:
```toml
python = "^3.13"
django = "^6.0"
djangorestframework = "^3.15"
djangorestframework-simplejwt = "^5.3"
drf-spectacular = "^0.27"
django-environ = "^0.11"
django-filter = "^24.0"
psycopg = {extras = ["binary"], version = "^3.2"}
pillow = "^11.0"
stripe = "^11.0"
gunicorn = "^23.0"
```

**`[tool.poetry.group.dev.dependencies]`:**
```toml
pytest = "^8.3"
pytest-django = "^4.9"
pytest-cov = "^6.0"
pytest-mock = "^3.14"
factory-boy = "^3.3"
faker = "^30.0"
ruff = "^0.7"
mypy = "^1.13"
django-stubs = {extras = ["compatible-mypy"], version = "^5.1"}
djangorestframework-stubs = {extras = ["compatible-mypy"], version = "^3.15"}
pre-commit = "^4.0"
django-debug-toolbar = "^4.4"
ipython = "^8.29"
```

### 5.2 Ruff (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 100
target-version = "py313"
extend-exclude = ["migrations", "media", "static", "locale"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "DJ", "SIM", "C4", "RET", "PT", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S101"]
"**/settings/*.py" = ["F405", "F403"]
```

### 5.3 Mypy (`pyproject.toml`)

```toml
[tool.mypy]
python_version = "3.13"
strict_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
disallow_untyped_defs = false
check_untyped_defs = true
plugins = ["mypy_django_plugin.main", "mypy_drf_plugin.main"]

[[tool.mypy.overrides]]
module = ["*.migrations.*", "*.tests.*"]
ignore_errors = true

[tool.django-stubs]
django_settings_module = "settings.settings"
```

### 5.4 Pytest (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "settings.settings"
python_files = ["test_*.py", "tests.py"]
addopts = [
    "--cov=accounts",
    "--cov=cinema",
    "--cov=payments",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80",
    "--reuse-db",
    "-ra",
]
markers = [
    "integration: integration tests (slower)",
    "stripe: tests touching Stripe (mocked)",
]
```

### 5.5 Coverage (`pyproject.toml`)

```toml
[tool.coverage.run]
source = ["accounts", "cinema", "payments"]
omit = ["*/migrations/*", "*/tests/*", "*/factories.py", "manage.py", "settings/*"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

### 5.6 Pre-commit (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ["--maxkb=500"]
      - id: check-merge-conflict
      - id: detect-private-key
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [django-stubs, djangorestframework-stubs]
  - repo: local
    hooks:
      - id: pytest-fast
        name: pytest (fast subset)
        entry: poetry run pytest -x -m "not integration" --no-cov
        language: system
        pass_filenames: false
        stages: [pre-push]
```

### 5.7 GitHub Actions CI (`.github/workflows/ci.yml`)

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install poetry && poetry install
      - run: poetry run ruff check .
      - run: poetry run ruff format --check .
      - run: poetry run mypy .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: kinomania_test }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install poetry && poetry install
      - run: poetry run pytest --cov-fail-under=80
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/kinomania_test
          SECRET_KEY: ci-secret
          STRIPE_SECRET_KEY: sk_test_dummy
          STRIPE_WEBHOOK_SECRET: whsec_dummy
      - uses: actions/upload-artifact@v4
        with: { name: coverage-html, path: htmlcov/ }
```

### 5.8 Docker Compose (`docker-compose.yml`)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: kinomania
      POSTGRES_USER: kinomania
      POSTGRES_PASSWORD: kinomania
    ports: ["5432:5432"]
    volumes: [pg_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kinomania"]
      interval: 5s
      retries: 10
volumes:
  pg_data:
```

Stripe webhook lokalnie: `stripe listen --forward-to localhost:8000/webhooks/stripe/` — instalacja Stripe CLI w README.

### 5.9 `.env.example`

```ini
DEBUG=True
SECRET_KEY=change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://kinomania:kinomania@localhost:5432/kinomania
LANGUAGE_CODE=pl
TIME_ZONE=Europe/Warsaw

# Stripe (test mode keys from dashboard.stripe.com/test)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CURRENCY=pln

# JWT
JWT_ACCESS_TOKEN_LIFETIME_MIN=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# DRF throttling
THROTTLE_ANON=100/hour
THROTTLE_USER=1000/hour
THROTTLE_AUTH=20/hour
```

### 5.10 Factory Boy — konwencja

**Lokalizacja:** `accounts/factories.py`, `cinema/factories.py`, `payments/factories.py`

**Konwencja:** `<Model>Factory` (np. `UserFactory`, `MovieFactory`, `BookingFactory`). Subfactories: `ConfirmedBookingFactory`, `PendingBookingFactory`, `PastScreeningFactory`.

**Zasady:**
- Factory NIGDY nie generuje plików obrazów (`None` dla `ImageField`); osobny `ImageFactory` tylko do testów uploadu
- `created_at`/`auto_now_add` — `factory.LazyFunction(timezone.now)` lub `freezegun` w teście
- Stripe ID z konwencją `cs_test_<faker>`, `pi_test_<faker>` — testy nie wołają Stripe API (mock)

### 5.11 Mockowanie Stripe w testach

- Pattern: `pytest-mock` + `mocker.patch("stripe.checkout.Session.create")`
- Helper fixture w `conftest.py`: `stripe_session_factory`, `stripe_event_factory` zwracające słowniki w formacie Stripe
- Test webhooków: generujemy fake event + manualnie liczymy podpis `stripe.WebhookSignature.verify_header` używając `STRIPE_WEBHOOK_SECRET=whsec_test`

### 5.12 Polecenia developerskie (do README)

```bash
# Setup
poetry install && poetry run pre-commit install
docker compose up -d
cp .env.example .env  # uzupełnij Stripe test keys
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run python manage.py seed_db

# Codzienna praca
poetry run python manage.py runserver
stripe listen --forward-to localhost:8000/webhooks/stripe/  # w drugim terminalu

# Quality gates (lokalnie)
poetry run ruff check . --fix
poetry run ruff format .
poetry run mypy .
poetry run pytest --cov

# i18n
poetry run python manage.py makemessages -l en -l pl --ignore=venv
poetry run python manage.py compilemessages
```

---

## 6. Commit & PR convention

Zawartość pliku `.Claude/commit_convention.md`.

### 6.1 Format commit message

```
<type>(<scope>): <subject>

[body — opcjonalny, why a nie what]

[footer — opcjonalny: BREAKING CHANGE, Refs, Co-Authored-By]
```

**Wymagania:**
- `<subject>` w trybie rozkazującym, **angielski**, bez kropki, max 72 znaki
- `<scope>` = numer FR (`FR-07`) lub kategoria (`infra`, `ci`, `deps`, `docs`)
- Pusta linia między subject a body
- Body wrap na 100 znaków
- Footer: `Refs: US-20`, `BREAKING CHANGE: ...`

### 6.2 Allowed `<type>`

| type | Kiedy używać | Przykład |
|---|---|---|
| `feat` | Nowa funkcjonalność widoczna dla usera | `feat(FR-07): add booking creation flow` |
| `fix` | Bugfix | `fix(FR-22): handle duplicate Stripe events idempotently` |
| `test` | Tylko zmiany w testach (gdy nie towarzyszą `feat`/`fix`) | `test(FR-18): add API contract tests for bookings` |
| `refactor` | Zmiana struktury bez zmiany zachowania | `refactor(FR-09): extract booking-list query to manager` |
| `docs` | Dokumentacja (README, docstrings, wymagania) | `docs(infra): document Stripe CLI setup in README` |
| `chore` | Setup, deps, configi (nie kod aplikacji) | `chore(deps): bump djangorestframework to 3.16` |
| `ci` | Tylko zmiany w CI/CD | `ci(infra): cache Poetry deps in GitHub Actions` |
| `style` | Whitespace/format (rzadko) | `style: apply ruff format` |
| `perf` | Optymalizacja wydajności | `perf(FR-01): prefetch genres in MovieList` |
| `build` | Build system / pyproject.toml | `build: switch psycopg to binary extras` |
| `revert` | Cofnięcie poprzedniego commita | `revert: feat(FR-19): admin write API` |

### 6.3 Konwencja `<scope>`

| Scope | Kiedy |
|---|---|
| `FR-XX` | Praca związana z konkretnym FR (większość) |
| `infra` | Setup, Docker, Poetry, struktura |
| `ci` | GitHub Actions, pre-commit |
| `deps` | Tylko deps |
| `docs` | Sam dokument (README, .Claude/, retros) |
| `i18n` | Tłumaczenia (locale/*.po) — używać przy M5 |
| `M1`–`M5` | Tylko gdy commit dotyczy całego milestone (rzadko) |

**Multiscope:** dopuszczalne `feat(FR-21,FR-22): ...` gdy zmiana atomicznie obejmuje 2 FR.

### 6.4 Przykłady

**`feat`:**
```
feat(FR-07): implement booking creation with row locking

Wraps Booking creation in transaction.atomic() with select_for_update
on the Screening row to prevent race conditions when two users compete
for the last seats. Returns 409 Conflict when capacity check fails
post-lock (defensive — lock should prevent it but the check stays).

Refs: US-20
```

**`feat` + nowy model:**
```
feat(FR-22): add StripeEvent model for webhook idempotency

Stores every received Stripe event_id with received_at and payload.
Webhook handler rejects duplicates by event_id unique constraint, so
retries from Stripe never double-process state changes.

Refs: US-25
```

**`fix` z BREAKING:**
```
fix(FR-18): rename booking API field seats -> seats_count

Aligns API serializer with the model field name. Existing API clients
must update their request/response payloads.

BREAKING CHANGE: POST /api/v1/bookings/ now expects "seats_count"
instead of "seats". GET responses also use the new key.

Refs: US-32
```

**`test`-only:**
```
test(FR-22): add idempotency test for duplicate Stripe events

Sends the same checkout.session.completed event twice and asserts
the booking transitions to CONFIRMED only once.

Refs: US-25
```

**`chore` + `deps`:**
```
chore(deps): add stripe and djangorestframework-simplejwt

Pinned to ^11.0 and ^5.3 respectively. Bundles djangorestframework-stubs
in dev group for mypy.

Refs: US-29
```

**`docs`:**
```
docs(infra): document local Stripe webhook setup with stripe CLI

Adds "Local development with Stripe" section to README explaining
stripe listen --forward-to and where to copy the whsec_ secret to .env.
```

### 6.5 Reguła „jeden commit = jedna spójna zmiana"

- ✅ Model + migracja + admin dla tego modelu w jednym commicie
- ✅ View + template + URL routing + test dla tego view w jednym commicie
- ❌ Wiele niezwiązanych refactorów w jednym commicie
- ❌ Mieszanie `feat` z `chore(deps)` w jednym

**Reguła:** „commit message musi się zmieścić w jednym `<type>(<scope>):`". Jeśli trzeba dwóch typów — zrób dwa commity.

**Wyjątek:** `feat` + odpowiadające testy idą razem (TDD-2 — testy są częścią kompletnej funkcjonalności).

### 6.6 Co Claude robi automatycznie

**Przed każdym `git commit`:**
1. Uruchamia `ruff check .`, `ruff format --check .`, `mypy .`, `pytest --cov` (lokalnie)
2. Pokazuje wynik wszystkich gates
3. Pokazuje proponowany commit message w bloku do skopiowania (HEREDOC z `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`)
4. Czeka na akceptację użytkownika („merge", „commit", „ok") — **nigdy nie commituje samodzielnie bez explicit zgody**

### 6.7 PR template (`.github/pull_request_template.md`)

```markdown
## Summary
<1–3 bullety: co i dlaczego>

## Linked
- FR: FR-XX
- US: US-XX

## Definition of Done checklist
- [ ] Acceptance Criteria spełnione
- [ ] Testy napisane i przechodzące (`pytest`)
- [ ] Coverage ≥ 80%
- [ ] `ruff check`, `ruff format --check`, `mypy` — czyste
- [ ] Migracje OK na czystej bazie
- [ ] i18n: `gettext_lazy` na nowych stringach, `makemessages` uruchomione
- [ ] OpenAPI schema aktualny (jeśli dotyczy API)
- [ ] README zaktualizowane (jeśli setup się zmienił)

## Test plan
- [ ] <ręczny test 1>
- [ ] <ręczny test 2>

## Screenshots / API examples
<dla zmian UI lub API>

## Notes
<otwarte pytania, follow-upy, znane ograniczenia>
```

### 6.8 PR title

**Identyczny format jak commit message:** `<type>(<scope>): <subject>`. Powód: GitHub *Squash & merge* używa tytuł PR jako message squashed commita — historia `main` ma jednolity Conventional Commits format.

### 6.9 Release flow per milestone

1. Wszystkie US z milestone zmergowane do `main`
2. `git checkout -b release/M3` z `main`
3. Bump wersji w `pyproject.toml` (`version = "0.3.0"`)
4. Wpis w `CHANGELOG.md`
5. PR `release/M3 → main`, merge
6. Tag: `git tag -a v0.3.0 -m "M3: Booking + Stripe"` + `git push --tags`
7. Notatka retro w `docs/retros/M3-retro.md`

### 6.10 Operacje wymagające ręcznej akceptacji

Claude NIE wykonuje samodzielnie:
- Cokolwiek dotykającego sekretów (`.env`, klucze, hasła)
- Force-push, rebase na `main`, `git reset --hard`
- Merge do `main` (zawsze przez PR)
- Edycja istniejącej migracji (zamiast tego — nowa migracja)
- Tag releasowy

---

## 7. Pierwsze kroki i plan startu

### 7.1 Stan obecny vs stan po zatwierdzeniu specu

**Teraz:**
```
cinema-booking-system/
├── .Claude/
│   └── KinoMania_wymagania_funkcjonalne.md  (v2.0)
├── .idea/
├── pyproject.toml  (puste deps)
└── poetry.lock
```

**Po zatwierdzeniu specu (przed pierwszym commitem kodu):**
```
cinema-booking-system/
├── .Claude/
│   ├── KinoMania_wymagania_funkcjonalne.md  (v3.0 — UPDATE)
│   ├── workflow_scrum_agile.md              (NEW)
│   ├── backlog.md                           (NEW)
│   ├── tooling_stack.md                     (NEW)
│   └── commit_convention.md                 (NEW)
├── docs/
│   ├── superpowers/specs/2026-05-04-requirements-rework-design.md  (TEN PLIK)
│   └── retros/                              (puste, zapełni się po M1)
├── .github/
│   └── pull_request_template.md
└── ...
```

### 7.2 Sprint zerowy — Spec consolidation (przed M1)

**Cel:** zatwierdzony spec + repo zinicjalizowane do GitHuba, jeszcze BEZ kodu aplikacji.

| # | Task | Commit message |
|---|---|---|
| T0.1 | Zapis tego designu do `docs/superpowers/specs/2026-05-04-requirements-rework-design.md` | `docs(infra): add brainstorm design for requirements rework v3` |
| T0.2 | Update `.Claude/KinoMania_wymagania_funkcjonalne.md` do v3.0 (DRF + Stripe + fixy) | `docs(infra): bump requirements to v3.0 with DRF and Stripe` |
| T0.3 | Dodaj `.Claude/workflow_scrum_agile.md` | `docs(infra): document SCRUM/AGILE workflow for solo+AI` |
| T0.4 | Dodaj `.Claude/backlog.md` (43 US) | `docs(infra): add product backlog with 43 user stories` |
| T0.5 | Dodaj `.Claude/tooling_stack.md` | `docs(infra): document tooling stack and configurations` |
| T0.6 | Dodaj `.Claude/commit_convention.md` | `docs(infra): document commit and PR conventions` |
| T0.7 | Dodaj `.github/pull_request_template.md` | `chore(ci): add pull request template` |
| T0.8 | `git init` + `.gitignore` + `README.md` (placeholder) + first commit + push do nowego GitHub repo | `chore(infra): initialize git repository and GitHub remote` |

### 7.3 Pierwsze 5 commitów M1 (gotowe wiadomości do skopiowania)

```
chore(infra): bootstrap Django project with Poetry

Adds Django 6 baseline with split settings (base/dev/prod), django-environ
for .env loading, and a smoke test ensuring the app boots and reads env vars.

Refs: US-01
```

```
chore(infra): add docker-compose with PostgreSQL 16

Adds local PG service with persistent volume and healthcheck. Updates
.env.example and README with the start command.

Refs: US-02
```

```
chore(infra): configure ruff, mypy, pytest, factory_boy

Pins quality and test toolchain in pyproject.toml. Coverage threshold
set to 80%. django-stubs and djangorestframework-stubs included for
mypy. Empty pytest run passes; ruff/mypy run on the bare project clean.

Refs: US-03
```

```
chore(ci): install pre-commit hooks for ruff and mypy

Adds .pre-commit-config.yaml with trailing-whitespace, end-of-file-fixer,
ruff (lint+format) and mypy. pytest moved to pre-push stage so commits
remain fast.

Refs: US-04
```

```
ci(infra): add GitHub Actions workflow for lint, type-check, tests

Two jobs: quality (ruff + mypy) and test (pytest with PG service,
coverage gate at 80%). Coverage HTML uploaded as artifact.

Refs: US-05
```

### 7.4 Zasady operacji Claude na start

Każda sesja startująca task:
1. **Wczytuje** `.Claude/backlog.md` → znajduje task z najwyższym priorytetem niezależnie statusu *Ready*
2. **Tworzy** plan w `docs/superpowers/plans/<US-XX>-plan.md` (przez skill `superpowers:writing-plans`)
3. **Czeka na akceptację** planu od użytkownika
4. **Wykonuje** TDD-2: testy → implementacja → quality gates → propozycja commita
5. **Po DoD** proponuje PR, czeka na merge od użytkownika
6. **Aktualizuje** `backlog.md` (US oznaczony jako Done) i `MEMORY.md` jeśli zaszły zmiany w workflow

### 7.5 Co użytkownik robi „ręcznie"

- Tworzy nowe repo na GitHub, przekazuje URL
- `gh auth login` (jeśli nie zalogowany)
- `gh pr create` może uruchomić sam, lub Claude przygotowuje komendę z `! gh pr create ...`
- Ostateczna decyzja merge → kliknięcie *Squash & merge* na GitHubie
- Tagowanie releasu na koniec milestone (Claude przygotowuje komendę)
- Wprowadzenie kluczy Stripe sandbox do `.env` (Claude nie dotyka sekretów)

### 7.6 Definicja sukcesu całego projektu

- [ ] 5 release tagów (`v0.1.0` … `v1.0.0`) na GitHubie
- [ ] 5 retrospektyw w `docs/retros/`
- [ ] CI green na `main` przez cały okres pracy
- [ ] Coverage ≥ 80% przez cały okres
- [ ] `poetry run python manage.py runserver` + `docker compose up` + `stripe listen` = pełen working cinema z bookingiem przez Stripe sandbox
- [ ] Swagger UI pod `/api/v1/docs/` z opisanymi endpoint'ami i przykładami
- [ ] Aplikacja w pełni dwujęzyczna PL/EN
- [ ] README pozwala obcej osobie postawić projekt lokalnie w <10 min

---

## 8. Otwarte ryzyka i decyzje na przyszłość

- **Celery beat dla `expire_pending_bookings`** — out of scope MVP; w M3 ręczny cron na hoście. Jeśli projekt rozwinie się produkcyjnie → osobny milestone „M6: async + scheduled".
- **Strict mypy** — startujemy z `disallow_untyped_defs=False`; do podniesienia w M5.
- **Stripe live mode** — całość projektu w sandbox; przejście na live wymaga osobnego designu (PCI considerations, `live` vs `test` keys, deploy infra).
- **Email service** (rejestracja, reset hasła) — nieobjęty bieżącym specem; jeśli potrzebny → nowe US-44+ w M5 lub M6.
- **Stripe Payment Intents jako alternatywa Checkout** — jeśli kiedyś będzie chęć nauczyć się embedded UI Stripe.js; osobny design.

---

## 9. Następne kroki

1. **Użytkownik** robi review tego specu — akceptuje lub prosi o zmiany.
2. Po akceptacji: Claude wywołuje `superpowers:writing-plans` aby stworzyć **plan implementacyjny** dla pierwszych tasków sprintu zerowego (T0.1–T0.8) **albo** od razu pierwszego US z M1 (US-01 — Setup projektu).
3. Egzekucja zgodnie z workflow z sekcji 3.
