# US-26 — expire_pending_bookings command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Management command `expire_pending_bookings [--dry-run]` (FR-23) that cancels PENDING bookings whose payment window (`expires_at`) has lapsed — status → CANCELLED (keeping `expires_at` for audit), reporting count + freed seats.

**Architecture:** A `BaseCommand` in the booking app (`apps/booking/management/commands/`) that does a single race-free bulk `filter(status=PENDING, expires_at__lt=now).update(status=CANCELLED)` (idempotent, index-backed), with a pre-`update()` aggregate for the output and a `--dry-run` that skips the write. Deliberately NOT reusing `cancel_booking` (different semantics — keeps `expires_at`, ignores the start_time+1h rule).

**Tech Stack:** Django 6 `BaseCommand`, pure ORM (`.update()` + aggregate), pytest-django `call_command`.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-24-us26-expire-pending.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (`tests/booking/test_expire_command.py`).
- Kod aplikacji (`apps/booking/management/commands/expire_pending_bookings.py` + puste `__init__.py`) — **default: user tworzy/wkleja** z planu. Jeśli user poprosi "popraw sam" — Claude edytuje.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

Branch już utworzony (`feat/FR-23-expire-pending`). Spec + plan jako pierwszy commit:

```bash
git add docs/superpowers/specs/2026-05-24-us26-expire-pending.md \
        docs/superpowers/plans/2026-05-24-us26-expire-pending.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-26 expire_pending_bookings spec and plan

Planning artifacts for US-26 (FR-23) — management command that cancels PENDING
bookings past their expires_at window. Bulk .update() (idempotent, index-backed),
keeps expires_at for audit, --dry-run. Lives in apps/booking/; not reusing
cancel_booking (different semantics). No migrations.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/management/__init__.py` | Create (empty) | package marker |
| `apps/booking/management/commands/__init__.py` | Create (empty) | package marker |
| `apps/booking/management/commands/expire_pending_bookings.py` | Create | `Command` (FR-23) |
| `tests/booking/test_expire_command.py` | Create | command tests |
| `.Claude/backlog.md` | Modify | US-26 → Done (po merge) |

No migrations.

---

## Task 1: expire_pending_bookings command

**Files:**
- Test: `tests/booking/test_expire_command.py` (Create)
- Create: `apps/booking/management/__init__.py`, `apps/booking/management/commands/__init__.py`, `apps/booking/management/commands/expire_pending_bookings.py`

- [ ] **Step 1: Write the failing tests** (`tests/booking/test_expire_command.py`)

```python
"""Tests for the expire_pending_bookings command (US-26 / FR-23)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory

pytestmark = pytest.mark.django_db


def _expired_pending(**kwargs):
    return BookingFactory(expires_at=timezone.now() - timedelta(minutes=1), **kwargs)


def _run(*args):
    out = StringIO()
    call_command("expire_pending_bookings", *args, stdout=out)
    return out.getvalue()


class TestExpirePendingBookings:
    def test_cancels_expired_pending(self):
        booking = _expired_pending()
        _run()
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_keeps_expires_at_for_audit(self):
        booking = _expired_pending()
        original = booking.expires_at
        _run()
        booking.refresh_from_db()
        assert booking.expires_at == original  # NOT cleared (FR-23 audit)

    def test_leaves_active_pending(self):
        booking = BookingFactory()  # expires +15min (future)
        _run()
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING

    def test_leaves_confirmed(self):
        booking = ConfirmedBookingFactory()
        _run()
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_idempotent_second_run_changes_nothing(self):
        _expired_pending()
        _run()
        _run()  # second run must not error or re-process
        assert not Booking.objects.filter(
            status=BookingStatus.PENDING, expires_at__lt=timezone.now()
        ).exists()

    def test_dry_run_makes_no_changes(self):
        booking = _expired_pending()
        output = _run("--dry-run")
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING  # unchanged
        assert "dry-run" in output

    def test_reports_count_and_freed_seats(self):
        _expired_pending(seats_count=3)
        _expired_pending(seats_count=2)
        output = _run()
        assert "2" in output  # 2 bookings cancelled
        assert "5" in output  # 5 freed seats
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_expire_command.py -v`
Expected: FAIL — `CommandError: Unknown command: 'expire_pending_bookings'`.

- [ ] **Step 3: Create the command package + command** (user creates)

