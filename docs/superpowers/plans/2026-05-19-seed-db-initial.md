# `seed_db` Initial Implementation Plan (US-08 / FR-13 — M1 scope)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py` commands, settings edits, app scaffolding); **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Implement `python manage.py seed_db` for M1 — seed 10 users (8 active + 2 inactive) with deterministic emails for manual smoke testing of the US-07 auth flow. Genres/Halls/Movies dochodzą w US-10/US-16.

**Architecture:** New minimal `apps/cinema/` package (no models yet) with `management/commands/seed_db.py`. Three orthogonal flag axes: `--flush|--append` (data behavior), `--force` (DEBUG bypass), `--users N` (count). All work atomic via `transaction.atomic()`. Inline `Faker("pl_PL")` (no test-tree imports). Full design in `docs/superpowers/specs/2026-05-19-seed-db-initial-design.md`.

**Tech Stack:** Django 6 (custom `accounts.User`, `USERNAME_FIELD="email"`), pytest-django, Faker (already in `[dependency-groups] dev`). PostgreSQL via Docker Compose locally.

**Branch:** `feat/FR-13-seed-db-initial` (per backlog US-08).

---

## Pre-flight checklist (read these first)

- [ ] `docs/superpowers/specs/2026-05-19-seed-db-initial-design.md` — design decisions
- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-13 (current location reference)
- [ ] `.Claude/backlog.md` US-08 (current AC list — będzie updated w Task 1)
- [ ] `.Claude/commit_convention.md` — Conventional Commits with FR-13 scope
- [ ] `apps/accounts/{models,managers}.py` — existing User model (custom manager `create_user(email, password, ...)`)
- [ ] `settings/base.py` — current `INSTALLED_APPS` + `env.str()` pattern
- [ ] `tests/accounts/factories.py` — `UserFactory` (used in 3 tests as helper for pre-existing users)

---

## File structure (what we'll create/modify)

```
apps/cinema/                                ★ NEW package (no models in US-08)
├── __init__.py                             ★ NEW — empty
├── apps.py                                 ★ NEW — CinemaConfig
├── migrations/
│   └── __init__.py                         ★ NEW — empty (models in US-10)
└── management/
    ├── __init__.py                         ★ NEW — empty
    └── commands/
        ├── __init__.py                     ★ NEW — empty
        └── seed_db.py                      ★ NEW — main command (FR-13, M1)

tests/cinema/                               ★ NEW directory
├── __init__.py                             ★ NEW — empty
└── test_seed_db.py                         ★ NEW — 10 tests per spec §6.1

settings/base.py                            ✎ + INSTALLED_APPS append, SEED_DB_DEFAULT_PASSWORD

.env.example                                ✎ + commented SEED_DB_DEFAULT_PASSWORD hint
.Claude/backlog.md                          ✎ US-08 AC updated, US-16 scope expanded
.Claude/KinoMania_wymagania_funkcjonalne.md ✎ FR-13 path + M1 sub-note
memory/project_kinomania_bootstrap.md       ✎ after merge — bump to 8/9 done
```

---

## Task 1: Update docs (backlog + FR-13 path) and create branch

**Files:**
- Modify: `.Claude/backlog.md` (US-08 AC, US-16 row, status board)
- Modify: `.Claude/KinoMania_wymagania_funkcjonalne.md` (§FR-13)

**Why first:** Backlog is the source of truth for AC. Spec-first, code-second. Same pattern as PR #7 — first commit updates docs, then implementation follows.

- [ ] **Step 1: Create and switch to feature branch**

```bash
git checkout -b feat/FR-13-seed-db-initial
```

- [ ] **Step 2: Update US-08 section in `.Claude/backlog.md`**

Locate `### US-08 — Komenda \`seed_db\` (initial — Genres + Halls + Users)` (around line 209). Replace the **title** to `### US-08 — Komenda \`seed_db\` (initial — Users only)`. Replace the **Zakres M1** line with:

```markdown
**Zakres M1:** Tylko Users (10 = 8 active + 2 inactive, deterministyczne emaile). Genres+Halls przeniesione do US-16 razem z Movies/Screenings (modele Genre/Hall nie istnieją do US-10).
```

Replace **Acceptance Criteria** block with:

