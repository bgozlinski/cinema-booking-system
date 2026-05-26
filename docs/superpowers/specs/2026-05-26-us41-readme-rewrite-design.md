# US-41 — README rewrite (setup, troubleshooting, architecture)

- **Milestone:** M5 — Security & i18n polish (`v1.0.0`)
- **Type:** infra · **Size:** M · **Branch:** `docs/M5-readme-rewrite`
- **Backlog:** "README rewrite (setup full, troubleshooting, architecture)"
- **Date:** 2026-05-26

## Goal

Replace the 48-line sprint-zero `README.md` (which still says "application code
arrives in M1" with every milestone unchecked) with a complete, accurate README for
the finished M1–M5 project. It must serve two readers: a portfolio reviewer skimming
the top, and a developer cloning the repo to run it.

This is a **docs-only** story — no TDD. Verification is the rendered Markdown plus the
setup steps being factually correct against the codebase. Two tiny non-doc additions
are in scope: a new `LICENSE` file (MIT) and a one-character `.env.example` fix.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Audience | **Balanced** — skimmable top (pitch/features/stack), deep developer section below |
| Language | English (matches the current README; the *app* is i18n PL/EN, docs stay EN) |
| Screenshots | **Omitted** — US-43 owns demo data + images and will add the section |
| License | **MIT** — add a real `LICENSE` file + README badge |
| `.env.example` port | **Fix 5432 → 5439** to match the committed compose override (see below) |

## Verified codebase facts (the README must match these)

- `manage.py` defaults `DJANGO_SETTINGS_MODULE = "settings.dev"`.
- **Postgres host port is 5439, not 5432.** `docker-compose.override.yml` (committed,
  auto-merged by `docker compose`) sets `ports: !override ["5439:5432"]`, but
  `.env.example`'s `DATABASE_URL` uses `5432`. A fresh `cp .env.example .env` therefore
  fails to connect. Resolution: change the single digit in `.env.example` to `5439`,
  AND document the override + port in Setup/Troubleshooting.
- `seed_db` flags: `--force` (allow when DEBUG=False), `--users` (10), `--flush`,
  `--append`, `--movies` (20), `--screenings` (100), `--bookings` (30). It creates
  **only non-superuser users** — admin access needs a separate `createsuperuser`.
- URL map (`settings/urls.py`): `admin/`, `accounts/`, web at root (cinema/booking/
  payments), `api/v1/`, `i18n/`. Media served only when `DEBUG`.
- API docs (`settings/api_urls.py`, mounted at `/api/v1/`): Swagger `/api/v1/docs/`,
  ReDoc `/api/v1/redoc/`, schema `/api/v1/schema/`. Auth = JWT (simplejwt).
- Apps: `accounts` (custom email user + activation), `cinema` (movies/screenings/
  halls + `selectors.py`), `booking` (reservation + `services.py` + expiry command),
  `payments` (Stripe `services.py` + webhook).
- Quality: Poetry; pre-commit (trailing-ws, ruff, mypy, pytest-fast on pre-push);
  CI `quality` job (ruff + mypy + bandit) and `test` job (pytest, `--cov-fail-under=80`).
- No `LICENSE` file currently exists.

## README structure

Top-to-bottom; each section scaled to need. The three backlog pillars — **setup,
troubleshooting, architecture** — are each first-class sections.

1. **Title + tagline + badges** — project name, one-line pitch; badges: CI status
   (GitHub Actions `ci.yml`), Python 3.13, Django 6, License MIT.
2. **Overview** — 2–3 sentences: what KinoMania is, that it's a learning-grade,
   milestone-built (M1–M5) Django + DRF cinema booking system with Stripe sandbox.
3. **Features** — grouped bullets: Catalog (movies/screenings/search/filter),
   Booking (seat reservation + auto-expiry of pending), Payments (Stripe Checkout
   sandbox + signature-verified webhooks + refunds), Accounts (email login +
   activation email), REST API (DRF + JWT + OpenAPI), i18n PL/EN, Django admin,
   Quality gates (CI, tests, coverage, bandit).
4. **Tech stack** — compact table (language/framework/DB/payments/UI/tooling/CI),
   versions sourced from `pyproject.toml`.
5. **Architecture** (medium depth):
   - App-responsibility table (`accounts` / `booking` / `cinema` / `payments`).
   - Settings split (`base` → `dev` / `prod`), env-driven via `django-environ`.
   - The service/selector pattern (`*/services.py`, `cinema/selectors.py`) — business
     logic out of views.
   - Stripe webhook flow: signature verify (`construct_event`) → idempotent
     (`StripeEvent.get_or_create`) → row-lock (`select_for_update`).
6. **Getting started** — prerequisites (Python 3.13, Poetry, Docker) then ordered steps:
   clone → `poetry install` → `poetry run pre-commit install` (+ `--hook-type pre-push`)
   → `cp .env.example .env` (note port 5439, set Stripe keys) → `docker compose up -d`
   → `poetry run python manage.py migrate` → `poetry run python manage.py createsuperuser`
   → `poetry run python manage.py seed_db` → `poetry run python manage.py runserver`
   → open `http://localhost:8000`. Plus a short "Stripe webhooks locally" note
   (`stripe listen --forward-to localhost:8000/payments/webhook/`, set
   `STRIPE_WEBHOOK_SECRET`).
7. **Configuration** — `.env` variable table grouped (core, database, i18n, email,
   Stripe, JWT, throttling) with one-line descriptions, sourced from `.env.example`.
8. **Troubleshooting** — real traps: Postgres host **port 5439 vs 5432**; "connection
   refused / DB not ready" → wait for healthcheck / `docker compose ps`; admin login
   fails → `seed_db` makes only regular users, run `createsuperuser`; migrations must
   run before `seed_db`; Stripe webhook 400 → missing/!wrong `STRIPE_WEBHOOK_SECRET`;
   `__debug__` toolbar absent under tests → it's gated off when pytest is loaded.
9. **Tests & quality** — `poetry run pytest` (coverage ≥ 80%), `ruff check .`,
   `ruff format --check .`, `mypy .`, `bandit -c pyproject.toml -r apps settings`,
   `pre-commit run --all-files`.
10. **API** — base `/api/v1/`, JWT auth (obtain/refresh), interactive docs at
    `/api/v1/docs/` (Swagger) and `/api/v1/redoc/`, raw schema at `/api/v1/schema/`.
11. **Internationalisation** — PL/EN, navbar switcher, `makemessages -l pl -l en`
    / `compilemessages` workflow.
12. **Project structure** — annotated directory tree (`apps/`, `settings/`,
    `templates/`, `tests/`, `docs/`, `locale/`, `static/`, `media/`).
13. **Milestones** — M1 (`v0.1.0`) … M5 (`v1.0.0`), all ✅, one line each.
14. **License** — MIT; point to the `LICENSE` file.

## Scope

**In scope**
- Full rewrite of `README.md` to the structure above.
- New `LICENSE` file — MIT, author "bgozlinski", year 2026.
- One-character fix in `.env.example`: `DATABASE_URL` port `5432` → `5439`.

**Out of scope (YAGNI)**
- Screenshots / demo-data walkthrough — US-43.
- Any application/test/config change beyond the `.env.example` port digit.
- Translating the README (docs stay English).
- A `CONTRIBUTING.md` / issue templates (solo learning project).

## Roles (per project workflow)

- **Claude prepares:** `README.md`, `LICENSE`, the `.env.example` one-char edit.
- **User runs:** any verification commands they want (e.g. re-running a setup step to
  confirm wording) and all `git`/`gh` commands.

## Verification

1. README renders cleanly (headings, tables, code fences, links resolve).
2. Every command in Getting started / Tests is copy-pasteable and matches the codebase
   (settings module, port 5439, `seed_db`/`createsuperuser` order, API URLs).
3. Internal doc links (to `.Claude/*`, `docs/superpowers/*`) resolve.
4. `LICENSE` present; README badge points to it.
5. `ruff`/`mypy`/`pytest` unaffected (no Python touched) — a sanity `pytest` run stays green.

## Risks / notes

- **Port fix blast radius:** changing `.env.example` only affects new `.env` files
  copied after this change; existing local `.env` files are untouched. If the user
  prefers strict docs-only, drop the edit and rely on the Troubleshooting note.
- **Badge URLs:** CI badge uses the GitHub repo path
  `bgozlinski/cinema-booking-system`; the branch is `main`.
