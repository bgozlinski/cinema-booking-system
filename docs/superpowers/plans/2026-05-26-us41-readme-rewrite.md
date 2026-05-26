# US-41 — README Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sprint-zero `README.md` with a complete, accurate README for the finished M1–M5 project; add an MIT `LICENSE`; fix the `.env.example` Postgres port.

**Architecture:** Docs-only — no TDD. Three files change: `README.md` (full rewrite), `LICENSE` (new), `.env.example` (one digit). All content is verified against the codebase in the spec. Verification = renders cleanly + commands are copy-pasteable + sanity `pytest` stays green (no Python touched).

**Tech Stack:** Markdown · MIT license.

**Role split:** Claude writes all three files. **You run** the verification commands and all `git`/`gh`. Branch is already `docs/M5-readme-rewrite`.

**Spec:** `docs/superpowers/specs/2026-05-26-us41-readme-rewrite-design.md`

---

### Task 1: Add the MIT LICENSE

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Create `LICENSE` (Claude)**

```text
MIT License

Copyright (c) 2026 Bartłomiej Gozliński

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "docs(M5): add MIT LICENSE (US-41)"
```

---

### Task 2: Fix the `.env.example` Postgres port

**Files:**
- Modify: `.env.example` (the `DATABASE_URL` line)

- [ ] **Step 1: Change the port (Claude)**

Replace:
```
DATABASE_URL=postgres://kinomania:kinomania@localhost:5432/kinomania
```
with (port `5432` → `5439`, matching `docker-compose.override.yml`):
```
DATABASE_URL=postgres://kinomania:kinomania@localhost:5439/kinomania
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "fix(M5): align .env.example DB port with compose override 5439 (US-41)"
```

---

### Task 3: Rewrite README.md

**Files:**
- Modify: `README.md` (full replacement)

- [ ] **Step 1: Replace the entire file (Claude)**

Write `README.md` with exactly this content:

````markdown
# KinoMania — Cinema Booking System