```markdown
**Acceptance Criteria:**
- **GIVEN** `poetry run python manage.py seed_db` **WHEN** baza jest pusta **THEN** tworzy 10 users (8 active + 2 inactive) z hasłem `test1234`, emaile `seed.user{i}@kinomania.local` dla i=1..10, inactive na indeksach 9-10.
- **GIVEN** `--flush` **WHEN** istnieją non-superuser users **THEN** usuwa ich wszystkich (zachowując superuserów), potem tworzy seed.
- **GIVEN** `--append` **WHEN** istnieją niektórzy seed userzy **THEN** brakujący są tworzeni, istniejący skip z info do stdout.
- **GIVEN** `--flush --append` razem **THEN** `CommandError("--flush and --append are mutually exclusive")`.
- **GIVEN** non-empty DB bez `--flush` i `--append` **THEN** `CommandError("Database not empty...")` z instrukcją.
- **GIVEN** `DEBUG=False` w env **WHEN** uruchamiam bez `--force` **THEN** `CommandError("seed_db is disabled when DEBUG=False...")`.
- **GIVEN** `--force` **WHEN** `DEBUG=False` **THEN** ostrzeżenie na stderr + kontynuuje.
- **GIVEN** `--users 0` lub ujemny **THEN** `CommandError("--users must be >= 1")`.
```

Replace **DoR** line with `**DoR:** [✅] story / [✅] AC / [✅] zależności / [✅] szkielet od Claude (spec + plan)`.

Replace **Tests-first** block with:

```markdown
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
```

Add after Tests-first block:

```markdown
- **Spec:** [`docs/superpowers/specs/2026-05-19-seed-db-initial-design.md`](../docs/superpowers/specs/2026-05-19-seed-db-initial-design.md)
- **Plan:** [`docs/superpowers/plans/2026-05-19-seed-db-initial.md`](../docs/superpowers/plans/2026-05-19-seed-db-initial.md)
```

- [ ] **Step 3: Update US-16 row in `.Claude/backlog.md` (§2 M2 table)**

Find row `| US-16 | Rozbudowa \`seed_db\` — Movies, Screenings | FR-13 | S | \`feat/FR-13-seed-db-movies\` |`. Replace with:

```markdown
| US-16 | Rozbudowa `seed_db` — Genres, Halls, Movies, Screenings | FR-13 | M | `feat/FR-13-seed-db-movies` |
```

- [ ] **Step 4: Update status board in `.Claude/backlog.md` (§7)**

Replace the table with:

```markdown
| Status | US |
|---|---|
| **In Progress (WIP=1)** | **US-08** (seed_db initial — Users only) |
| **Ready (DoR ✅)** | _none_ |
| **Backlog** | US-09..US-43 |
| **Done** | **US-01..US-07** ✅✅✅✅✅✅✅ |
```

Update the milestone-summary line below the table:

```markdown
**Bieżący milestone:** M1 — Foundation (`v0.1.0`). 7/9 US zmergowanych, US-08 in progress. US-08 (FR-13, M1) zwężone do Users only — Genres+Halls przesunięte do US-16 (M2) gdy modele Genre/Hall będą istniały po US-10. Następny task po US-08: US-09 (baseline templates extract + home view).
```

- [ ] **Step 5: Update `.Claude/KinoMania_wymagania_funkcjonalne.md` FR-13**

Find `### FR-13 — Komenda management \`seed_db\`` (around line 358). Update the **Lokalizacja** line:

```markdown
**Lokalizacja:** `apps/cinema/management/commands/seed_db.py` *(zgodnie z decyzją strukturalną 2026-05-18 — apps żyją pod `apps/<nazwa>/`)*
```

Add a sub-section directly under FR-13 header (before existing **Wywołanie**):

```markdown
**Realizacja milestone'owa:**
- **M1 (US-08):** Users only — 10 users (8 active + 2 inactive), flagi `--flush|--append`, `--force`, `--users N`. Spec: `docs/superpowers/specs/2026-05-19-seed-db-initial-design.md`.
- **M2 (US-16):** + Genres, Halls, Movies, Actors, Directors, Screenings.
- **M3 (US-18+):** + Bookings z 5% PENDING dla testowania `expire_pending_bookings`.
```

- [ ] **Step 6: Verify diff looks right**

```bash
git diff .Claude/backlog.md .Claude/KinoMania_wymagania_funkcjonalne.md
```

Expected: 4 sections of `.Claude/backlog.md` changed (US-08 body, US-16 row, status board, milestone summary), FR-13 location + new sub-section.

- [ ] **Step 7: Commit**

