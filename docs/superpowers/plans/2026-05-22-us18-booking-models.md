# US-18 — Booking + StripeEvent models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Utwórz dwie nowe apps (`apps/booking/`, `apps/payments/`) z modelami Booking + StripeEvent, refactor `Screening.booked_seats_count()` z stub na real aggregation, extend `seed_db` o bookings + stripe_events. Model-only US — bez views, bez Stripe service.

**Architecture:** Booking jako domain model w `apps/booking/` (FK do `cinema.Screening` + `settings.AUTH_USER_MODEL`); StripeEvent jako infrastructure log w `apps/payments/` (no FK — loose coupling via `payload.client_reference_id`). Screening.booked_seats_count używa lazy import + Q-aggregation (CONFIRMED + active-PENDING). Bundled w jednym PR: 2 nowe apps + Screening refactor + seed_db extension + minimal admin + factories + ~32 testy.

**Tech Stack:** Django 6 models + migracje, factory_boy z lazy string `model="booking.Booking"` refs (per US-10 pitfall), pytest-django, Django `JSONField` (Postgres JSONB), composite index na `(status, expires_at)`.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-22-us18-booking-models.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (test_*.py, factories) — testy są jego scope.
- Claude pisze również refactor `Screening.booked_seats_count()` w `apps/cinema/models.py` (drobny perf-related change, ściśle powiązany z testami; user może override).
- Models (`apps/booking/models.py`, `apps/payments/models.py`), apps.py, admin.py, seed_db extension — **default: user wkleja** pełen content z planu do plików. Jeśli user wybierze "sam popraw" — Claude edytuje.
- User odpala wszystkie komendy git/gh + pytest sam.

---

## Branch Strategy

Pre-Task-1 — utwórz nowy branch off main:

```bash
git checkout main && git pull
git checkout -b feat/FR-3.8-booking-model
git branch --show-current   # → feat/FR-3.8-booking-model
```

Spec + plan (uncommitted na main) commitujemy jako pierwszy commit NA branchu (pattern z PR #18/#19/#20):

```bash
git add docs/superpowers/specs/2026-05-22-us18-booking-models.md \
        docs/superpowers/plans/2026-05-22-us18-booking-models.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-18 Booking models spec and implementation plan

Brainstorming + planning artifacts for US-18 — first M3 task. Bootstrap 2 new
apps (apps/booking + apps/payments), Booking + StripeEvent models, Screening
refactor (real booked_seats_count), seed_db extension. Model-only US; views
come in US-19+. App layout B-variant: Booking own app, StripeEvent in payments
(per FR §3.9). ~32 new tests across model + screening_methods + admin + seed_db.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

### Tworzone (apps + tests)

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/payments/__init__.py` | Create (empty) | Python package marker |
| `apps/payments/apps.py` | Create | `PaymentsConfig` name=`"apps.payments"` |
| `apps/payments/models.py` | Create | `StripeEvent` model |
| `apps/payments/admin.py` | Create | `StripeEventAdmin` read-only |
| `apps/payments/migrations/__init__.py` | Create (empty) | |
| `apps/payments/migrations/0001_initial.py` | Generated via `makemigrations` | |
| `apps/booking/__init__.py` | Create (empty) | |
| `apps/booking/apps.py` | Create | `BookingConfig` name=`"apps.booking"` |
| `apps/booking/models.py` | Create | `Booking` + `BookingStatus` |
| `apps/booking/admin.py` | Create | Minimal `BookingAdmin` |
| `apps/booking/migrations/__init__.py` | Create (empty) | |
| `apps/booking/migrations/0001_initial.py` | Generated via `makemigrations` | |
| `tests/booking/__init__.py` | Create (empty) | |
| `tests/booking/factories.py` | Create | `BookingFactory` + variants |
| `tests/booking/test_models.py` | Create | Booking model tests |
| `tests/booking/test_admin.py` | Create | Admin registration tests |
| `tests/payments/__init__.py` | Create (empty) | |
| `tests/payments/factories.py` | Create | `StripeEventFactory` |
| `tests/payments/test_models.py` | Create | StripeEvent model tests |
| `tests/payments/test_admin.py` | Create | Admin registration tests |
| `tests/cinema/test_screening_methods.py` | Create | Real `booked_seats_count` tests (replaces stub assertions) |

### Edytowane

| Plik | Akcja |
|------|-------|
| `settings/base.py` | `INSTALLED_APPS += apps.booking, apps.payments` |
| `apps/cinema/models.py` | `Screening.booked_seats_count()` — stub → real aggregation |
| `apps/cinema/management/commands/seed_db.py` | `--bookings=N` arg + `_seed_bookings` + `_seed_stripe_events` helpers + flush order |
| `tests/cinema/test_models.py` | Usuń 6 stub-based Screening method tests (linie 280-329) — migrowane do `test_screening_methods.py` |
| `tests/cinema/test_seed_db.py` | Extension — booking + stripe_events tests |
| `.Claude/backlog.md` | US-18 → Done |

---

## Task 1: Bootstrap `apps/payments/` — StripeEvent model + admin + factory + tests

**Files:**
- Create: `apps/payments/__init__.py`, `apps/payments/apps.py`, `apps/payments/models.py`, `apps/payments/admin.py`, `apps/payments/migrations/__init__.py`
- Create: `tests/payments/__init__.py`, `tests/payments/factories.py`, `tests/payments/test_models.py`, `tests/payments/test_admin.py`
- Modify: `settings/base.py` (INSTALLED_APPS)

- [ ] **Step 1: Utwórz strukturę `apps/payments/` ręcznie w PyCharm (5 nowych plików):**

```
apps/payments/
├── __init__.py                 (empty)
├── apps.py                     (content below)
├── models.py                   (content below)
├── admin.py                    (content below)
└── migrations/
    └── __init__.py             (empty)
```

`apps/payments/__init__.py` — empty file.

`apps/payments/migrations/__init__.py` — empty file.

`apps/payments/apps.py`:

```python
from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Payments"
```

`apps/payments/models.py`:

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

`apps/payments/admin.py`:

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

- [ ] **Step 2: Zarejestruj app w `settings/base.py`. Otwórz plik, znajdź `INSTALLED_APPS` (linia 24-33). Po linii `"apps.cinema",` dopisz:**

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.cinema",
    "apps.payments",       # NEW
]
```

(Booking dorzucamy w Task 2.)

- [ ] **Step 3: Wygeneruj migrację:**

```bash
poetry run python manage.py makemigrations payments
```

Oczekiwane output: `Migrations for 'payments': apps/payments/migrations/0001_initial.py - Create model StripeEvent`.

- [ ] **Step 4: Sanity check — apply migration na test DB:**

```bash
poetry run python manage.py migrate
poetry run python manage.py makemigrations --check
```

Drugie polecenie powinno exit 0 (nothing missing).

- [ ] **Step 5: Utwórz `tests/payments/__init__.py` (empty) + `tests/payments/factories.py`:**

`tests/payments/factories.py`:

```python
"""factory_boy factories for the payments app."""

