# KinoMania — Cinema Booking System

> **Status:** Sprint zero (docs bootstrap) — application code arrives in M1.

## What is this

KinoMania is a learning-grade Django + DRF cinema booking system with Stripe sandbox payments. Built end-to-end in milestones M1..M5 by a solo developer (bartek) with Claude (Opus 4.7) as Tech Lead / Reviewer / Coach.

**Tech:** Python 3.13 · Django 6 · Django REST Framework · PostgreSQL 16 (docker-compose) · Stripe Checkout (sandbox) · Bootstrap 5 · pytest + factory_boy · ruff + mypy · GitHub Actions CI

## Documentation

| Doc | Purpose |
|---|---|
| [`.Claude/KinoMania_wymagania_funkcjonalne.md`](.Claude/KinoMania_wymagania_funkcjonalne.md) | Functional requirements (PL) — FR-01..FR-24 |
| [`.Claude/workflow_scrum_agile.md`](.Claude/workflow_scrum_agile.md) | SCRUM/AGILE workflow definition + role split |
| [`.Claude/backlog.md`](.Claude/backlog.md) | Product backlog (43 User Stories, M1..M5) |
| [`.Claude/tooling_stack.md`](.Claude/tooling_stack.md) | Tooling configurations (ruff/mypy/pytest/CI) |
| [`.Claude/commit_convention.md`](.Claude/commit_convention.md) | Commit + PR + branch conventions |
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | Design specifications |
| [`docs/superpowers/plans/`](docs/superpowers/plans/) | Implementation plans per milestone |

## Setup

> Application setup will be added in M1 (US-01). For now, this repo holds documentation only.

## Local development hooks

```bash
poetry install
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push
```

`ruff` (lint + format), `mypy`, and file checks run on every commit; `pytest` runs on every push.


## Milestones

- [ ] **M1 — Foundation** (`v0.1.0`) — Django bootstrap, custom User, Docker, CI
- [ ] **M2 — Catalog web** (`v0.2.0`) — Movies, screenings, search, admin
- [ ] **M3 — Booking + Stripe** (`v0.3.0`) — Reservations, Stripe Checkout, refunds
- [ ] **M4 — REST API** (`v0.4.0`) — Full DRF mirror with JWT + OpenAPI
- [ ] **M5 — Polish** (`v1.0.0`) — i18n PL/EN, error pages, performance, README rewrite

## License

TBD (private learning project).