```bash
git add .Claude/backlog.md .Claude/KinoMania_wymagania_funkcjonalne.md
git commit -m "$(cat <<'EOF'
docs(infra): scope US-08 to users-only, push genres/halls to US-16

US-08 AC originally included Genres and Halls, but those models won't
exist until US-10 (M2). Narrow US-08 to Users only (10 = 8 active + 2
inactive, deterministic emails) and expand US-16 to include Genres +
Halls alongside Movies + Screenings. Update FR-13 path to apps/cinema/
per the 2026-05-18 structural decision.

Spec: docs/superpowers/specs/2026-05-19-seed-db-initial-design.md
Plan: docs/superpowers/plans/2026-05-19-seed-db-initial.md
EOF
)"
```

---

## Task 2: Scaffold `apps/cinema/` package

**Files:**
- Create: `apps/cinema/__init__.py`
- Create: `apps/cinema/apps.py`
- Create: `apps/cinema/migrations/__init__.py`
- Create: `apps/cinema/management/__init__.py`
- Create: `apps/cinema/management/commands/__init__.py`
- Modify: `settings/base.py` (where `INSTALLED_APPS` lives)

**Why:** Django needs the package skeleton before it discovers any management commands. No models yet — those come in US-10.

- [ ] **Step 1: Create empty package files**

User runs (Git Bash) or types each file via PyCharm:

```bash
mkdir -p apps/cinema/migrations apps/cinema/management/commands
touch apps/cinema/__init__.py
touch apps/cinema/migrations/__init__.py
touch apps/cinema/management/__init__.py
touch apps/cinema/management/commands/__init__.py
```

- [ ] **Step 2: Write `apps/cinema/apps.py` (reference for user)**

```python
from django.apps import AppConfig


class CinemaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cinema"
```

- [ ] **Step 3: Add `apps.cinema` to `INSTALLED_APPS`**

Open `settings/base.py`. Find the `INSTALLED_APPS` list and add `"apps.cinema"` directly after `"apps.accounts"`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.cinema",   # ← new
]
```

- [ ] **Step 4: Verify Django picks up the new app**

```bash
poetry run python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

Also verify the command is discovered:

```bash
poetry run python manage.py help 2>&1 | grep -i seed
```

Expected: empty (no seed_db yet — but `[cinema]` section may appear empty). If `manage.py help` errors out, it means import failed somewhere. Fix before proceeding.

- [ ] **Step 5: Commit**

```bash
git add apps/cinema/ settings/base.py
git commit -m "chore(FR-13): scaffold apps/cinema package skeleton

Adds apps/cinema/ with apps.py + management/commands/ subpackage,
ready for seed_db (US-08) and models (US-10). Adds 'apps.cinema'
to INSTALLED_APPS. No models, no migrations content yet."
```

---

## Task 3: Add `SEED_DB_DEFAULT_PASSWORD` setting

**Files:**
- Modify: `settings/base.py`
- Modify: `.env.example`

**Why:** The command reads this setting. Make it overridable via env var, default to spec value `test1234`.

- [ ] **Step 1: Add setting in `base.py`**

Below the existing env-driven settings (e.g., near `SECRET_KEY`, `DEBUG`, `DATABASES`), add:

```python
SEED_DB_DEFAULT_PASSWORD = env.str("SEED_DB_DEFAULT_PASSWORD", default="test1234")
```

- [ ] **Step 2: Document in `.env.example`**

Add to `.env.example` (near other optional settings):

```bash
# Optional override for seed_db default password (dev only)
# SEED_DB_DEFAULT_PASSWORD=test1234
```

- [ ] **Step 3: Verify setting loads**

```bash
poetry run python manage.py shell -c "from django.conf import settings; print(settings.SEED_DB_DEFAULT_PASSWORD)"
```

Expected: `test1234`

- [ ] **Step 4: Commit**

```bash
git add settings/base.py .env.example
git commit -m "feat(FR-13): add SEED_DB_DEFAULT_PASSWORD setting (default test1234)"
```

---

## Task 4: First test + skeleton command with DEBUG guard

**Files:**
- Create: `tests/cinema/__init__.py` (empty)
- Create: `tests/cinema/test_seed_db.py`
- Create: `apps/cinema/management/commands/seed_db.py`

**Why:** TDD start. The DEBUG guard is the cheapest gate to test and forces us to scaffold `Command.handle()`.

- [ ] **Step 1: Create empty `tests/cinema/__init__.py`**

```bash
mkdir -p tests/cinema
touch tests/cinema/__init__.py
```

- [ ] **Step 2: Write the failing test (Claude — paste verbatim)**

Create `tests/cinema/test_seed_db.py` with:

```python
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

User = get_user_model()


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_seed_db_blocked_when_debug_false_without_force():
    stdout = StringIO()
    stderr = StringIO()

    with pytest.raises(CommandError, match="disabled when DEBUG=False"):
        call_command("seed_db", stdout=stdout, stderr=stderr)

    assert User.objects.count() == 0
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: `ERROR` or `FAIL` — `Unknown command: 'seed_db'` (Django doesn't see it yet because `seed_db.py` doesn't exist).

- [ ] **Step 4: Write minimal `seed_db.py` (reference for user)**

```python
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Seed the database with dev test data (M1: users only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow seeding when DEBUG=False (dev only).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_db is disabled when DEBUG=False. "
                "Use --force to override (DEV ONLY)."
            )
        # body coming in Task 6
```

- [ ] **Step 5: Run the test again**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: PASS.

- [ ] **Step 6: Run quality gates**

```bash
poetry run ruff check apps/cinema tests/cinema
poetry run ruff format --check apps/cinema tests/cinema
poetry run mypy apps/cinema tests/cinema
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/__init__.py tests/cinema/test_seed_db.py
git commit -m "feat(FR-13): seed_db base command with DEBUG guard and --force flag"
```

---

## Task 5: `--force` bypasses production guard

**Files:**
- Modify: `apps/cinema/management/commands/seed_db.py`
- Modify: `tests/cinema/test_seed_db.py`

- [ ] **Step 1: Add test (Claude — paste verbatim, append to existing file)**

Append to `tests/cinema/test_seed_db.py`:

```python
@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_seed_db_force_bypasses_production_guard():
    stdout = StringIO()
    stderr = StringIO()

    call_command("seed_db", "--force", stdout=stdout, stderr=stderr)

    assert "WARNING" in stderr.getvalue()
    assert User.objects.count() == 10
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_force_bypasses_production_guard -v
```

Expected: FAIL — either no users created yet (body not implemented) or no WARNING on stderr.

> **Note:** This test will keep failing until Task 6 implements the seed loop. That's expected — we'll keep it failing as a forcing function for Task 6 and verify both pass together. Alternative: skip with `pytest.mark.xfail(reason="seed loop in Task 6")` and remove the marker in Task 6.

- [ ] **Step 3: Add `--force` warning to `handle()` (reference)**

In `seed_db.py`, modify `handle()`:

```python
def handle(self, *args, **options):
    if not settings.DEBUG and not options["force"]:
        raise CommandError(
            "seed_db is disabled when DEBUG=False. "
            "Use --force to override (DEV ONLY)."
        )
    if not settings.DEBUG and options["force"]:
        self.stderr.write(
            self.style.WARNING(
                "Running seed_db in non-DEBUG environment. "
                "This is intended for dev only."
            )
        )
    # body coming in Task 6
```

- [ ] **Step 4: Verify previous test still passes (no regression)**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_blocked_when_debug_false_without_force -v
```

Expected: PASS.

- [ ] **Step 5: Skip the force test until Task 6 (recommended)**

Add `@pytest.mark.xfail(reason="seed loop implemented in Task 6", strict=True)` above the force test for now. Remove the marker in Task 6 Step 6.

- [ ] **Step 6: Commit**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
git commit -m "feat(FR-13): seed_db --force flag prints warning and bypasses DEBUG guard"
```

---

## Task 6: Default seed loop — 10 users, 8/2 split, deterministic emails

**Files:**
- Modify: `apps/cinema/management/commands/seed_db.py`
- Modify: `tests/cinema/test_seed_db.py`

**Why:** Now we implement the happy path. Most tests gate on this body existing.

- [ ] **Step 1: Add four tests (Claude — paste verbatim, append)**

```python
@pytest.mark.django_db
def test_seed_db_creates_default_counts():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert User.objects.count() == 10
    assert User.objects.filter(is_active=True).count() == 8
    assert User.objects.filter(is_active=False).count() == 2


@pytest.mark.django_db
def test_seed_db_emails_are_deterministic():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    expected_emails = {f"seed.user{i}@kinomania.local" for i in range(1, 11)}
    assert set(User.objects.values_list("email", flat=True)) == expected_emails

    inactive_emails = set(
        User.objects.filter(is_active=False).values_list("email", flat=True)
    )
    assert inactive_emails == {
        "seed.user9@kinomania.local",
        "seed.user10@kinomania.local",
    }


@pytest.mark.django_db
def test_seed_db_password_is_hashed():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    user = User.objects.get(email="seed.user1@kinomania.local")
    assert user.check_password("test1234") is True
    assert user.password.startswith("pbkdf2_")