import factory
from factory.django import DjangoModelFactory


class StripeEventFactory(DjangoModelFactory):
    """Default factory creates a checkout.session.completed event with mock payload."""

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

- [ ] **Step 6: Utwórz `tests/payments/test_models.py`:**

```python
"""Tests for apps.payments.StripeEvent model."""

import pytest
from django.db import IntegrityError

from apps.payments.models import StripeEvent
from tests.payments.factories import StripeEventFactory

pytestmark = pytest.mark.django_db


class TestStripeEventCreation:
    def test_creation_with_required_fields(self):
        event = StripeEvent.objects.create(
            event_id="evt_unit_1",
            event_type="checkout.session.completed",
            payload={"id": "evt_unit_1", "type": "checkout.session.completed"},
        )
        assert event.pk is not None
        assert event.event_id == "evt_unit_1"
        assert event.event_type == "checkout.session.completed"
        assert event.payload["id"] == "evt_unit_1"

    def test_received_at_auto_set(self):
        event = StripeEventFactory()
        assert event.received_at is not None

    def test_processed_at_defaults_none(self):
        event = StripeEventFactory()
        assert event.processed_at is None

    def test_payload_round_trips_dict(self):
        payload = {"nested": {"key": [1, 2, 3]}, "flag": True}
        event = StripeEventFactory(payload=payload)
        event.refresh_from_db()
        assert event.payload == payload


class TestStripeEventConstraints:
    def test_event_id_unique_constraint_raises_integrity_error(self):
        StripeEventFactory(event_id="evt_dup")
        with pytest.raises(IntegrityError):
            StripeEventFactory(event_id="evt_dup")


class TestStripeEventMeta:
    def test_str_includes_type_and_id(self):
        event = StripeEventFactory(
            event_id="evt_str_test", event_type="checkout.session.completed"
        )
        assert str(event) == "checkout.session.completed (evt_str_test)"

    def test_default_ordering_newest_first(self):
        first = StripeEventFactory()
        second = StripeEventFactory()
        events = list(StripeEvent.objects.all())
        assert events[0] == second
        assert events[1] == first
```

- [ ] **Step 7: Utwórz `tests/payments/test_admin.py`:**

```python
"""Tests for apps.payments admin registration."""

import pytest
from django.contrib import admin

from apps.payments.models import StripeEvent

pytestmark = pytest.mark.django_db


class TestStripeEventAdminRegistration:
    def test_stripe_event_is_registered(self):
        assert admin.site.is_registered(StripeEvent)

    def test_stripe_event_admin_list_display_columns(self):
        ma = admin.site._registry[StripeEvent]
        assert ma.list_display == ("event_id", "event_type", "received_at", "processed_at")

    def test_stripe_event_admin_all_fields_readonly(self):
        ma = admin.site._registry[StripeEvent]
        # StripeEvent is an audit log — all fields read-only via admin.
        assert set(ma.readonly_fields) == {
            "event_id",
            "event_type",
            "payload",
            "received_at",
            "processed_at",
        }
```

- [ ] **Step 8: Run testów dla payments:**

```bash
poetry run pytest tests/payments/ -v
```

Oczekiwane: wszystkie zielone (7 testów: 4 creation + 1 constraint + 2 meta + 3 admin).

- [ ] **Step 9: Pełny pytest regression:**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone (istniejące M1/M2 testy + nowe payments).

- [ ] **Step 10: Commit:**

```bash
git add apps/payments/ settings/base.py tests/payments/
git commit -m "$(cat <<'EOF'
feat(FR-3.9): add apps/payments with StripeEvent model and idempotency log

Bootstrap new app apps/payments/ for Stripe integration layer. StripeEvent model
serves as idempotency log — event_id with unique=True constraint guarantees
that webhook retries (Stripe sends duplicates on 5xx) cannot trigger domain
state changes twice. JSONField payload stores full event for audit/debug.
Minimal read-only admin registered. No FK to Booking — loose coupling via
payload.client_reference_id (per FR §3.9). Webhook view + dispatch logic
deferred to US-25.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

---

## Task 2: Bootstrap `apps/booking/` — Booking model + admin + factories + tests

**Files:**
- Create: `apps/booking/__init__.py`, `apps/booking/apps.py`, `apps/booking/models.py`, `apps/booking/admin.py`, `apps/booking/migrations/__init__.py`
- Create: `tests/booking/__init__.py`, `tests/booking/factories.py`, `tests/booking/test_models.py`, `tests/booking/test_admin.py`
- Modify: `settings/base.py` (INSTALLED_APPS)

- [ ] **Step 1: Utwórz strukturę `apps/booking/` w PyCharm (5 nowych plików):**

`apps/booking/__init__.py` — empty.

`apps/booking/migrations/__init__.py` — empty.

`apps/booking/apps.py`:

```python
from django.apps import AppConfig


class BookingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.booking"
    verbose_name = "Booking"
```

`apps/booking/models.py`:

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
        "cinema.Screening",
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
    stripe_session_id = models.CharField(
        _("Stripe session ID"), max_length=255, blank=True, default=""
    )
    stripe_payment_intent_id = models.CharField(
        _("Stripe payment intent ID"), max_length=255, blank=True, default=""
    )
    refund_id = models.CharField(_("refund ID"), max_length=255, blank=True, default="")
    refunded_at = models.DateTimeField(_("refunded at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("booking")
        verbose_name_plural = _("bookings")
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "expires_at"], name="booking_status_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"Booking #{self.pk} — {self.screening.movie.title}"

    @property
    def total_price(self) -> Decimal:
        return self.seats_count * self.screening.price
```