[![CI](https://github.com/bgozlinski/cinema-booking-system/actions/workflows/ci.yml/badge.svg)](https://github.com/bgozlinski/cinema-booking-system/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![Django](https://img.shields.io/badge/Django-6.0-092E20.svg)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> A full-stack cinema booking system — browse films, reserve seats, pay with Stripe — built end-to-end in Django + DRF as a learning project.

KinoMania is a learning-grade Django 6 + Django REST Framework application: a public web UI and a mirrored REST API for browsing screenings, booking seats, and paying through Stripe Checkout (sandbox). It was built in five milestones (M1–M5) by a solo developer with Claude as tech-lead/reviewer, with an emphasis on tests, typing, and CI from day one.

## Features

- **Catalog** — movies, halls, and screenings with search and filtering.
- **Booking** — seat reservation with automatic expiry of unpaid (pending) bookings.
- **Payments** — Stripe Checkout (sandbox), signature-verified webhooks, and refunds.
- **Accounts** — email-based registration with email activation (no usernames).
- **REST API** — DRF mirror of the web app with JWT auth and an OpenAPI 3 schema.
- **Internationalisation** — full Polish/English translations with a navbar switcher.
- **Admin** — Django admin for managing the catalog, screenings, and bookings.
- **Quality gates** — pytest (coverage ≥ 80%), ruff, mypy, and bandit, all enforced in CI.

## Tech stack

| Area | Technology |
|---|---|
| Language | Python 3.13 |
| Framework | Django 6 · Django REST Framework |
| Database | PostgreSQL 16 (Docker) |
| Payments | Stripe Checkout (sandbox) |
| Auth (API) | JWT — `djangorestframework-simplejwt` |
| API schema | `drf-spectacular` (OpenAPI 3 + Swagger/ReDoc) |
| Frontend | Django templates · Bootstrap 5 |
| Config | `django-environ` (12-factor `.env`) |
| Tooling | Poetry · pytest · factory_boy · ruff · mypy · bandit |
| CI | GitHub Actions |

## Architecture

**Apps** (`apps/`):

| App | Responsibility |
|---|---|
| `accounts` | Custom email-based `User`, registration, email activation |
| `cinema` | Movies, genres, actors, directors, halls, screenings (+ `selectors.py` read queries) |
| `booking` | Seat reservation flow, booking lifecycle, pending-expiry command (`services.py`) |
| `payments` | Stripe Checkout sessions, webhook handling, refunds (`services.py`) |

**Settings** (`settings/`) are split `base.py` → `dev.py` / `prod.py`, all values read
from the environment via `django-environ`. `manage.py` defaults to `settings.dev`.

**Patterns:** business logic lives in service/selector modules (`*/services.py`,
`cinema/selectors.py`), keeping views thin. The Stripe webhook is hardened:
it verifies the signature (`stripe.Webhook.construct_event`), is idempotent
(`StripeEvent.get_or_create`), and locks the booking row (`select_for_update`).

The REST API mirrors the web app under `/api/v1/` and is documented by an OpenAPI schema.

## Getting started

**Prerequisites:** Python 3.13, [Poetry](https://python-poetry.org/), and Docker
(for PostgreSQL).

```bash
# 1. Clone
git clone https://github.com/bgozlinski/cinema-booking-system.git
cd cinema-booking-system

# 2. Install dependencies (incl. dev tools)
poetry install

# 3. Install git hooks (lint/format/type-check on commit; tests on push)
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push

# 4. Create your env file (see Configuration below). The default DATABASE_URL
#    points at host port 5439, matching docker-compose.override.yml.
cp .env.example .env

# 5. Start PostgreSQL (compose auto-merges the override → host port 5439)
docker compose up -d

# 6. Apply migrations
poetry run python manage.py migrate

# 7. Create an admin user (prompts for email — there are no usernames)
poetry run python manage.py createsuperuser

# 8. Seed demo data (movies, screenings, users, bookings)
poetry run python manage.py seed_db

# 9. Run the dev server
poetry run python manage.py runserver
```

Open <http://localhost:8000> for the site and <http://localhost:8000/admin/> for the admin.

**`seed_db` options:** `--users N` (default 10), `--movies N` (20), `--screenings N`
(100), `--bookings N` (30), `--flush` (delete non-superuser users first),
`--append` (only create missing seed users), `--force` (allow when `DEBUG=False`).

**Stripe webhooks locally** (optional, for testing payment confirmation): install the
[Stripe CLI](https://stripe.com/docs/stripe-cli), then:

```bash
stripe listen --forward-to localhost:8000/payments/webhooks/stripe/
```

Put the printed signing secret in `.env` as `STRIPE_WEBHOOK_SECRET`, and your test
secret key as `STRIPE_API_KEY`.

## Configuration

All configuration is read from `.env` (copy `.env.example`). Key variables:

| Variable | Purpose |
|---|---|
| `DEBUG` | Debug mode (`True` for local dev) |
| `SECRET_KEY` | Django secret key |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `DATABASE_URL` | Postgres DSN — host port **5439** locally |
| `LANGUAGE_CODE` / `TIME_ZONE` | Defaults (`pl` / `Europe/Warsaw`) |
| `STRIPE_API_KEY` | Stripe test secret key (`sk_test_...`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`) |
| `BASE_URL` | Public base URL used in Stripe redirect links |
| `JWT_ACCESS_TOKEN_LIFETIME_MIN` / `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | JWT lifetimes |
| `THROTTLE_ANON` / `THROTTLE_USER` / `THROTTLE_AUTH` | DRF rate limits |
| `DEFAULT_FROM_EMAIL`, `EMAIL_*` | Email (SMTP used by prod; console in dev) |

## Troubleshooting

- **`connection refused` / can't reach Postgres** — the committed
  `docker-compose.override.yml` maps Postgres to host port **5439** (not 5432) to avoid
  clashing with a local Postgres. Ensure `DATABASE_URL` uses `5439` (the shipped
  `.env.example` already does).
- **`database "kinomania" does not exist` / DB not ready** — the container needs a moment
  to pass its healthcheck; check `docker compose ps` and retry `migrate`.
- **Can't log into `/admin/`** — `seed_db` creates only regular users. Create an admin
  with `python manage.py createsuperuser`.
- **`relation ... does not exist` when seeding** — run `migrate` before `seed_db`.
- **Stripe webhook returns 400** — `STRIPE_WEBHOOK_SECRET` is missing or doesn't match the
  secret printed by `stripe listen`.
- **Debug toolbar missing under tests** — intentional: it's disabled whenever pytest is
  loaded, so it can't pollute query-count assertions.

## Tests & quality

```bash
poetry run pytest                                   # full suite + coverage (≥ 80%)
poetry run ruff check .                              # lint
poetry run ruff format --check .                     # format check
poetry run mypy .                                    # type-check
poetry run bandit -c pyproject.toml -r apps settings # security lint
poetry run pre-commit run --all-files                # all hooks at once
```

CI (GitHub Actions) runs ruff + mypy + bandit in a `quality` job and the full pytest
suite (with a Postgres service) in a `test` job on every push and PR.

## REST API

The API is served under `/api/v1/` and authenticated with JWT.

| Endpoint | Description |
|---|---|
| `/api/v1/docs/` | Swagger UI (interactive) |
| `/api/v1/redoc/` | ReDoc |
| `/api/v1/schema/` | Raw OpenAPI 3 schema |

Obtain a token via the JWT auth endpoints, then send `Authorization: Bearer <token>`.

## Internationalisation

The UI ships in Polish and English with a navbar language switcher. Translation
workflow:

```bash
poetry run python manage.py makemessages -l pl -l en
poetry run python manage.py compilemessages
```

## Project structure

```text
cinema-booking-system/
├── apps/
│   ├── accounts/      # custom email user, registration, activation
│   ├── booking/       # reservation flow, services, expiry command
│   ├── cinema/        # movies/screenings/halls, selectors, seed_db command
│   └── payments/      # Stripe services + webhook
├── settings/          # base / dev / prod, urls, api_urls
├── templates/         # Bootstrap 5 templates, error pages
├── locale/            # pl / en translation catalogs
├── static/  media/    # assets / uploads
├── tests/             # pytest suite (factories, mocks)
├── docs/              # specs, plans, security review
├── .Claude/           # requirements, backlog, workflow, conventions
├── docker-compose.yml # PostgreSQL 16
└── pyproject.toml     # deps + tool config
```

## Milestones

- [x] **M1 — Foundation** (`v0.1.0`) — Django bootstrap, custom user, Docker, CI
- [x] **M2 — Catalog web** (`v0.2.0`) — movies, screenings, search, admin
- [x] **M3 — Booking + Stripe** (`v0.3.0`) — reservations, Stripe Checkout, refunds
- [x] **M4 — REST API** (`v0.4.0`) — DRF mirror with JWT + OpenAPI
- [ ] **M5 — Polish** (`v1.0.0`) — i18n PL/EN, error pages, performance, security, docs

## Further documentation

| Doc | Purpose |
|---|---|
| [`.Claude/KinoMania_wymagania_funkcjonalne.md`](.Claude/KinoMania_wymagania_funkcjonalne.md) | Functional requirements (PL) |
| [`.Claude/backlog.md`](.Claude/backlog.md) | Product backlog (User Stories, M1–M5) |
| [`docs/security-review.md`](docs/security-review.md) | Security review (US-42) |
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | Design specifications |
| [`docs/superpowers/plans/`](docs/superpowers/plans/) | Implementation plans |

## License

Released under the [MIT License](LICENSE).
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(M5): rewrite README — setup, troubleshooting, architecture (US-41)"
```

---

### Task 4: Verify and open PR

- [ ] **Step 1: Sanity-check the repo is unaffected (you run)**

```bash
poetry run pytest -q
```
Expected: full suite still green (no Python changed).

- [ ] **Step 2: Eyeball the rendered README (you)**

Open `README.md` in the IDE/GitHub preview. Confirm: badges render, tables/code
fences are well-formed, internal links (`LICENSE`, `.Claude/*`, `docs/*`) resolve,
and the Getting-started commands match your environment.

- [ ] **Step 3: Push + open PR (you run)**

```bash
git push -u origin docs/M5-readme-rewrite
gh pr create --base main \
  --title "docs(M5): README rewrite + MIT license (US-41)" \
  --body "Closes US-41. Full README (setup/troubleshooting/architecture), MIT LICENSE, and .env.example DB-port fix (5432→5439)."
```

---

## Self-review

- **Spec coverage:** LICENSE (Task 1), `.env.example` port fix (Task 2), all 14 README
  sections + Documentation pointer (Task 3), verification + PR (Task 4). Every spec
  section maps to a task.
- **Placeholders:** none — full LICENSE text and full README Markdown are inline; no TBD.
- **Fact consistency:** webhook path `/payments/webhooks/stripe/`, API base `/api/v1/`,
  port `5439`, `settings.dev` default, email-only superuser, tags `v0.1.0`–`v0.4.0`
  (M5 → `v1.0.0` pending) — all match the verified codebase facts in the spec.
