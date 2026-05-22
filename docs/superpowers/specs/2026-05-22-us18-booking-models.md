# US-18 — Booking + StripeEvent models (M3 first task)

**Data:** 2026-05-22
**Branch (planned):** `feat/FR-3.8-booking-model` (off `main`)
**Estymata:** M (~0.5 dnia, faktycznie zbliżone do L ze względu na 2 nowe apps + seed_db bundle)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 milestone brief (US-18 jako #1, brainstorm-required)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §3.7 (Screening), §3.8 (Booking), §3.9 (StripeEvent), §6.4 (seed_db M3 extension)
- `apps/cinema/models.py::Screening` — stub `booked_seats_count` z US-10 do podmienienia
- `apps/cinema/management/commands/seed_db.py` — extension target dla bookings + stripe_events

---

## 1. Cel

US-18 to **fundament M3** — wszystkie pozostałe US (US-19..28) zależą od modeli wprowadzonych tutaj.

Zakres:

1. **Booking model** w nowej app `apps/booking/` — domain model dla rezerwacji biletów
2. **StripeEvent model** w nowej app `apps/payments/` — idempotency log dla webhooków Stripe (US-25)
3. **Screening refactor** w istniejącym `apps/cinema/` — `booked_seats_count()` zmienia stub `return 0` (US-10) na real aggregation z bookings (CONFIRMED + active-PENDING)
4. **Factories** w `tests/booking/factories.py` i `tests/payments/factories.py` (nowe moduły)
5. **`seed_db` extension** — `--bookings=N` arg + per-entity helpers + StripeEvent generation dla CONFIRMED (bundled w tym samym PR per `m3_planning.md` recommendation A)
6. **Minimal admin** — Booking + StripeEvent registered z basic `list_display` (pełny refactor z annotate/badge → US-28)

### Out of scope (defer'd do następnych US)

- **BookingForm + validation** (`seats_count ≤ available`, `start_time > now()`) → US-19. Powód: business validation siedzi w form layer (request context + transaction.atomic), NIE w `Booking.clean()` (full_clean nie auto-invoked przy `objects.create`, factory_boy bypass).
- **Booking create view** (`POST /screenings/<id>/book/`) + `select_for_update` race handling → US-20
- **Booking detail / my-bookings / cancel views** → US-21, 22, 23
- **Stripe Checkout integration** (real `stripe.checkout.Session.create`) → US-24
- **Stripe webhook handler** + idempotency dispatch → US-25
- **`expire_pending_bookings` management command** → US-26
- **Refund flow** → US-27
- **BookingAdmin pełen refactor** (annotate, status badges, inlines) + **ScreeningAdmin** (available_seats_display z kolorowym badge) → US-28
- Email notifications po CONFIRMED — out of M3 (lub follow-up w M5)

---

## 2. Architektura plików

### Nowe pliki

```
apps/booking/
├── __init__.py
├── apps.py                                       # BookingConfig name="apps.booking"
├── models.py                                     # Booking + BookingStatus
├── admin.py                                      # Minimal BookingAdmin
└── migrations/
    ├── __init__.py
    └── 0001_initial.py                           # generated via makemigrations

apps/payments/
├── __init__.py
├── apps.py                                       # PaymentsConfig name="apps.payments"
├── models.py                                     # StripeEvent
├── admin.py                                      # Minimal StripeEventAdmin (read-only)
└── migrations/
    ├── __init__.py
    └── 0001_initial.py                           # generated via makemigrations

tests/booking/
├── __init__.py
├── factories.py                                  # BookingFactory + variants
├── test_models.py                                # Booking model tests
└── test_admin.py                                 # BookingAdmin registration tests

tests/payments/
├── __init__.py
├── factories.py                                  # StripeEventFactory
├── test_models.py                                # StripeEvent model tests
└── test_admin.py                                 # StripeEventAdmin registration tests

tests/cinema/test_screening_methods.py            # Real booked_seats_count tests
                                                  # (separated from existing test_models.py)
```

### Edytowane pliki

```
settings/base.py                                  # INSTALLED_APPS += apps.booking, apps.payments
apps/cinema/models.py                             # Screening.booked_seats_count refactored (stub → real)
apps/cinema/management/commands/seed_db.py        # +bookings, +stripe_events helpers, --flush order
tests/cinema/test_seed_db.py                      # +bookings/stripe_events extension tests
.Claude/backlog.md                                # US-18 status → Done (after merge)
```

### Stan obecny (zweryfikowane)

| Element | Stan |
|---------|------|
| `apps/cinema/models.py::Screening.booked_seats_count()` | ⚠️ stub `return 0` (US-10 placeholder) |
| `apps/cinema/models.py::Screening.available_seats_count()` | ✅ delegate do `booked_seats_count` — sygnatura unchanged |
| `apps.booking` | ❌ nie istnieje |
| `apps.payments` | ❌ nie istnieje |
| `tests/booking/`, `tests/payments/` | ❌ nie istnieją |
| `tests/accounts/factories.py::UserFactory` | ✅ exists (M1) — dostępna dla BookingFactory.SubFactory |
| `tests/cinema/factories.py::ScreeningFactory` | ✅ exists (US-10) — dostępna dla BookingFactory.SubFactory |
| `apps/cinema/management/commands/seed_db.py` | ✅ exists (US-08, US-16) — pattern dla extension |

---

## 3. App layout decision (rozstrzygnięte w brainstormingu)

**Wybór:** Booking → nowa `apps/booking/`; StripeEvent → nowa `apps/payments/`.

| Decyzja | Wartość | Powód |
|---------|---------|-------|
| Booking app location | `apps/booking/` | Separation: domain (booking) vs cinema catalog. `cinema/` rośnie do 8 modeli inaczej. |
| StripeEvent app location | `apps/payments/` | Per FR §3.9 explicit. Infrastructure layer (Stripe-specific) oddzielony od domain (Booking). |
| Cross-app dependency direction | `booking` → `cinema` (FK `Booking.screening`); `booking` → `accounts` (FK `Booking.user`); `cinema` → `booking` (lazy import w `Screening.booked_seats_count`) | One-way FK + lazy import na cinema side rozwiązuje circular |
| StripeEvent ↔ Booking relation | Brak FK — loose coupling via `payload.client_reference_id` | Per FR §3.9. Webhook arrives before Booking lookup; StripeEvent jako pure audit log. |

### Cross-app load order (migration dependency)

```
1. accounts/migrations/0001..              (M1, exists)
2. cinema/migrations/0001..0006            (M2, exists)
3. booking/migrations/0001_initial         (NEW — depends on cinema + accounts)
4. payments/migrations/0001_initial        (NEW — no FK deps; parallel-able with booking)
```

---

## 4. Booking model

### `apps/booking/models.py`

```python
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class BookingStatus(models.TextChoices):
    PENDING = "PENDING", _("Oczekująca")
    CONFIRMED = "CONFIRMED", _("Potwierdzona")
    CANCELLED = "CANCELLED", _("Anulowana")


class Booking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name=_("user"),
    )
    screening = models.ForeignKey(
        "cinema.Screening",        # string ref → avoids circular import
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name=_("screening"),
    )
    seats_count = models.PositiveIntegerField(
        _("seats count"),
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    status = models.CharField(
        _("status"),
        max_length=12,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    stripe_session_id = models.CharField(_("Stripe session ID"), max_length=255, blank=True, default="")
    stripe_payment_intent_id = models.CharField(_("Stripe payment intent ID"), max_length=255, blank=True, default="")
    refund_id = models.CharField(_("refund ID"), max_length=255, blank=True, default="")
    refunded_at = models.DateTimeField(_("refunded at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("booking")
        verbose_name_plural = _("bookings")
        ordering = ("-created_at",)
        indexes = [
            # Optimizes US-26 expire_pending_bookings query
            models.Index(fields=["status", "expires_at"], name="booking_status_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"Booking #{self.pk} — {self.screening.movie.title}"

    @property
    def total_price(self) -> Decimal:
        return self.seats_count * self.screening.price
```

### Decyzje uzasadnione

1. **`expires_at` BEZ auto-default.** View layer (US-20) ustawia jawnie `now() + timedelta(minutes=15)` przy tworzeniu PENDING. CANCELLED i CONFIRMED bookingi mają `expires_at = None` (cleared post-payment lub niepotrzebne). Field allows `null=True, blank=True`.

2. **Stripe ID fields = `CharField(blank=True, default="")`, NIE `null=True`.** Django convention dla string fields (per FR §3.8) — używa `""` zamiast `NULL` dla 1-stan ambiguity.

3. **`refunded_at = null=True`** — asymetria z `refund_id`. DateTimeField nie używa `""` defaults; NULL semantically poprawne (no timestamp yet).

4. **`Meta.ordering = ("-created_at",)`** — US-22 (my-bookings list) chce najnowsze pierwsze. Default dla wszystkich querysetów; jeśli widok potrzebuje innego, override.

5. **`indexes = [Index(fields=["status", "expires_at"])]`** — optimizes US-26 query `filter(status="PENDING", expires_at__lt=now)`. Composite index z status first (high selectivity). FK auto-indexes na `user`, `screening` covered separately.

6. **`clean()` empty / brak override.** Business validation idzie do `BookingForm.clean()` (US-19). Reasons:
   - `full_clean()` NIE auto-called przy `objects.create(...)` — factory_boy + seed_db pomijają
   - Validation wymaga query (`screening.available_seats_count`) — coupling z query layer
   - Form/serializer layer ma request context + transaction.atomic
   - Django convention: model = data shape; form = input validation

7. **`__str__` używa `screening.movie.title`.** 1-query overhead (`select_related("screening__movie")` recommended w admin queryset). Useful dla admin display + debugging.

8. **`@property total_price`.** Per FR §3.8. NIE persisted — derived from `seats_count * screening.price`. Jeśli screening.price się zmienia post-booking, `total_price` reflects new value (intentional). Refund calculations używają Stripe `Refund.amount` (real money), nie `total_price`.

9. **`BookingStatus` jako `TextChoices` (max_length=12)** — `"CANCELLED"` to 9 chars; 12 buffer dla potential future statuses (np. `REFUNDED` ma 8 chars). Per FR §3.8.

---

## 5. StripeEvent model

### `apps/payments/models.py`

```python
from django.db import models
from django.utils.translation import gettext_lazy as _


class StripeEvent(models.Model):
    """Idempotency log for Stripe webhook events.

    Stripe retries webhooks on 5xx responses. This table guarantees that the same
    event_id never triggers a domain state change twice. Webhook handler (US-25)
    uses get_or_create(event_id=...) — duplicates return 200 OK without processing.
    """

    event_id = models.CharField(
        _("Stripe event ID"),
        max_length=255,
        unique=True,
    )
    event_type = models.CharField(_("event type"), max_length=100)
    payload = models.JSONField(_("payload"))
    received_at = models.DateTimeField(_("received at"), auto_now_add=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Stripe event")
        verbose_name_plural = _("Stripe events")
        ordering = ("-received_at",)

    def __str__(self) -> str:
        return f"{self.event_type} ({self.event_id})"
```

### Decyzje uzasadnione

1. **`event_id = unique=True`** — DB-level guarantee idempotencji. Concurrent webhook delivery (Stripe retries) race na `get_or_create` jest safe — drugi insert raises `IntegrityError`, webhook handler łapie i zwraca 200 OK.

2. **`payload = JSONField`** (per FR §3.9). Django `models.JSONField` od 3.1+ — Postgres używa JSONB (queryable, indexable); SQLite fallback to TEXT (project use Postgres dev/CI/prod, więc real JSONB).

3. **No FK do Booking.** Loose coupling via `payload.client_reference_id` (Stripe `Event.data.object.client_reference_id` = `str(booking.id)`). Rationale per FR §3.9: webhook arrives BEFORE Booking lookup; StripeEvent pure audit log; allows odbieranie events spoza booking domain (test events od Stripe CLI).

4. **`processed_at = null=True`** — Null initially; set to `timezone.now()` po pomyślnej obsłudze (US-25). Stale `processed_at IS NULL` rows = failed processing → debug signal.

5. **`ordering = ("-received_at",)`** — admin widzi najnowsze events pierwsze.

6. **Brak compound unique constraints** — `event_id` unique sam wystarczy (Stripe-issued globally unique).

---

## 6. Screening refactor

### `apps/cinema/models.py::Screening` — `booked_seats_count` rewrite

**Stub do podmienienia** (linia 125-127 w obecnym pliku):

```python
def booked_seats_count(self) -> int:
    # US-18 will sum seats_count from CONFIRMED bookings; until then no bookings exist.
    return 0
```

**Nowa implementacja:**

```python
def booked_seats_count(self) -> int:
    """Sum of seats_count from CONFIRMED + active-PENDING bookings.

    Active-PENDING = status=PENDING AND expires_at > now(). Expired PENDING
    bookings (expires_at <= now()) are NOT counted — they're effectively
    cancelled (waiting for expire_pending_bookings command to flip status).
    PENDING with expires_at IS NULL is also excluded (defensive — broken state).
    """
    from apps.booking.models import Booking, BookingStatus  # lazy: avoid circular

    now = timezone.now()
    return (
        self.bookings.filter(
            models.Q(status=BookingStatus.CONFIRMED)
            | models.Q(status=BookingStatus.PENDING, expires_at__gt=now)
        )
        .aggregate(total=models.Sum("seats_count"))["total"]
        or 0
    )
```

`available_seats_count()`, `is_available()`, `is_in_past()` — **sygnatury bez zmian**; one delegują do `booked_seats_count` więc automatically dostają nową semantykę.

### Decyzje uzasadnione

1. **Lazy import w metodzie** (`from apps.booking.models import Booking, BookingStatus`). Powód: `apps/booking/` importuje `cinema.Screening` (FK string ref, ale przy `apps.get_model` calls — sometimes top-level booking module → cinema module load order). Lazy import wewnątrz metody = bezpieczne (obie apps loaded przy call time).

2. **`Q(status=PENDING, expires_at__gt=now)`** matchuje TYLKO non-null expires_at z timestamp w przyszłości. Edge case: `expires_at IS NULL` — Postgres trójwartościowa logika daje False na `expires_at > now()` gdy NULL, więc NIE matches. Defensive exclude broken state z aggregation.

3. **`or 0` na końcu aggregate** — `Sum()` zwraca None dla empty queryset. `or 0` zapewnia integer return type. Django idiom.

4. **`Booking` import używa `apps.booking.models`** — NIE `apps.get_model("booking", "Booking")` (cleaner type hints, IDE-friendly).

### Regression risk

Istniejące testy używające `Screening.booked_seats_count` / `available_seats_count` / `is_available` przed US-18:

- `tests/cinema/test_movie_detail.py` — używa `available_seats_count` w template render. Test scenarios używają fresh screening (no bookings) → wciąż capacity. **No regression.**
- `tests/cinema/test_screening_list.py` — same. **No regression.**
- `tests/cinema/test_models.py` — jeśli ma `test_screening_*_methods`, używały stub'a (return 0). **Verify w plan phase.**

US-18 dorzuca **nowy plik** `tests/cinema/test_screening_methods.py` z real bookings — replaces stub-based assertions.

---

## 7. Factories

### `tests/booking/factories.py`

```python
from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.booking.models import BookingStatus
from tests.accounts.factories import UserFactory
from tests.cinema.factories import ScreeningFactory


class BookingFactory(DjangoModelFactory):
    class Meta:
        model = "booking.Booking"   # lazy string ref (per US-10 pitfall — module-load ordering)

    user = factory.SubFactory(UserFactory)
    screening = factory.SubFactory(ScreeningFactory)
    seats_count = factory.Faker("pyint", min_value=1, max_value=10)
    status = BookingStatus.PENDING
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))


class ConfirmedBookingFactory(BookingFactory):
    """PENDING → CONFIRMED transition simulated. Stripe IDs populated."""

    status = BookingStatus.CONFIRMED
    expires_at = None   # CONFIRMED clears expires_at (no longer relevant after payment)
    stripe_session_id = factory.Sequence(lambda n: f"cs_test_{n}")
    stripe_payment_intent_id = factory.Sequence(lambda n: f"pi_test_{n}")


class CancelledBookingFactory(BookingFactory):
    """CANCELLED — used for testing list/history views."""

    status = BookingStatus.CANCELLED
    expires_at = None
```

### `tests/payments/factories.py`

```python
import factory
from factory.django import DjangoModelFactory


class StripeEventFactory(DjangoModelFactory):
    class Meta:
        model = "payments.StripeEvent"

    event_id = factory.Sequence(lambda n: f"evt_test_{n}")
    event_type = "checkout.session.completed"
    payload = factory.LazyAttribute(
        lambda obj: {
            "id": obj.event_id,
            "type": obj.event_type,
            "data": {"object": {"client_reference_id": "1"}},
        }
    )
    # processed_at default None (raw event, not yet processed by webhook handler)
```

---

## 8. Tests scope

### `tests/booking/test_models.py`

- `test_booking_creation_with_required_fields`
- `test_booking_status_default_is_pending`
- `test_booking_created_at_auto_set`
- `test_booking_total_price_returns_seats_times_screening_price`
- `test_booking_str_includes_id_and_movie_title`
- `test_booking_seats_count_validator_rejects_zero` (via `full_clean()`)
- `test_booking_seats_count_validator_rejects_eleven`
- `test_booking_default_ordering_newest_first` (create 3 w różnych czasach, assert)
- `test_booking_cascade_from_user` (delete user → bookings gone)
- `test_booking_cascade_from_screening` (delete screening → bookings gone)
- `test_booking_status_expires_index_exists` (introspect `Meta.indexes`)

### `tests/payments/test_models.py`

- `test_stripe_event_creation_with_required_fields`
- `test_stripe_event_id_unique_constraint_raises_integrity_error`
- `test_stripe_event_payload_round_trips_dict`
- `test_stripe_event_received_at_auto_set`
- `test_stripe_event_processed_at_defaults_none`
- `test_stripe_event_str_includes_type_and_id`
- `test_stripe_event_default_ordering_newest_first`

### `tests/cinema/test_screening_methods.py` (nowy plik)

- `test_booked_seats_count_zero_for_no_bookings`
- `test_booked_seats_count_sums_confirmed_bookings`
- `test_booked_seats_count_includes_active_pending` (expires_at > now)
- `test_booked_seats_count_excludes_expired_pending` (expires_at <= now)
- `test_booked_seats_count_excludes_cancelled`
- `test_booked_seats_count_excludes_pending_with_null_expires_at` (defensive)
- `test_available_seats_count_equals_capacity_minus_booked` (FR-7 example: hall 100, booking 30 → 70)
- `test_available_seats_count_zero_when_sold_out`
- `test_is_available_true_for_future_with_seats`
- `test_is_available_false_when_sold_out`
- `test_is_available_false_for_past_screening`

### `tests/booking/test_admin.py` + `tests/payments/test_admin.py` (minimal)

- `test_booking_is_registered`
- `test_booking_admin_list_display_columns` (sprawdza basic shape)
- `test_stripe_event_is_registered`
- `test_stripe_event_admin_is_read_only` (sprawdza `readonly_fields`)

### `tests/cinema/test_seed_db.py` extension

- `test_seed_db_creates_bookings_with_default_count`
- `test_seed_db_bookings_status_distribution_includes_all_three` (CONFIRMED + PENDING + CANCELLED present; NIE strict ratio — flaky)
- `test_seed_db_creates_one_stripe_event_per_confirmed_booking`
- `test_seed_db_flush_deletes_bookings_before_screenings` (FK-safe; existing screenings_first test pattern)
- `test_seed_db_flush_deletes_stripe_events_independently`
- `test_seed_db_non_empty_guard_includes_bookings`

**Razem:** ~32 nowe testy.

---

## 9. seed_db extension

### `apps/cinema/management/commands/seed_db.py` zmiany

#### Nowy argument

```python
parser.add_argument(
    "--bookings",
    type=int,
    default=30,
    help="Number of bookings to create (default 30).",
)
```

#### Nowe per-entity helpers (sibling methods na Command — NIE nested!)

```python
def _seed_bookings(self, count, screenings, users):
    """Generate ~85% CONFIRMED / ~5% PENDING / ~10% CANCELLED bookings.

    PENDING bookings get random expires_at (50/50 past/future) for testing
    expire_pending_bookings command (US-26). CONFIRMED bookings get realistic
    Stripe session/payment_intent IDs.

    Returns list of created CONFIRMED bookings (for _seed_stripe_events).
    """
    # Implementation in plan phase. Uses random.choices with weights.

def _seed_stripe_events(self, confirmed_bookings):
    """Generate one StripeEvent per CONFIRMED booking with mock payload.

    event_id = f"evt_seed_{uuid.uuid4().hex[:16]}"
    event_type = "checkout.session.completed"
    payload = minimal mock JSON with client_reference_id = str(booking.id)
    """
    # Implementation in plan phase.
```

#### `handle()` integration

Po `_seed_screenings(...)` dorzuć:

```python
confirmed_bookings = self._seed_bookings(
    options["bookings"], screenings=screenings, users=users
)
self._seed_stripe_events(confirmed_bookings)
```

#### `--flush` order extension

Nowa kolejność (FK-safe, top-down):

```
StripeEvent (independent — no FK; can be deleted any time)
Booking     (FK to Screening + User; must die before Screening + User)
Screening   (existing — FK to Movie + Hall)
Movie       (existing — M2M to Genre/Actor/Director)
Hall        (existing)
Actor       (existing)
Director    (existing)
Genre       (existing)
User        (existing — superusers preserved)
```

#### Non-empty guard

Rozszerzony — jeśli `Booking.objects.exists()` lub `StripeEvent.objects.exists()` bez `--append`/`--flush` → abort.

---

## 10. Minimal admin

### `apps/booking/admin.py`

```python
from django.contrib import admin

from apps.booking.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Minimal registration. Full refactor (annotate, status badges, screening inline)
    deferred to US-28."""

    list_display = ("id", "user", "screening", "seats_count", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "screening__movie__title")
    readonly_fields = ("created_at",)
```

### `apps/payments/admin.py`

```python
from django.contrib import admin

from apps.payments.models import StripeEvent


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    """StripeEvent is an audit log — all fields read-only."""

    list_display = ("event_id", "event_type", "received_at", "processed_at")
    list_filter = ("event_type",)
    search_fields = ("event_id",)
    readonly_fields = ("event_id", "event_type", "payload", "received_at", "processed_at")
```

---

## 11. Definition of Done

- [ ] **Apps registered:** `INSTALLED_APPS` zawiera `apps.booking` + `apps.payments`
- [ ] **Migrations:** `booking/migrations/0001_initial.py` + `payments/migrations/0001_initial.py` utworzone i applikowalne na fresh DB. `makemigrations --check` exits 0.
- [ ] **Booking model:** wszystkie pola per FR §3.8 + `BookingStatus` enum + composite index na (status, expires_at) + `total_price` property + `__str__`
- [ ] **StripeEvent model:** pola per FR §3.9 + `event_id unique=True` + JSONField payload
- [ ] **Screening refactor:** `booked_seats_count()` zwraca real aggregation (CONFIRMED + active-PENDING). `available_seats_count`, `is_available`, `is_in_past` — sygnatury unchanged.
- [ ] **Factories:** `BookingFactory`, `ConfirmedBookingFactory`, `CancelledBookingFactory`, `StripeEventFactory` z lazy string model refs
- [ ] **Tests:** ~32 nowych testów (model + screening refactor + admin registration + seed_db extension); wszystkie green
- [ ] **`seed_db` extension:** `--bookings=N` arg (default 30); status distribution 85/5/10 (all three present); StripeEvent per CONFIRMED; `--flush` FK-safe order
- [ ] **Minimal admin:** Booking + StripeEvent registered, basic `list_display` (pełny refactor → US-28)
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff check`, `ruff format --check`, `mypy` — wszystkie clean
- [ ] **No regression:** istniejące M1/M2 testy pass; `manage.py makemigrations --check` exits 0
- [ ] **Manual smoke:**
  - `poetry run python manage.py seed_db --flush --bookings=10` succeeds
  - `/admin/booking/booking/` accessible + lists bookings z status filter
  - `/admin/payments/stripeevent/` accessible + StripeEvents visible

---

## 12. Risks

1. **Lazy import circular safety.** `Screening.booked_seats_count()` lazy-importuje `apps.booking.models.Booking`. Jeśli `apps/booking/__init__.py` lub `apps.py` ever doda top-level cinema import — kiedy cinema loads booking, booking ładowa cinema znowu → AppRegistryNotReady error. **Mitigation:** `apps/booking/` keeps imports minimal; FK uses string ref; admin imports lokalnie w `admin.py` (post-apps-ready).

2. **`expires_at` `IS NULL` defensive exclusion.** `booked_seats_count` aggregation explicit excludes PENDING with `expires_at IS NULL`. Jeśli US-20 view kiedyś tworzy PENDING bez `expires_at` (bug), bookingi NIE liczą się do `booked` → race condition (overbooking). **Mitigation:** US-20 spec MUSI wymagać `expires_at` na create; testy validate non-null PENDING.

3. **Existing `tests/cinema/test_models.py` Screening tests.** Stub-based assertions (jeśli istnieją) wymagają update. **Action:** plan phase grep `booked_seats_count\|available_seats_count\|is_available` w `tests/cinema/test_models.py`, decide update/migrate.

4. **`Booking.cascade` from `User`.** Per FR §3.8: `on_delete=CASCADE`. Edge case: superuser delete usuwa wszystkie ich bookings + StripeEvents related (via payload reference — choć no FK). **Action:** spec dla US-28 admin może chcieć soft-delete pattern, ale to scope tamtego US.

5. **JSONField w SQLite.** `models.JSONField` works w Postgres (JSONB native) i SQLite (3.9+, TEXT z JSON1). Project uses Postgres dev/CI/prod, ale CI może przejść na SQLite dla speed. **Verify:** `pyproject.toml` test config + `DATABASE_URL` w workflow.

6. **`seed_db --flush` order regression.** Dodanie 2 nowych modeli (Booking + StripeEvent) do flush order. Pomyłka order → `IntegrityError` (ProtectedError). **Mitigation:** test `test_seed_db_flush_deletes_bookings_before_screenings` + manual smoke pre-merge.

7. **Status distribution flaky tests.** `85% CONFIRMED / 5% PENDING / 10% CANCELLED` z `random.choices` daje nondeterministic exact counts w testach. **Mitigation:** test sprawdza obecność wszystkich 3 statusów (`Booking.objects.filter(status=X).exists()` for each), NIE strict ratio.

8. **`Booking.__str__` query overhead.** Access `screening.movie.title` triggers 1 query if screening not prefetched. Admin `list_display = ("__str__",)` could N+1 — ale używamy `list_display = ("id", "user", "screening", ...)` które używają `__str__` na FK objects (default Django admin format). **Mitigation:** US-28 spec dodaje `select_related("user", "screening__movie")` w `BookingAdmin.get_queryset`. US-18 skip (minimal admin).

---

## 13. Decisions data-driven (do plan phase)

1. **Migration auto-gen vs hand-write.** Default: `makemigrations` auto. Verify output (field types, indexes name).
2. **`seed_db._seed_bookings` weighted random.** `random.choices(STATUSES, weights=[85, 5, 10], k=count)` vs explicit split (e.g., first 85% = CONFIRMED). Default: weighted random + `random.seed` opt-in dla determinism.
3. **`tests/cinema/test_models.py` audit.** Plan phase grep, decide which tests reorganize do `test_screening_methods.py`.
4. **Status default test trifecta** — czy testować Booking creation per każdy status (`BookingFactory`, `ConfirmedBookingFactory`, `CancelledBookingFactory`) explicit, czy delegate do factory variants tests. Default: factory tests covered via downstream tests using factories.