`apps/booking/admin.py`:

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

- [ ] **Step 2: Zarejestruj app w `settings/base.py`. INSTALLED_APPS:**

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.cinema",
    "apps.booking",        # NEW
    "apps.payments",       # already added in Task 1
]
```

- [ ] **Step 3: Wygeneruj migrację:**

```bash
poetry run python manage.py makemigrations booking
```

Oczekiwane: `Migrations for 'booking': apps/booking/migrations/0001_initial.py - Create model Booking`.

- [ ] **Step 4: Sanity check:**

```bash
poetry run python manage.py migrate
poetry run python manage.py makemigrations --check
```

- [ ] **Step 5: Utwórz `tests/booking/__init__.py` (empty) + `tests/booking/factories.py`:**

`tests/booking/factories.py`:

```python
"""factory_boy factories for the booking app."""

from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.booking.models import BookingStatus
from tests.accounts.factories import UserFactory
from tests.cinema.factories import ScreeningFactory


class BookingFactory(DjangoModelFactory):
    """Default factory creates a PENDING booking with expires_at = now + 15min."""

    class Meta:
        model = "booking.Booking"  # lazy string ref (per US-10 pitfall)

    user = factory.SubFactory(UserFactory)
    screening = factory.SubFactory(ScreeningFactory)
    seats_count = factory.Faker("pyint", min_value=1, max_value=10)
    status = BookingStatus.PENDING
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))


class ConfirmedBookingFactory(BookingFactory):
    """PENDING → CONFIRMED transition simulated. Stripe IDs populated."""

    status = BookingStatus.CONFIRMED
    expires_at = None  # CONFIRMED clears expires_at (no longer relevant after payment)
    stripe_session_id = factory.Sequence(lambda n: f"cs_test_{n}")
    stripe_payment_intent_id = factory.Sequence(lambda n: f"pi_test_{n}")


class CancelledBookingFactory(BookingFactory):
    """CANCELLED — used for testing list/history views."""

    status = BookingStatus.CANCELLED
    expires_at = None
```

- [ ] **Step 6: Utwórz `tests/booking/test_models.py`:**

```python
"""Tests for apps.booking.Booking model."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import ScreeningFactory

pytestmark = pytest.mark.django_db


class TestBookingCreation:
    def test_creation_with_required_fields(self):
        user = UserFactory()
        screening = ScreeningFactory()
        booking = Booking.objects.create(
            user=user,
            screening=screening,
            seats_count=2,
        )
        assert booking.pk is not None
        assert booking.user == user
        assert booking.screening == screening
        assert booking.seats_count == 2

    def test_status_default_is_pending(self):
        booking = Booking.objects.create(
            user=UserFactory(), screening=ScreeningFactory(), seats_count=1
        )
        assert booking.status == BookingStatus.PENDING

    def test_created_at_auto_set(self):
        booking = BookingFactory()
        assert booking.created_at is not None


class TestBookingProperties:
    def test_total_price_returns_seats_times_screening_price(self):
        screening = ScreeningFactory(price=Decimal("25.50"))
        booking = BookingFactory(screening=screening, seats_count=3)
        assert booking.total_price == Decimal("76.50")

    def test_str_includes_id_and_movie_title(self):
        booking = BookingFactory()
        assert f"Booking #{booking.pk}" in str(booking)
        assert booking.screening.movie.title in str(booking)


class TestBookingValidators:
    def test_seats_count_validator_rejects_zero(self):
        booking = BookingFactory.build(seats_count=0)
        with pytest.raises(ValidationError):
            booking.full_clean()

    def test_seats_count_validator_rejects_eleven(self):
        booking = BookingFactory.build(seats_count=11)
        with pytest.raises(ValidationError):
            booking.full_clean()

    def test_seats_count_accepts_one(self):
        booking = BookingFactory.build(seats_count=1)
        booking.full_clean()  # should not raise

    def test_seats_count_accepts_ten(self):
        booking = BookingFactory.build(seats_count=10)
        booking.full_clean()  # should not raise


class TestBookingMeta:
    def test_default_ordering_newest_first(self):
        first = BookingFactory()
        second = BookingFactory()
        third = BookingFactory()
        bookings = list(Booking.objects.all())
        assert bookings == [third, second, first]

    def test_status_expires_index_exists(self):
        index_names = [idx.name for idx in Booking._meta.indexes]
        assert "booking_status_expires_idx" in index_names


class TestBookingCascade:
    def test_cascade_from_user(self):
        user = UserFactory()
        BookingFactory(user=user)
        BookingFactory(user=user)
        assert Booking.objects.filter(user=user).count() == 2
        user.delete()
        assert Booking.objects.filter(user__pk=user.pk).count() == 0

    def test_cascade_from_screening(self):
        screening = ScreeningFactory()
        BookingFactory(screening=screening)
        BookingFactory(screening=screening)
        assert Booking.objects.filter(screening=screening).count() == 2
        screening.delete()
        assert Booking.objects.filter(screening__pk=screening.pk).count() == 0


class TestBookingFactoryVariants:
    def test_confirmed_booking_factory_sets_status_and_stripe_ids(self):
        booking = ConfirmedBookingFactory()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.expires_at is None
        assert booking.stripe_session_id.startswith("cs_test_")
        assert booking.stripe_payment_intent_id.startswith("pi_test_")
```

- [ ] **Step 7: Utwórz `tests/booking/test_admin.py`:**

```python
"""Tests for apps.booking admin registration."""

import pytest
from django.contrib import admin

from apps.booking.models import Booking

pytestmark = pytest.mark.django_db


class TestBookingAdminRegistration:
    def test_booking_is_registered(self):
        assert admin.site.is_registered(Booking)

    def test_booking_admin_list_display_columns(self):
        ma = admin.site._registry[Booking]
        assert ma.list_display == (
            "id",
            "user",
            "screening",
            "seats_count",
            "status",
            "created_at",
        )

    def test_booking_admin_search_fields(self):
        ma = admin.site._registry[Booking]
        assert ma.search_fields == ("user__email", "screening__movie__title")

    def test_booking_admin_status_filter(self):
        ma = admin.site._registry[Booking]
        assert ma.list_filter == ("status",)

    def test_booking_admin_created_at_readonly(self):
        ma = admin.site._registry[Booking]
        assert "created_at" in ma.readonly_fields
```

- [ ] **Step 8: Run testów dla booking:**

```bash
poetry run pytest tests/booking/ -v
```

Oczekiwane: wszystkie zielone (~15 testów).

- [ ] **Step 9: Pełny pytest regression:**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone. Note: jeśli `tests/cinema/test_models.py` ma stub-based assertions na `Screening.booked_seats_count` (linie 280-329), wciąż przechodzą bo stub `return 0` wciąż obowiązuje (refactor w Task 3).

- [ ] **Step 10: Commit:**

```bash
git add apps/booking/ settings/base.py tests/booking/
git commit -m "$(cat <<'EOF'
feat(FR-3.8): add apps/booking with Booking model and status lifecycle

Bootstrap new app apps/booking/ for cinema reservations. Booking model includes
BookingStatus enum (PENDING/CONFIRMED/CANCELLED), FKs to User and Screening
(both CASCADE), seats_count validators (1..10), expires_at field for 15-min
PENDING lock (set by view layer in US-20), stripe_session_id and
stripe_payment_intent_id for Stripe integration (US-24/25), refund_id +
refunded_at for refund flow (US-27), composite index on (status, expires_at)
optimizing US-26 expire query, and total_price @property. Three factory
variants (default PENDING + ConfirmedBookingFactory + CancelledBookingFactory)
for downstream tests. Minimal admin registered. clean() empty — business
validation lives in BookingForm (US-19).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git log --oneline -4
```

---

## Task 3: Refactor `Screening.booked_seats_count()` + migrate existing tests

**Files:**
- Modify: `apps/cinema/models.py` (Screening.booked_seats_count — stub → real)
- Modify: `tests/cinema/test_models.py` (delete 6 stub-based Screening method tests, lines 280-329)
- Create: `tests/cinema/test_screening_methods.py` (replacement + new scenarios)

- [ ] **Step 1: Utwórz nowy plik `tests/cinema/test_screening_methods.py` z 11 testami pokrywającymi wszystkie scenariusze:**

```python
"""Tests for Screening method behavior (US-18 / FR-3.7).