@pytest.mark.django_db
def test_seed_db_no_staff_no_super():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert User.objects.filter(is_staff=True).count() == 0
    assert User.objects.filter(is_superuser=True).count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: 4 new tests FAIL — `User.objects.count() == 0` (no body yet). The xfail-marked `test_seed_db_force_bypasses_production_guard` still shows XFAIL.

- [ ] **Step 3: Implement seed loop (reference for user)**

In `seed_db.py`, add imports and update `handle()`:

```python
from math import floor

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from faker import Faker

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with dev test data (M1: users only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow seeding when DEBUG=False (dev only).",
        )
        parser.add_argument(
            "--users",
            type=int,
            default=10,
            help="Number of users to seed (default 10).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_db is disabled when DEBUG=False. "
                "Use --force to override (DEV ONLY)."
            )
        if not settings.DEBUG and options["force"]:
            self.stderr.write(
                self.style.WARNING(
                    "Running seed_db in non-DEBUG environment. "
                    "This is intended for dev only."
                )
            )

        n = options["users"]
        if n < 1:
            raise CommandError("--users must be >= 1")

        active_count = floor(n * 0.8)
        inactive_count = n - active_count
        fake = Faker("pl_PL")
        password = settings.SEED_DB_DEFAULT_PASSWORD

        with transaction.atomic():
            for i in range(1, n + 1):
                user = User(
                    email=f"seed.user{i}@kinomania.local",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    is_active=(i <= active_count),
                    is_staff=False,
                    is_superuser=False,
                )
                user.set_password(password)
                user.save()

        inactive_emails = [
            f"seed.user{i}@kinomania.local"
            for i in range(active_count + 1, n + 1)
        ]
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {n} users ({active_count} active, {inactive_count} inactive). "
                f"Default password: {password}."
            )
        )
        if inactive_emails:
            self.stdout.write("Inactive accounts:")
            for email in inactive_emails:
                self.stdout.write(f"  {email}")
```

- [ ] **Step 4: Remove the xfail marker from Task 5's force test**

In `tests/cinema/test_seed_db.py`, remove the `@pytest.mark.xfail(...)` line above `test_seed_db_force_bypasses_production_guard`.

- [ ] **Step 5: Run all tests**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: 6 PASS (1 DEBUG guard + 1 force + 4 default seed). 0 fail, 0 xfail.

- [ ] **Step 6: Quality gates**

```bash
poetry run ruff check apps/cinema tests/cinema
poetry run ruff format --check apps/cinema tests/cinema
poetry run mypy apps/cinema tests/cinema
```

Expected: all pass.

- [ ] **Step 7: Manual smoke test (optional but recommended)**

```bash
docker compose up -d db
poetry run python manage.py migrate
poetry run python manage.py seed_db
```

Expected stdout:
```
Seeded 10 users (8 active, 2 inactive). Default password: test1234.
Inactive accounts:
  seed.user9@kinomania.local
  seed.user10@kinomania.local
```

Verify in admin (`/admin/`) or via shell:
```bash
poetry run python manage.py shell -c "from apps.accounts.models import User; print(User.objects.count())"
```

Clean up if needed:
```bash
poetry run python manage.py shell -c "from apps.accounts.models import User; User.objects.filter(email__startswith='seed.user').delete()"
```

- [ ] **Step 8: Commit**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
git commit -m "feat(FR-13): seed_db creates 10 users (8 active + 2 inactive)

Deterministic emails (seed.user{i}@kinomania.local), Faker(pl_PL) for
names, PBKDF2 password from settings.SEED_DB_DEFAULT_PASSWORD. Atomic
transaction. --users N flag for custom count (validated >= 1)."
```

---

## Task 7: Non-empty DB guard (without `--flush`/`--append`)

**Files:**
- Modify: `apps/cinema/management/commands/seed_db.py`
- Modify: `tests/cinema/test_seed_db.py`

- [ ] **Step 1: Add test (Claude — paste verbatim, append)**

```python
@pytest.mark.django_db
def test_seed_db_blocks_on_non_empty_db_without_flags():
    User.objects.create_user(email="existing@example.com", password="x" * 12)

    with pytest.raises(CommandError, match="Database not empty"):
        call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert User.objects.filter(email="existing@example.com").exists()
    assert User.objects.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_blocks_on_non_empty_db_without_flags -v