Create the two empty package markers (Git Bash):

```bash
mkdir -p apps/booking/management/commands
touch apps/booking/management/__init__.py
touch apps/booking/management/commands/__init__.py
```

Then create `apps/booking/management/commands/expire_pending_bookings.py` with:

```python
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus


class Command(BaseCommand):
    help = "Cancel PENDING bookings whose payment window (expires_at) has lapsed (FR-23)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cancelled without saving.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Booking.objects.filter(
            status=BookingStatus.PENDING, expires_at__lt=now
        )
        stats = expired.aggregate(count=Count("id"), seats=Sum("seats_count"))
        count = stats["count"]
        freed = stats["seats"] or 0

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {count} rezerwacji do anulowania (zwolniłoby {freed} miejsc)."
            )
            return

        updated = expired.update(status=BookingStatus.CANCELLED)
        self.stdout.write(
            self.style.SUCCESS(
                f"Anulowano {updated} rezerwacji (zwolniono {freed} miejsc)."
            )
        )
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/booking/test_expire_command.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/booking/management tests/booking/test_expire_command.py
git commit -m "$(cat <<'EOF'
feat(FR-23): add expire_pending_bookings management command

Cancels PENDING bookings whose expires_at has lapsed via a single idempotent bulk
update (status -> CANCELLED, keeping expires_at for audit), reporting the count
and freed seats. --dry-run shows what would change without saving. Lives in the
booking app; not reusing cancel_booking (which clears expires_at and enforces the
start_time+1h rule). Run manually in dev; cron/Celery is out of MVP per FR-23.

Closes US-26.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

> **Migrations gotcha (project dev pitfall):** `git add apps/booking/management` adds the whole new package — confirm both `__init__.py` files landed (`git status` should show them staged). An empty package dir without `__init__.py` means the command won't be discovered.

---

## Task 2: Quality gates

- [ ] **Step 1: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/booking tests/booking
poetry run ruff format --check apps/booking tests/booking
poetry run mypy apps/booking
poetry run python manage.py makemigrations --check --dry-run   # expect: no changes
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; `makemigrations --check` exits 0; full suite green; coverage ≥80%.

> mypy: `handle(self, *args, **options)` matches `BaseCommand` — should be clean (mirrors `seed_db.py`). If django-stubs wants typed `**options: Any`, match `seed_db.py`'s signature.

- [ ] **Step 2: Manual smoke (optional)**

```bash
poetry run python manage.py expire_pending_bookings --dry-run   # shows count, no change
poetry run python manage.py expire_pending_bookings             # cancels, prints freed seats
poetry run python manage.py expire_pending_bookings             # idempotent: 0
```

(Seed data via `seed_db` already creates PENDING with past `expires_at` per FR-13.)

---

## Task 3: Backlog + PR

- [ ] **Step 1: Update `.Claude/backlog.md` status board**

- `Done` → append US-26; M3 count → 7/11
- `Ready (DoR ✅)` → US-24 (Stripe Checkout) — **brainstorm-required** per m3_planning (replace stub, `poetry add stripe`, `.env` keys, `BASE_URL`)

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-26 done — expire_pending_bookings command shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-23-expire-pending
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-26) / DoD checklist / Test plan / Out of scope (cron scheduling, Stripe expired-webhook US-25).

---

## Self-Review (wykonane)

**Spec coverage:** §3 command → Task 1 Step 3. §4 tests → Task 1 Step 1 (7). §5 DoD → covered. §6 risk #4 (stdout capture) → tests pass `stdout=StringIO()`. FR-23 acceptance: finds PENDING+expired (filter), sets CANCELLED keeping expires_at (`test_keeps_expires_at_for_audit`), output count+seats (`test_reports_count_and_freed_seats`), `--dry-run` (`test_dry_run_makes_no_changes`), idempotent (`test_idempotent_second_run_changes_nothing`).

**Placeholder scan:** no TBD/TODO; every step has full code/command.

**Type consistency:** command name `expire_pending_bookings` consistent in tests (`call_command(...)`), Step 2 RED message, plan title, and the spec. `--dry-run` → `options["dry_run"]` consistent. `BookingStatus.PENDING`/`CANCELLED` match model. Output strings ("dry-run", count, freed) match what `test_dry_run_makes_no_changes` / `test_reports_count_and_freed_seats` assert.