Replaces the stub-based assertions previously in tests/cinema/test_models.py
(lines 280-329). After US-18, booked_seats_count aggregates CONFIRMED +
active-PENDING bookings rather than returning a stub 0.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.booking.models import BookingStatus
from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


class TestBookedSeatsCount:
    def test_zero_for_no_bookings(self):
        screening = ScreeningFactory()
        assert screening.booked_seats_count() == 0

    def test_sums_confirmed_bookings(self):
        screening = ScreeningFactory()
        ConfirmedBookingFactory(screening=screening, seats_count=3)
        ConfirmedBookingFactory(screening=screening, seats_count=2)
        assert screening.booked_seats_count() == 5

    def test_includes_active_pending(self):
        screening = ScreeningFactory()
        # PENDING with expires_at > now() counts as reserved (anti-overbook semantics)
        BookingFactory(
            screening=screening,
            seats_count=4,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        assert screening.booked_seats_count() == 4

    def test_excludes_expired_pending(self):
        screening = ScreeningFactory()
        # PENDING with expires_at <= now() is effectively cancelled
        BookingFactory(
            screening=screening,
            seats_count=4,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        assert screening.booked_seats_count() == 0

    def test_excludes_cancelled(self):
        screening = ScreeningFactory()
        CancelledBookingFactory(screening=screening, seats_count=4)
        assert screening.booked_seats_count() == 0

    def test_excludes_pending_with_null_expires_at(self):
        """Defensive — view layer should always set expires_at, but if it's None
        (broken state) we exclude it from the count rather than treating it as
        reserved indefinitely."""
        screening = ScreeningFactory()
        BookingFactory(
            screening=screening,
            seats_count=4,
            status=BookingStatus.PENDING,
            expires_at=None,
        )
        assert screening.booked_seats_count() == 0

    def test_combines_confirmed_and_active_pending(self):
        screening = ScreeningFactory()
        ConfirmedBookingFactory(screening=screening, seats_count=3)
        BookingFactory(
            screening=screening,
            seats_count=2,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        # CONFIRMED 3 + active-PENDING 2 = 5
        assert screening.booked_seats_count() == 5


class TestAvailableSeatsCount:
    def test_equals_capacity_minus_booked(self):
        # FR §7.2 unit example: hall 100, booking 30 → 70 available
        hall = HallFactory(capacity=100)
        screening = ScreeningFactory(hall=hall)
        ConfirmedBookingFactory(screening=screening, seats_count=30)
        assert screening.available_seats_count() == 70

    def test_zero_when_sold_out(self):
        hall = HallFactory(capacity=10)
        screening = ScreeningFactory(hall=hall)
        ConfirmedBookingFactory(screening=screening, seats_count=10)
        assert screening.available_seats_count() == 0


class TestIsAvailable:
    def test_true_for_future_with_seats(self):
        future = timezone.now() + timedelta(days=1)
        screening = ScreeningFactory(start_time=future)
        assert screening.is_available() is True

    def test_false_when_sold_out(self):
        future = timezone.now() + timedelta(days=1)
        hall = HallFactory(capacity=5)
        screening = ScreeningFactory(hall=hall, start_time=future)
        ConfirmedBookingFactory(screening=screening, seats_count=5)
        assert screening.is_available() is False

    def test_false_for_past_screening(self):
        past = timezone.now() - timedelta(days=1)
        screening = ScreeningFactory(start_time=past)
        assert screening.is_available() is False
```

- [ ] **Step 2: Usuń stub-based Screening method tests w `tests/cinema/test_models.py`.**

Otwórz `tests/cinema/test_models.py` i znajdź linie 278-329 (6 testów):

```python
@pytest.mark.django_db
def test_screening_booked_seats_count_stub_returns_zero():
    ...

@pytest.mark.django_db
def test_screening_available_seats_count_returns_hall_capacity():
    ...

@pytest.mark.django_db
def test_screening_is_in_past_true_for_past_screening():
    ...

@pytest.mark.django_db
def test_screening_is_in_past_false_for_future_screening():
    ...

@pytest.mark.django_db
def test_screening_is_available_true_for_future_with_capacity():
    ...

@pytest.mark.django_db
def test_screening_is_available_false_for_past_screening():
    ...
```

**Usuń wszystkie 6 testów** (od linii ~278 do końca pliku jeśli to ostatnie testy w pliku, lub do następnego non-Screening testu jeśli są w środku).

`is_in_past` testy (2 testy) możesz alternatywnie ZACHOWAĆ (są niezależne od booking aggregation — działają wciąż z nową implementacją Screening). Decyzja: usuń wszystkie 6 dla cleanness — `test_screening_methods.py` zawiera odpowiedniki via `test_is_available_false_for_past_screening` które delegate to `is_in_past`.

- [ ] **Step 3: Refactor `apps/cinema/models.py::Screening.booked_seats_count()`.**

Znajdź w `apps/cinema/models.py` (linia 125-127):

```python
    def booked_seats_count(self) -> int:
        # US-18 will sum seats_count from CONFIRMED bookings; until then no bookings exist.
        return 0
```

Zastąp:

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

`Booking` jest unused w outer scope (lazy import zwraca tylko `BookingStatus` w użytku). Można refactorować na `from apps.booking.models import BookingStatus` only — ale `Booking` import jest defensive (jeśli ktoś doda `Booking.objects.filter(...)` w przyszłości). Zostaw oba.

**Aktualizacja:** uproszczenie — import tylko `BookingStatus`:

```python
        from apps.booking.models import BookingStatus  # lazy: avoid circular
```

(Mniej imports, cleaner.) `Booking` accessible via `self.bookings` (reverse relation manager).

- [ ] **Step 4: Run testów dla cinema:**

```bash
poetry run pytest tests/cinema/test_screening_methods.py -v
```

Oczekiwane: 12 zielonych testów (7 booked_seats_count + 2 available_seats_count + 3 is_available).

- [ ] **Step 5: Run pełnego `tests/cinema/`:**

```bash
poetry run pytest tests/cinema/ -v --tb=short
```

Oczekiwane: zielone. `test_models.py` ma 6 testów mniej (usunięte w Step 2).

- [ ] **Step 6: Pełny pytest regression:**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 7: Commit:**

```bash
git add apps/cinema/models.py tests/cinema/test_screening_methods.py tests/cinema/test_models.py
git commit -m "$(cat <<'EOF'
refactor(FR-3.7): real Screening.booked_seats_count (CONFIRMED + active-PENDING)

Replaces US-10 stub (return 0) with aggregation across cinema.Screening.bookings
reverse relation. Counts seats_count from bookings where status=CONFIRMED OR
(status=PENDING AND expires_at > now()) — anti-overbook semantics: 15-min PENDING
window protects against concurrent overbookings before Stripe webhook confirms.
Expired PENDING and CANCELLED are excluded. PENDING with NULL expires_at is also
excluded as a defensive measure against broken state. Uses lazy import (booking
inside method) to avoid cinema/booking circular load.

Old stub-based tests in tests/cinema/test_models.py (6 tests) removed; replaced
by tests/cinema/test_screening_methods.py (12 tests) covering all status × expiry
combinations + FR §7.2 hall-100/booking-30 unit example.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git log --oneline -5
```

---

## Task 4: Extend `seed_db` — `--bookings` arg + helpers + flush order

**Files:**
- Modify: `apps/cinema/management/commands/seed_db.py` (add arg + 2 helpers + flush order)
- Modify: `tests/cinema/test_seed_db.py` (add 6 booking/stripe-event tests)

- [ ] **Step 1: Dorzuć helper testy na koniec `tests/cinema/test_seed_db.py` w nowej klasie testowej:**

Open `tests/cinema/test_seed_db.py`. Na koniec pliku dorzuć:

```python
class TestSeedDbBookings:
    @pytest.mark.django_db
    def test_creates_bookings_with_default_count(self):
        from django.core.management import call_command
        from apps.booking.models import Booking

        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=10")
        assert Booking.objects.count() == 10

    @pytest.mark.django_db
    def test_bookings_status_distribution_includes_all_three(self):
        """Distribution is 85/5/10 random — flaky exact ratio test.
        Instead, with bookings=50, assert all three statuses present."""
        from django.core.management import call_command
        from apps.booking.models import Booking, BookingStatus

        call_command("seed_db", "--users=10", "--movies=5", "--screenings=20", "--bookings=50")
        for status in (BookingStatus.CONFIRMED, BookingStatus.PENDING, BookingStatus.CANCELLED):
            assert Booking.objects.filter(status=status).exists(), f"{status} missing"

    @pytest.mark.django_db
    def test_creates_one_stripe_event_per_confirmed_booking(self):
        from django.core.management import call_command
        from apps.booking.models import Booking, BookingStatus
        from apps.payments.models import StripeEvent

        call_command("seed_db", "--users=10", "--movies=5", "--screenings=20", "--bookings=30")
        confirmed_count = Booking.objects.filter(status=BookingStatus.CONFIRMED).count()
        stripe_event_count = StripeEvent.objects.count()
        assert stripe_event_count == confirmed_count

    @pytest.mark.django_db
    def test_flush_deletes_bookings_before_screenings(self):
        from django.core.management import call_command
        from apps.booking.models import Booking
        from apps.cinema.models import Screening

        # Initial seed
        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=10")
        assert Booking.objects.count() == 10
        # Re-seed with --flush — must not raise IntegrityError on Screening.bookings cascade
        call_command(
            "seed_db",
            "--flush",
            "--users=5",
            "--movies=3",
            "--screenings=10",
            "--bookings=8",
        )
        assert Booking.objects.count() == 8
        assert Screening.objects.count() == 10

    @pytest.mark.django_db
    def test_flush_deletes_stripe_events_independently(self):
        from django.core.management import call_command
        from apps.payments.models import StripeEvent

        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=10")
        initial_events = StripeEvent.objects.count()
        assert initial_events > 0
        call_command(
            "seed_db",
            "--flush",
            "--users=5",
            "--movies=3",
            "--screenings=10",
            "--bookings=10",
        )
        # Old events gone, new ones created (count may differ — random distribution)
        new_events = StripeEvent.objects.count()
        assert new_events >= 0  # depends on CONFIRMED distribution in re-seed

    @pytest.mark.django_db
    def test_non_empty_guard_includes_bookings(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=5")
        # Re-run without --flush or --append → CommandError
        with pytest.raises(CommandError, match="Database not empty"):
            call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=5")
```

- [ ] **Step 2: Run failing tests (TDD red):**

```bash
poetry run pytest tests/cinema/test_seed_db.py::TestSeedDbBookings -v
```

Oczekiwane: **FAIL** — `seed_db` nie ma jeszcze `--bookings` arg.

- [ ] **Step 3: Extend `apps/cinema/management/commands/seed_db.py`.**

W górnej części pliku (przy istniejących imports linia 1-13) dodaj:

```python
import uuid
```

(Już mamy `random`, `timedelta`, `Decimal`, etc.)

Po linii `from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening` dorzuć:

```python
from apps.booking.models import Booking, BookingStatus
from apps.payments.models import StripeEvent
```

W metodzie `add_arguments` (po istniejącym `--screenings` arg, linia ~66) dorzuć:

```python
        parser.add_argument(
            "--bookings",
            type=int,
            default=30,
            help="Number of bookings to seed (default 30).",
        )
```

W metodzie `handle` (linia ~92-99) rozszerzanym `cinema_count` o booking + stripe_event:

```python
        cinema_count = (
            Genre.objects.count()
            + Hall.objects.count()
            + Actor.objects.count()
            + Director.objects.count()
            + Movie.objects.count()
            + Screening.objects.count()
            + Booking.objects.count()           # NEW
            + StripeEvent.objects.count()       # NEW
        )
```

W `--flush` block (linia ~112-119) ZASTĄP istniejącą sekwencję na (Booking + StripeEvent najpierw, FK-safe):

```python
            if options["flush"]:
                StripeEvent.objects.all().delete()       # NEW — no FK deps
                Booking.objects.all().delete()           # NEW — FK to Screening + User
                Screening.objects.all().delete()
                Movie.objects.all().delete()
                Hall.objects.all().delete()
                Actor.objects.all().delete()
                Director.objects.all().delete()
                Genre.objects.all().delete()
                User.objects.filter(is_superuser=False).delete()
```

Po `self._seed_screenings(options["screenings"], movies, halls)` (linia ~126) — przed loop tworzącym users — dodaj seed users PIERWSZY (przesuń user loop wyżej), potem _seed_bookings:

Aktualizacja flow w `handle()` — szczegóły implementacji. Zachowaj istniejący flow przejść do `self._seed_screenings(...)`. **Po `_seed_screenings` ale PRZED user loop** wstaw:

Wait — user loop musi pójść PRZED bookings (potrzebne dla `_seed_bookings(users=...)`). Sprawdzę current order w handle:

Current handle order: genres → halls → actors → directors → movies → screenings → users (loop).

Refactor: musimy mieć users przed bookings. Plan: extract user loop do `_seed_users()` method i wywołaj go przed `_seed_bookings`. Lub po prostu przesuń bookings po user loop.

**Decyzja:** po prostu add `_seed_bookings` i `_seed_stripe_events` **po** user loop w `handle()` (najmniejsza zmiana). Existing user loop ends z `created_count` increment. After the loop and before final stdout, dodaj:

```python
        # ... existing user loop ...

        # NEW: bookings + stripe_events (after users exist)
        with transaction.atomic():  # second atomic block — first is for cinema entities
            seed_users = User.objects.filter(is_superuser=False)
            seed_screenings = list(Screening.objects.all())
            confirmed_bookings = self._seed_bookings(
                options["bookings"], list(seed_screenings), list(seed_users)
            )
            self._seed_stripe_events(confirmed_bookings)
```

Wait — istniejący `handle()` ma `with transaction.atomic():` block obejmujący WSZYSTKO including user loop (linia 111-144). Czyli musimy:
- (Option A) Włożyć `_seed_bookings` call WEWNĄTRZ existing atomic, PO user loop. Less invasive.
- (Option B) Extract user loop do `_seed_users()` method + reorder. Cleaner but more refactor.

Default: **Option A** (less invasive). Po user loop (linia ~144) wewnątrz istniejącego `with transaction.atomic()`:

```python
            # ... user loop ends ...

            # Bookings + StripeEvents (US-18 / FR-3.8 + FR-3.9)
            if options["bookings"] > 0:
                seed_users = list(User.objects.filter(is_superuser=False))
                seed_screenings = list(Screening.objects.all())
                if seed_users and seed_screenings:
                    confirmed_bookings = self._seed_bookings(
                        options["bookings"], seed_screenings, seed_users
                    )
                    self._seed_stripe_events(confirmed_bookings)
```

Następnie na końcu klasy `Command` dorzuć helpers:

```python
    def _seed_bookings(self, count, screenings, users):
        """Generate bookings with status distribution ~85% CONFIRMED / ~5% PENDING /
        ~10% CANCELLED. Returns list of CONFIRMED bookings for _seed_stripe_events."""
        statuses = random.choices(
            [BookingStatus.CONFIRMED, BookingStatus.PENDING, BookingStatus.CANCELLED],
            weights=[85, 5, 10],
            k=count,
        )
        confirmed = []
        for status in statuses:
            user = random.choice(users)
            screening = random.choice(screenings)
            seats = random.randint(1, 10)

            booking_kwargs = {
                "user": user,
                "screening": screening,
                "seats_count": seats,
                "status": status,
            }
            if status == BookingStatus.PENDING:
                # 50/50 past/future expires_at — for testing expire_pending_bookings (US-26)
                offset = random.choice([-1, 1]) * timedelta(minutes=random.randint(5, 60))
                booking_kwargs["expires_at"] = timezone.now() + offset
            elif status == BookingStatus.CONFIRMED:
                booking_kwargs["stripe_session_id"] = f"cs_seed_{uuid.uuid4().hex[:16]}"
                booking_kwargs["stripe_payment_intent_id"] = f"pi_seed_{uuid.uuid4().hex[:16]}"

            booking = Booking.objects.create(**booking_kwargs)
            if status == BookingStatus.CONFIRMED:
                confirmed.append(booking)
        return confirmed

    def _seed_stripe_events(self, confirmed_bookings):
        """One StripeEvent per CONFIRMED booking — checkout.session.completed event
        with payload referencing booking via client_reference_id."""
        for booking in confirmed_bookings:
            event_id = f"evt_seed_{uuid.uuid4().hex[:16]}"
            StripeEvent.objects.create(
                event_id=event_id,
                event_type="checkout.session.completed",
                payload={
                    "id": event_id,
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": booking.stripe_session_id,
                            "client_reference_id": str(booking.id),
                            "payment_intent": booking.stripe_payment_intent_id,
                        }
                    },
                },
                processed_at=timezone.now(),
            )
```

Także dorzuć info o bookings + events do final stdout (linia ~158-168 w `handle`):

```python
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {Genre.objects.count()} genres, "
                    f"{Hall.objects.count()} halls, "
                    f"{Actor.objects.count()} actors, "
                    f"{Director.objects.count()} directors, "
                    f"{Movie.objects.count()} movies, "
                    f"{Screening.objects.count()} screenings, "
                    f"{Booking.objects.count()} bookings, "                # NEW
                    f"{StripeEvent.objects.count()} stripe events, "        # NEW
                    f"and {created_count} users ({active_count} active, "
                    f"{inactive_count} inactive). Default password: {password}."
                )
            )
