# US-26 — expire_pending_bookings command (FR-23)

**Data:** 2026-05-24
**Branch (planned):** `feat/FR-23-expire-pending` (off `main`)
**Estymata:** S (jeden management command + testy; pure ORM, bez Stripe)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-26 jako #7, **plan-directly**; ostatni non-Stripe task przed US-24/25)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-23 (auto-expiration PENDING)
- `apps/cinema/management/commands/seed_db.py` — wzorzec `BaseCommand` (add_arguments/handle)
- `apps/booking/models.py::Booking` — `status`, `expires_at`, composite index `booking_status_expires_idx` (US-18)
- `apps/booking/services.py::cancel_booking` (US-23) — **NIE reused** (różna semantyka — patrz §3 decyzja 2)

---

## 1. Cel

US-26 dostarcza komendę `python manage.py expire_pending_bookings [--dry-run]` (FR-23): znajduje PENDING bookingi z wygasłym oknem płatności (`expires_at < now()`) i ustawia ich status na CANCELLED. W prod odpalane przez cron co 1 min (out of MVP — ręcznie w dev).

Zakres:

1. **Command** `apps/booking/management/commands/expire_pending_bookings.py` — `BaseCommand` z `--dry-run`.
2. **Package scaffolding** — `apps/booking/management/__init__.py` + `apps/booking/management/commands/__init__.py` (puste).
3. **Testy** w `tests/booking/test_expire_command.py` (~7).

### Out of scope (defer'd)