```

Expected: FAIL — no guard, seed proceeds and creates 10 users, total 11.

- [ ] **Step 3: Add guard in `handle()` (reference)**

Add after the `--users` validation, before `transaction.atomic()`:

```python
non_super_count = User.objects.filter(is_superuser=False).count()
if non_super_count > 0:
    raise CommandError(
        f"Database not empty (found {non_super_count} non-superuser user(s)). "
        f"Use --flush to wipe non-superusers or --append to add only missing."
    )
```

- [ ] **Step 4: Run all tests**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: 7 PASS. No regressions.

- [ ] **Step 5: Commit**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
git commit -m "feat(FR-13): seed_db blocks on non-empty DB without --flush/--append"
```

---

## Task 8: `--flush` wipes non-superusers, preserves superusers

**Files:**
- Modify: `apps/cinema/management/commands/seed_db.py`
- Modify: `tests/cinema/test_seed_db.py`

- [ ] **Step 1: Add test (Claude — paste verbatim, append)**

```python
@pytest.mark.django_db
def test_seed_db_flush_preserves_superuser_wipes_others():
    User.objects.create_superuser(email="admin@example.com", password="x" * 12)
    User.objects.create_user(email="user1@example.com", password="x" * 12)
    User.objects.create_user(email="user2@example.com", password="x" * 12)

    call_command("seed_db", "--flush", stdout=StringIO(), stderr=StringIO())

    assert User.objects.filter(email="admin@example.com").exists()
    assert not User.objects.filter(email="user1@example.com").exists()
    assert not User.objects.filter(email="user2@example.com").exists()
    seed_count = User.objects.filter(email__startswith="seed.user").count()
    assert seed_count == 10
    assert User.objects.count() == 11  # 10 seed + 1 superuser
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_flush_preserves_superuser_wipes_others -v
```

Expected: FAIL — `--flush` flag not recognized (or non-empty guard rejects).

- [ ] **Step 3: Add `--flush` flag and wire logic (reference)**

In `add_arguments()`, add:

```python
parser.add_argument(
    "--flush",
    action="store_true",
    help="Delete non-superuser users before seeding.",
)
```

In `handle()`, replace the non-empty guard with this branching logic (still before `transaction.atomic()`):

```python
non_super_count = User.objects.filter(is_superuser=False).count()
if options["flush"]:
    pass  # delete happens inside atomic below
elif non_super_count > 0:
    raise CommandError(
        f"Database not empty (found {non_super_count} non-superuser user(s)). "
        f"Use --flush to wipe non-superusers or --append to add only missing."
    )
```

Then inside `transaction.atomic()`, at the top of the block (before the for loop):

```python
with transaction.atomic():
    if options["flush"]:
        User.objects.filter(is_superuser=False).delete()
    for i in range(1, n + 1):
        # ... existing loop
```

- [ ] **Step 4: Run all tests**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
git commit -m "feat(FR-13): seed_db --flush wipes non-superusers before seeding"
```

---

## Task 9: `--append` skip-existing (idempotent)

**Files:**
- Modify: `apps/cinema/management/commands/seed_db.py`
- Modify: `tests/cinema/test_seed_db.py`

- [ ] **Step 1: Add test (Claude — paste verbatim, append)**

```python
@pytest.mark.django_db
def test_seed_db_append_idempotent_skip_existing():
    for i in [1, 2, 3]:
        User.objects.create_user(
            email=f"seed.user{i}@kinomania.local", password="x" * 12
        )
    original_joined = {
        u.email: u.date_joined
        for u in User.objects.filter(email__startswith="seed.user")
    }

    stdout = StringIO()
    call_command("seed_db", "--append", stdout=stdout, stderr=StringIO())

    assert User.objects.count() == 10
    assert User.objects.filter(email__startswith="seed.user").count() == 10
    for i in [1, 2, 3]:
        email = f"seed.user{i}@kinomania.local"
        assert User.objects.get(email=email).date_joined == original_joined[email]
    out = stdout.getvalue()
    assert "Skipping existing: seed.user1@kinomania.local" in out
    assert "Appended 7 users (3 skipped)" in out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_append_idempotent_skip_existing -v
```

Expected: FAIL — `--append` flag not recognized.

- [ ] **Step 3: Add `--append` flag and wire logic (reference)**

In `add_arguments()`, add:

```python
parser.add_argument(
    "--append",
    action="store_true",
    help="Create only missing seed users (skip existing by email).",
)
```

In `handle()`, update the branching logic before `transaction.atomic()`:

```python
non_super_count = User.objects.filter(is_superuser=False).count()
if options["flush"] or options["append"]:
    pass