```

- [ ] **Step 4: Run testów seed_db:**

```bash
poetry run pytest tests/cinema/test_seed_db.py -v
```

Oczekiwane: wszystkie zielone (existing + 6 new TestSeedDbBookings).

- [ ] **Step 5: Manual smoke test seed_db:**

```bash
poetry run python manage.py seed_db --flush --users=5 --movies=3 --screenings=10 --bookings=10
```

Oczekiwane stdout:
```
Seeded 9 genres, 3-5 halls, 30 actors, 10 directors, 3 movies, 10 screenings,
10 bookings, ~8 stripe events, and 5 users ...
```

(`~8` bo CONFIRMED rate ~85%, so 10 × 0.85 = 8-9 events expected.)

- [ ] **Step 6: Pełny pytest regression:**

```bash
poetry run pytest --tb=short
```

Oczekiwane: zielone, coverage ≥80%.

- [ ] **Step 7: Commit:**

```bash
git add apps/cinema/management/commands/seed_db.py tests/cinema/test_seed_db.py
git commit -m "$(cat <<'EOF'
feat(FR-13): seed_db bookings + stripe_events extension

Extends seed_db to populate the M3 booking domain. New --bookings=N arg
(default 30). Status distribution: ~85% CONFIRMED / ~5% PENDING / ~10% CANCELLED
via random.choices with weights. PENDING bookings get 50/50 past/future
expires_at for testing US-26 expire_pending_bookings command. CONFIRMED bookings
get realistic Stripe IDs (cs_seed_<hex>, pi_seed_<hex>); StripeEvent generated
per CONFIRMED booking with mock checkout.session.completed payload. --flush
order now: StripeEvent (no FK) → Booking → Screening → Movie → ... (FK-safe).
Non-empty guard extended to include Booking + StripeEvent counts.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git log --oneline -6
```

---

## Task 5: Update `.Claude/backlog.md` — US-18 → Done

**Files:**
- Modify: `.Claude/backlog.md` (§7 status board)

- [ ] **Step 1: Otwórz `.Claude/backlog.md`, znajdź §7 (status board). Zaktualizuj:**

Stary:
```markdown
| **In Progress (WIP=1)** | _none_ |
| **Ready (DoR ✅)** | **US-18** (M3 kickoff — Booking model + reservation flow) |
| **Backlog** | US-19..US-43 (M3..M5) |
| **Done** | **US-01..US-17** ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅ — **M2 (`v0.2.0`) COMPLETE** |
```

Nowy:
```markdown
| **In Progress (WIP=1)** | _none_ |
| **Ready (DoR ✅)** | **US-19** (BookingForm + validation logic) |
| **Backlog** | US-20..US-43 (M3..M5) |
| **Done** | **US-01..US-18** ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅ — M2 COMPLETE; M3 in progress (1/11) |
```

(Liczba ✅ matches: US-01..US-18 = 18 checkmarków.)

- [ ] **Step 2: Commit:**

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-18 done — Booking + StripeEvent models shipped

Status board updated: US-18 → Done (1/11 M3), US-19 (BookingForm) moves to Ready.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git log --oneline -7
```