- **Cron / Celery beat** scheduling → poza MVP per FR-23 (ręcznie w dev). README note opcjonalnie.
- **Stripe `checkout.session.expired` webhook** (osobny trigger expire'a) → US-25.
- **`expire_pending_bookings` na PENDING z `stripe_session_id`** — komenda nie woła Stripe (PENDING = niezapłacone; brak refundu). Stripe sam zamyka sesję po `expires_at` (US-24 ustawi `Session.expires_at`).

---

## 2. Architektura plików

### Tworzone

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/management/__init__.py` | Create (empty) | package marker |
| `apps/booking/management/commands/__init__.py` | Create (empty) | package marker |
| `apps/booking/management/commands/expire_pending_bookings.py` | Create | `Command` (FR-23) |
| `tests/booking/test_expire_command.py` | Create | command tests |

### Edytowane

| Plik | Zmiana |
|------|--------|
| `.Claude/backlog.md` | US-26 → Done (po merge) |

Brak migracji (zero zmian modeli).

### Stan obecny (zweryfikowane)

| Element | Stan |
|---------|------|
| `apps/booking/management/` | ❌ nie istnieje — US-26 tworzy |
| `apps/cinema/management/commands/seed_db.py` | ✅ wzorzec `BaseCommand` |
| `apps/booking/models.py::Booking` | ✅ `status`, `expires_at`, index `booking_status_expires_idx` na (status, expires_at) |
| `tests/booking/factories.py` | ✅ `BookingFactory` (PENDING, expires +15m), `ConfirmedBookingFactory` |

---

## 3. Command design — `expire_pending_bookings.py`

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

### Decyzje uzasadnione

1. **`filter(status=PENDING, expires_at__lt=now)`.** Korzysta z composite index `booking_status_expires_idx` (US-18) — index był dodany dokładnie pod tę query. PENDING z `expires_at IS NULL` (broken state) NIE matchuje (`NULL < now` = False w SQL) — defensywnie wykluczone (spójne z `booked_seats_count`).

2. **NIE reused `cancel_booking` (US-23).** Dwie różnice semantyczne:
   - **`expires_at` zostaje** (FR-23: "audytowo") — `cancel_booking` clearuje `expires_at=None`. Expire keeps it.
   - **Brak reguły `start_time > now+1h`** — `can_be_cancelled()` wymaga przyszłego seansu; expire ignoruje czas seansu (liczy się wygasłe okno płatności, nie czas seansu). Expired PENDING może mieć seans w przyszłości (15-min okno płatności minęło, ale seans dopiero za tydzień).
   - Bulk `.update()` zamiast per-row `select_for_update` — batch job, nie request; idempotentny.

3. **Bulk `.update(status=CANCELLED)`** — single SQL UPDATE (atomic samo w sobie), wydajne, idempotentne (re-run: filter status=PENDING wyklucza już-CANCELLED). Zwraca liczbę zmienionych wierszy (`updated`).

4. **Aggregate PRZED update** — `Count` + `Sum(seats_count)` na queryset dla outputu (FR-23: "ile bookingów + suma zwolnionych miejsc"). `now` capture'owany raz → aggregate i update na tym samym zbiorze (concurrent edge: nieistotny dla dev cron; `updated` z `.update()` to actual count).

5. **`--dry-run`** — aggregate + print, bez `.update()`. Booking status pozostaje PENDING.

6. **`freed` semantyka.** Expired PENDING (`expires_at < now`) już NIE liczą się do `booked_seats_count` (tamto liczy tylko PENDING z `expires_at > now`). Więc miejsca były "zwolnione" z dostępności już przy wygaśnięciu — komenda tylko formalizuje status. `freed` w outpucie to suma `seats_count` expired bookingów (informacyjnie, per FR-23).

7. **Lokalizacja `apps/booking/`.** Komenda operuje wyłącznie na `Booking` (pure ORM, bez Stripe) → należy do booking app. FR §8 szkic umieścił ją pod payments, ale to predates US-18 app-layout decision (Booking → `apps/booking/`).

8. **Brak `transaction.atomic()`.** `.update()` to pojedynczy statement (atomic). Report z `updated` (actual return) → dokładny. Atomic zbędny.

---

## 4. Tests scope — `tests/booking/test_expire_command.py`

`pytestmark = pytest.mark.django_db`. Helper `_expired_pending(**kw) = BookingFactory(expires_at=now-1min, **kw)`, `_run(*args)` = `call_command("expire_pending_bookings", *args, stdout=StringIO())` → zwraca output.

- `test_cancels_expired_pending` — expired PENDING → CANCELLED.
- `test_keeps_expires_at_for_audit` — `expires_at` NIEzmienione po expire (FR-23 audit; ≠ cancel_booking).
- `test_leaves_active_pending` — `BookingFactory()` (expires +15m) → zostaje PENDING.
- `test_leaves_confirmed` — `ConfirmedBookingFactory()` → zostaje CONFIRMED.
- `test_idempotent_second_run_changes_nothing` — 2× run; po pierwszym brak PENDING z `expires_at < now`.
- `test_dry_run_makes_no_changes` — `--dry-run`: status pozostaje PENDING, output zawiera "dry-run".
- `test_reports_count_and_freed_seats` — 2 expired (seats 3 + 2) → output zawiera "2" (bookingi) i "5" (freed seats).

**Razem:** ~7 testów.

---

## 5. Definition of Done

- [ ] **Command:** `expire_pending_bookings` — filter PENDING + `expires_at < now` → CANCELLED (keep `expires_at`), output count + freed seats, `--dry-run`.
- [ ] **Package:** `apps/booking/management/commands/` z `__init__.py` × 2.
- [ ] **Idempotent:** re-run nie zmienia już-CANCELLED.
- [ ] **Testy:** ~7 w `tests/booking/test_expire_command.py`, green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff`, `ruff format --check`, `mypy` — clean.
- [ ] **No regression:** istniejące testy pass; `makemigrations --check` exits 0.
- [ ] **Manual smoke:** `seed_db` (PENDING z expires w przeszłości) → `python manage.py expire_pending_bookings --dry-run` (pokazuje count) → bez flagi (anuluje) → re-run (0 zmian).

---

## 6. Risks

1. **`expires_at IS NULL` PENDING.** Defensywnie wykluczone (`NULL < now` = False). Jeśli US-20 kiedyś stworzy PENDING bez expires_at (bug) — komenda go NIE złapie (zostanie wieczny PENDING). Mitigation: US-20 zawsze ustawia expires_at (zweryfikowane); brak akcji tu.
2. **`freed` vs realna dostępność.** Expired PENDING już nie liczą się do booked (booked liczy expires > now). "Freed seats" w outpucie jest informacyjne, nie reprezentuje realnego zwolnienia (to nastąpiło przy wygaśnięciu). Udokumentowane; FR-23 i tak prosi o tę sumę.
3. **Concurrent zmiana między aggregate a update.** `now` fixed; rzadki edge gdy booking expiruje/confirmuje się w międzyczasie → `updated` (actual) może != `count` (aggregate). Report `updated` jako liczbę anulowanych. Nieistotne dla dev cron.
4. **`call_command` stdout capture.** Test przekazuje `stdout=StringIO()`. `self.style.SUCCESS` dodaje ANSI tylko gdy tty — w teście `StringIO` brak kolorów, czysty tekst → substring asserts działają.
5. **Bulk `.update()` omija `save()`/signals.** Brak `auto_now`/signals na Booking istotnych tu (`created_at` to auto_now_add, nie zmieniany). Status-only update — OK. Brak custom save logic na Booking.