elif non_super_count > 0:
    raise CommandError(
        f"Database not empty (found {non_super_count} non-superuser user(s)). "
        f"Use --flush to wipe non-superusers or --append to add only missing."
    )
```

Restructure the seed loop body to handle append mode (replace the existing `transaction.atomic()` block):

```python
created_count = 0
skipped_count = 0
with transaction.atomic():
    if options["flush"]:
        User.objects.filter(is_superuser=False).delete()
    for i in range(1, n + 1):
        email = f"seed.user{i}@kinomania.local"
        if options["append"] and User.objects.filter(email=email).exists():
            self.stdout.write(f"Skipping existing: {email}")
            skipped_count += 1
            continue
        user = User(
            email=email,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            is_active=(i <= active_count),
            is_staff=False,
            is_superuser=False,
        )
        user.set_password(password)
        user.save()
        created_count += 1
```

And update the summary stdout block:

```python
if options["append"]:
    self.stdout.write(
        self.style.SUCCESS(
            f"Appended {created_count} users ({skipped_count} skipped). "
            f"Default password: {password}."
        )
    )
else:
    inactive_emails = [
        f"seed.user{i}@kinomania.local"
        for i in range(active_count + 1, n + 1)
    ]
    self.stdout.write(
        self.style.SUCCESS(
            f"Seeded {created_count} users ({active_count} active, "
            f"{inactive_count} inactive). Default password: {password}."
        )
    )
    if inactive_emails:
        self.stdout.write("Inactive accounts:")
        for email in inactive_emails:
            self.stdout.write(f"  {email}")
```

- [ ] **Step 4: Run all tests**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
git commit -m "feat(FR-13): seed_db --append skips existing seed users (idempotent)"
```

---

## Task 10: Mutex `--flush` and `--append`

**Files:**
- Modify: `apps/cinema/management/commands/seed_db.py`
- Modify: `tests/cinema/test_seed_db.py`

- [ ] **Step 1: Add test (Claude — paste verbatim, append)**

```python
@pytest.mark.django_db
def test_seed_db_flush_and_append_mutually_exclusive():
    with pytest.raises(CommandError, match="mutually exclusive"):
        call_command(
            "seed_db",
            "--flush",
            "--append",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert User.objects.count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/cinema/test_seed_db.py::test_seed_db_flush_and_append_mutually_exclusive -v
```

Expected: FAIL — both flags currently accepted, seed runs.

- [ ] **Step 3: Add mutex guard (reference)**

In `handle()`, add right after the DEBUG guard block (before `--users` validation):

```python
if options["flush"] and options["append"]:
    raise CommandError("--flush and --append are mutually exclusive")
```

- [ ] **Step 4: Run all tests**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
git commit -m "feat(FR-13): seed_db rejects --flush and --append used together"
```

---

## Task 11: Coverage check + final manual smoke

**Files:** none modified.

**Why:** Verify the spec's 90% target on `seed_db.py` and 80% global threshold hold. Sanity check the command end-to-end manually.

- [ ] **Step 1: Run full test suite with coverage**

```bash
poetry run pytest --cov=apps --cov=tests --cov-report=term-missing
```

Expected: all tests pass (accounts + cinema), `apps/cinema/management/commands/seed_db.py` coverage ≥ 90%, total coverage ≥ 80%.

- [ ] **Step 2: Manual smoke — full happy path**

```bash
docker compose up -d db
poetry run python manage.py migrate
poetry run python manage.py seed_db
poetry run python manage.py shell -c "from apps.accounts.models import User; print(User.objects.count(), User.objects.filter(is_active=False).count())"
```

Expected: `10 2`.

- [ ] **Step 3: Manual smoke — `--flush` and `--append`**

```bash
poetry run python manage.py seed_db --flush
poetry run python manage.py seed_db --append
poetry run python manage.py shell -c "from apps.accounts.models import User; User.objects.filter(email__startswith='seed.user').delete()"
```

Each command should succeed; `--append` after `--flush` should report `Appended 0 users (10 skipped)`.

- [ ] **Step 4: Verify login with seeded account (browser smoke)**

```bash
poetry run python manage.py seed_db
poetry run python manage.py runserver
```

Open `http://localhost:8000/accounts/login/`. Login with `seed.user1@kinomania.local` / `test1234`. Expected: success. Try `seed.user9@kinomania.local` / `test1234`. Expected: generic "invalid credentials" (inactive account, US-07 behavior).