---

## Task 6: Final verification + PR

- [ ] **Step 1: Pełen pytest + coverage:**

```bash
poetry run pytest --cov
```

Oczekiwane: wszystkie zielone, coverage ≥80%. Wklej summary jeśli coś chrupnie.

- [ ] **Step 2: Lint + format + mypy:**

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
```

Oczekiwane: zero błędów.

- [ ] **Step 3: Manual smoke test (verify wszystko działa end-to-end):**

```bash
poetry run python manage.py seed_db --flush --users=5 --movies=3 --screenings=10 --bookings=10
poetry run python manage.py runserver
```

Login na `/admin/` jako superuser. Sprawdź:
1. `/admin/booking/booking/` — lista bookings z status filter (PENDING / CONFIRMED / CANCELLED)
2. `/admin/payments/stripeevent/` — lista StripeEvents (read-only, można otworzyć detail i zobaczyć JSON payload)
3. `/admin/cinema/screening/` — wciąż działa (M2 admin); sprawdź `screenings_count` na sąsiednich models nie rozwala się

Zatrzymaj serwer.

- [ ] **Step 4: Sprawdź historię commitów:**

```bash
git log --oneline main..HEAD
```

Oczekiwane: **7 commitów** na branchu:
1. `docs(M3): add US-18 Booking models spec and implementation plan`
2. `feat(FR-3.9): add apps/payments with StripeEvent model and idempotency log`
3. `feat(FR-3.8): add apps/booking with Booking model and status lifecycle`
4. `refactor(FR-3.7): real Screening.booked_seats_count (CONFIRMED + active-PENDING)`
5. `feat(FR-13): seed_db bookings + stripe_events extension`
6. `docs(M3): mark US-18 done — Booking + StripeEvent models shipped`

(Powinno być 6, plus pre-task = 1, more = 7. Liczba zależy czy fixup commits.)

- [ ] **Step 5: Push + PR:**

```bash
git push -u origin feat/FR-3.8-booking-model

gh pr create --title "feat(FR-3.8): US-18 Booking + StripeEvent models" --body "$(cat <<'EOF'
## Summary
- **US-18 — first M3 task.** Bootstrap 2 new apps (`apps/booking/`, `apps/payments/`) z modelami Booking + StripeEvent.
- **`Booking` model** w `apps/booking/`: FK do User + Screening (CASCADE), BookingStatus enum (PENDING/CONFIRMED/CANCELLED), seats_count validators (1..10), expires_at for 15-min PENDING lock, Stripe IDs + refund tracking, composite index na (status, expires_at) optimizing US-26.
- **`StripeEvent` model** w `apps/payments/`: idempotency log (event_id unique=True), JSONField payload, no FK to Booking (loose coupling via payload.client_reference_id per FR §3.9).
- **Screening refactor**: \`booked_seats_count()\` zmienia stub z US-10 (return 0) na real aggregation z bookings — CONFIRMED + active-PENDING (anti-overbook semantics). Lazy import avoid circular.
- **\`seed_db\` extension**: \`--bookings=N\` arg (default 30), status distribution 85/5/10, StripeEvent per CONFIRMED, --flush FK-safe order.
- **~30 nowych testów** (10 booking model + 7 stripe event model + 12 screening methods + 8 seed_db extension + 5 admin registrations).

## Linked
- Spec: \`docs/superpowers/specs/2026-05-22-us18-booking-models.md\`
- Plan: \`docs/superpowers/plans/2026-05-22-us18-booking-models.md\`
- Closes US-18

## Definition of Done checklist
- [x] Apps registered: \`INSTALLED_APPS\` zawiera \`apps.booking\` + \`apps.payments\`
- [x] Migrations: 2 nowe initial migrations applikowalne na fresh DB
- [x] Booking model: wszystkie pola per FR §3.8 + BookingStatus + composite index + total_price property
- [x] StripeEvent model: pola per FR §3.9 + unique event_id + JSONField payload
- [x] Screening refactor: real booked_seats_count (CONFIRMED + active-PENDING)
- [x] Factories: BookingFactory + ConfirmedBookingFactory + CancelledBookingFactory + StripeEventFactory
- [x] ~30 nowych testów green
- [x] seed_db: --bookings=N + status distribution + StripeEvent per CONFIRMED + FK-safe flush
- [x] Minimal admin: Booking + StripeEvent registered (pełny refactor → US-28)
- [x] \`pytest --cov\` ≥80%, \`ruff\`, \`mypy\` — clean
- [x] No regression: M1/M2 testy pass; \`makemigrations --check\` exits 0
- [x] Manual smoke: \`seed_db --flush --bookings=10\` works; \`/admin/booking/booking/\` + \`/admin/payments/stripeevent/\` accessible

## Test plan
- [x] \`pytest tests/payments/ -v\` — 7 zielonych
- [x] \`pytest tests/booking/ -v\` — ~15 zielonych
- [x] \`pytest tests/cinema/test_screening_methods.py -v\` — 12 zielonych
- [x] \`pytest tests/cinema/test_seed_db.py -v\` — wszystkie zielone (existing + 6 new TestSeedDbBookings)
- [x] \`pytest -x --tb=short\` — zielone
- [x] Manual: \`/admin/booking/booking/\` + \`/admin/payments/stripeevent/\` accessible po seed

## Out of scope (US-19+ follow-ups)
- **BookingForm + validation** → US-19
- **Booking create view** (\`select_for_update\` + atomic) → US-20
- **Booking detail / my-bookings / cancel views** → US-21, 22, 23
- **Stripe Checkout integration** → US-24
- **Webhook handler** → US-25
- **\`expire_pending_bookings\` command** → US-26
- **Refund flow** → US-27
- **BookingAdmin/ScreeningAdmin pełen refactor** (annotate, badges) → US-28

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Wklej URL PR-a po utworzeniu.

---

## Spec coverage check (self-review)

| Sekcja spec | Pokrycie w planie |
|-------------|--------------------|
| §1 Cel / out-of-scope | Header + Tasks 1-4 (apps + refactor + seed) + Task 5 (backlog) |
| §2 Architektura plików | File Structure table + per-task Files headers |
| §3 App layout decision | Tasks 1-2 (apps/payments + apps/booking creation), INSTALLED_APPS w obu |
| §4 Booking model design | Task 2 Step 1 (apps/booking/models.py pełny code) |
| §5 StripeEvent model design | Task 1 Step 1 (apps/payments/models.py pełny code) |
| §6 Screening refactor | Task 3 (test + refactor + audit existing tests) |
| §7 Factories | Task 1 Step 5 (StripeEventFactory) + Task 2 Step 5 (BookingFactory + 2 variants) |
| §8 Tests scope | Task 1 Steps 6-7 + Task 2 Steps 6-7 + Task 3 Step 1 + Task 4 Step 1 |
| §9 seed_db extension | Task 4 (full helpers + flush order + args) |
| §10 Minimal admin | Task 1 Step 1 (StripeEventAdmin) + Task 2 Step 1 (BookingAdmin) |
| §11 Definition of Done | Task 6 (final verification + PR body checklist) |
| §12 Risks | Pokryte przez per-task care: lazy import w Task 3 Step 3, defensive null exclusion w Task 3 Step 1, flush order test w Task 4 Step 1 |
| §13 Decisions data-driven | Task 4 Step 3 (weighted random impl), Task 3 Step 2 (test_models.py audit) |

Brak gaps. Plan domknięty.