- [ ] **Step 5: Run quality gates one more time**

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
```

Expected: all green.

- [ ] **Step 6: No commit needed** (verification only).

---

## Task 12: Mark US-08 done and update memory

**Files:**
- Modify: `.Claude/backlog.md` (status board)
- Modify: `memory/project_kinomania_bootstrap.md` (after merge — Claude's job, propose to user)

**Why:** Close the loop. Backlog board reflects reality.

- [ ] **Step 1: Update status board (`.Claude/backlog.md` §7)**

Replace the table with:

```markdown
| Status | US |
|---|---|
| **In Progress (WIP=1)** | _none_ |
| **Ready (DoR ✅)** | **US-09** (baseline templates extract + home view — zależy od US-07, US-08) |
| **Backlog** | US-10..US-43 |
| **Done** | **US-01..US-08** ✅✅✅✅✅✅✅✅ |
```

Update the milestone-summary line:

```markdown
**Bieżący milestone:** M1 — Foundation (`v0.1.0`). 8/9 US zmergowanych. US-08 dostarczyło `seed_db` command dla Users (FR-13, M1 scope). Ostatni task M1: US-09 (baseline templates extract `_base.html` → globalne `templates/base.html` + home view `/`).
```

- [ ] **Step 2: Commit on the feature branch**

```bash
git add .Claude/backlog.md
git commit -m "docs(FR-13): mark US-08 done, queue US-09 as next M1 task"
```

- [ ] **Step 3: Push branch and open PR**

```bash
git push -u origin feat/FR-13-seed-db-initial
gh pr create --title "feat(FR-13): seed_db initial command (US-08, M1 scope)" --body "$(cat <<'EOF'
## Summary
- Adds `apps/cinema/` package (no models yet — US-10) with `management/commands/seed_db.py`
- Seeds 10 users (8 active + 2 inactive) with deterministic emails `seed.user{i}@kinomania.local`
- Flags: `--flush` (wipe non-supers), `--append` (idempotent skip), `--force` (bypass DEBUG guard), `--users N`
- 10 tests in `tests/cinema/test_seed_db.py` covering all branches; ≥90% local coverage on `seed_db.py`
- Backlog: US-08 narrowed from "Genres + Halls + Users" to "Users only"; Genres+Halls moved to US-16

## Closes
US-08 (M1)

## Spec & Plan
- `docs/superpowers/specs/2026-05-19-seed-db-initial-design.md`
- `docs/superpowers/plans/2026-05-19-seed-db-initial.md`

## Test plan
- [x] `pytest tests/cinema/ -v` — all 10 tests pass
- [x] `pytest --cov-fail-under=80` — global coverage threshold holds
- [x] `ruff check . && ruff format --check . && mypy .` — quality gates green
- [x] Manual: `seed_db` on empty DB → 10 users seeded; `--flush` re-runs cleanly; `--append` is idempotent
- [x] Manual: login with `seed.user1@kinomania.local` / `test1234` works; `seed.user9@kinomania.local` (inactive) gets generic error

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: After merge — update memory (Claude proposes)**

After PR is merged to main, Claude proposes updating `memory/project_kinomania_bootstrap.md`:
- Bump M1 progress: `7/9 → 8/9 US done`
- Update "Następny task" to US-09
- Note the structural addition: `apps/cinema/` package created (still no models)

This is Claude's job per role-division — Claude edits memory directly, user reviews.

---

## Out-of-band notes

- **Faker import lazy:** Django lazy-loads `management/commands/` modules. `Faker` import in `seed_db.py` doesn't break prod env (the command is never invoked there). The DEBUG guard is belt-and-suspenders.
- **Test ordering:** Tests don't depend on each other (every test has fresh DB via `@pytest.mark.django_db`). pytest can run them in any order.
- **`UserManager.create_user` vs `User()` + `set_password()`:** The reference impl uses the latter for explicit control over `is_active`. The custom `UserManager.create_user` exists (US-06) — using it instead requires checking whether it accepts `is_active=False` kwarg. Either works; pick what reads cleaner when you implement.
- **`User.objects.create_user(email, password)` in tests:** The tests use the manager method directly. This relies on US-06's `UserManager.create_user(email, password=None, **extra_fields)` signature — verify it accepts a positional `password` or convert to kwargs (`User.objects.create_user(email="x", password="y")`) if it doesn't.

---

**Done criteria:** All 10 tests pass. Manual smoke green. PR merged. US-08 box in backlog ticked. Memory updated.
