# US-23 — Cancel booking (PENDING-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cancel-booking flow (FR-10): `POST /bookings/<int:pk>/cancel/` lets the owner cancel a PENDING booking up to 1h before the screening — status → CANCELLED, flash + redirect to `/my-bookings/`. CONFIRMED + refund stays in US-27.

**Architecture:** `Booking.can_be_cancelled()` model method (PENDING + `start_time > now+1h`) is the single source of truth for FR-10; `cancel_booking` service (atomic + `select_for_update` + re-check) mirrors `create_booking` and is the shared web+API path US-27 extends with a refund; thin POST-only `BookingCancelView` calls it. The US-22 disabled "Anuluj" placeholder becomes a real POST form gated on `can_be_cancelled`.

**Tech Stack:** Django 6 model method + CBV (`LoginRequiredMixin`, `View`), `transaction.atomic` + `select_for_update`, pytest-django, factory_boy.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-23-us23-booking-cancel.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (`tests/booking/test_cancel_view.py` + appendy do `test_models.py`/`test_services.py`).
- Kod aplikacji (`apps/booking/models.py`, `services.py`, `views.py`, `urls.py`, `templates/booking/my_bookings.html`) — **default: user wkleja** z planu. Jeśli user poprosi "popraw sam" — Claude edytuje.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

```bash
git checkout main && git pull
git checkout -b feat/FR-10-booking-cancel
git branch --show-current   # → feat/FR-10-booking-cancel
```

Spec + plan jako pierwszy commit na branchu:

```bash
git add docs/superpowers/specs/2026-05-23-us23-booking-cancel.md \
        docs/superpowers/plans/2026-05-23-us23-booking-cancel.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-23 booking cancel spec and plan

Planning artifacts for US-23 (FR-10) — cancel PENDING bookings up to 1h before
the screening. Booking.can_be_cancelled() + cancel_booking service (atomic +
select_for_update) + POST-only BookingCancelView; wires the US-22 "Anuluj"
placeholder. CONFIRMED + Stripe refund deferred to US-27. No migrations.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/models.py` | Modify | + `Booking.can_be_cancelled()` |
| `apps/booking/services.py` | Modify | + `cancel_booking` + `BookingNotCancellableError` |
| `apps/booking/views.py` | Modify | + `BookingCancelView` |
| `apps/booking/urls.py` | Modify | + `booking:cancel` route |
| `templates/booking/my_bookings.html` | Modify | "Anuluj" disabled → POST form |
| `tests/booking/test_models.py` | Modify | + `TestCanBeCancelled` |
| `tests/booking/test_services.py` | Modify | + `TestCancelBooking` |
| `tests/booking/test_cancel_view.py` | Create | `BookingCancelView` tests |
| `.Claude/backlog.md` | Modify | US-23 → Done (po merge) |

Brak migracji (`can_be_cancelled` to method, nie pole).

---

## Task 1: `Booking.can_be_cancelled()` model method

**Files:**
- Test: `tests/booking/test_models.py` (Modify — append)
- Modify: `apps/booking/models.py`

- [ ] **Step 1: Append the failing tests** (`tests/booking/test_models.py`)

Add at the end of the file:

```python
class TestCanBeCancelled:
    def test_pending_future_over_1h_true(self):
        booking = BookingFactory()  # PENDING, screening +7d
        assert booking.can_be_cancelled() is True

    def test_pending_under_1h_false(self):
        screening = ScreeningFactory(start_time=timezone.now() + timedelta(minutes=30))
        booking = BookingFactory(screening=screening)
        assert booking.can_be_cancelled() is False

    def test_pending_past_false(self):
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(days=1))
        booking = BookingFactory(screening=screening)
        assert booking.can_be_cancelled() is False

    def test_confirmed_false(self):
        booking = ConfirmedBookingFactory()  # future, but CONFIRMED → US-23 PENDING-only
        assert booking.can_be_cancelled() is False

    def test_cancelled_false(self):
        booking = CancelledBookingFactory()
        assert booking.can_be_cancelled() is False
```

Ensure the imports at the top of `tests/booking/test_models.py` include (add any missing):

```python
from datetime import timedelta

from django.utils import timezone

from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)
from tests.cinema.factories import ScreeningFactory
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_models.py::TestCanBeCancelled -v`
Expected: FAIL — `AttributeError: 'Booking' object has no attribute 'can_be_cancelled'`.

- [ ] **Step 3: Add `can_be_cancelled` to `apps/booking/models.py`** (user pastes)

Add imports at the top:

```python
from datetime import timedelta

from django.utils import timezone
```

Add the method on `Booking` (e.g. just after `total_price`):

```python
    def can_be_cancelled(self) -> bool:
        """True when this booking may still be cancelled by its owner (FR-10).

        US-23 scope: PENDING bookings up to 1h before the screening. US-27 will
        broaden this to CONFIRMED (which additionally requires a Stripe refund).
        """
        return (
            self.status == BookingStatus.PENDING
            and self.screening.start_time > timezone.now() + timedelta(hours=1)
        )
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/booking/test_models.py::TestCanBeCancelled -v`
Expected: PASS (5 tests).

---

## Task 2: `cancel_booking` service

**Files:**
- Test: `tests/booking/test_services.py` (Modify — append)
- Modify: `apps/booking/services.py`

- [ ] **Step 1: Append the failing tests** (`tests/booking/test_services.py`)

Add at the end of the file (imports `cancel_booking`, `BookingNotCancellableError`, `CancelledBookingFactory`, `ConfirmedBookingFactory`, `timedelta` — add any missing to the top import block):

```python
class TestCancelBooking:
    def test_cancels_pending(self):
        booking = BookingFactory()  # PENDING, future +7d
        result = cancel_booking(booking=booking)
        assert result.status == BookingStatus.CANCELLED
        assert result.expires_at is None
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_raises_for_confirmed(self):
        booking = ConfirmedBookingFactory()
        with pytest.raises(NotCancellableError := __import__("apps.booking.services", fromlist=["BookingNotCancellableError"]).BookingNotCancellableError):
            cancel_booking(booking=booking)
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_raises_when_too_late(self):
        screening = ScreeningFactory(start_time=timezone.now() + timedelta(minutes=30))
        booking = BookingFactory(screening=screening)
        with pytest.raises(BookingNotCancellableError):
            cancel_booking(booking=booking)
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING

    def test_raises_when_already_cancelled(self):
        booking = CancelledBookingFactory()
        with pytest.raises(BookingNotCancellableError):
            cancel_booking(booking=booking)
```

> Replace the awkward `__import__` line — the intended import is at the top of the file. Use this clean version instead:

```python
class TestCancelBooking:
    def test_cancels_pending(self):
        booking = BookingFactory()  # PENDING, future +7d
        result = cancel_booking(booking=booking)
        assert result.status == BookingStatus.CANCELLED
        assert result.expires_at is None
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_raises_for_confirmed(self):
        booking = ConfirmedBookingFactory()
        with pytest.raises(BookingNotCancellableError):
            cancel_booking(booking=booking)
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_raises_when_too_late(self):
        screening = ScreeningFactory(start_time=timezone.now() + timedelta(minutes=30))
        booking = BookingFactory(screening=screening)
        with pytest.raises(BookingNotCancellableError):
            cancel_booking(booking=booking)
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING

    def test_raises_when_already_cancelled(self):
        booking = CancelledBookingFactory()
        with pytest.raises(BookingNotCancellableError):
            cancel_booking(booking=booking)
```

Top-of-file imports to ensure present in `tests/booking/test_services.py`:

```python
from datetime import timedelta

from django.utils import timezone

from apps.booking.services import (
    BookingNotCancellableError,
    NotEnoughSeatsError,
    ScreeningInPastError,
    cancel_booking,
    create_booking,
)
from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)
from tests.cinema.factories import HallFactory, ScreeningFactory
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_services.py::TestCancelBooking -v`
Expected: FAIL — `ImportError: cannot import name 'cancel_booking'` / `BookingNotCancellableError`.

- [ ] **Step 3: Append to `apps/booking/services.py`** (user pastes)

```python
class BookingNotCancellableError(BookingError):
    """Booking can't be cancelled (wrong status, too late, or already cancelled)."""

    def __init__(self) -> None:
        super().__init__("Tej rezerwacji nie można już anulować.")


def cancel_booking(*, booking: Booking) -> Booking:
    """Cancel a PENDING booking race-safely (FR-10).

    Locks the booking row, re-checks can_be_cancelled() under the lock, flips
    status to CANCELLED and clears expires_at. Raises BookingNotCancellableError
    if the booking is no longer cancellable. Caller verifies ownership. US-27 will
    add a Stripe refund branch for CONFIRMED bookings before the status change.
    """
    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(pk=booking.pk)
        if not locked.can_be_cancelled():
            raise BookingNotCancellableError()
        locked.status = BookingStatus.CANCELLED
        locked.expires_at = None
        locked.save(update_fields=["status", "expires_at"])
    return locked
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/booking/test_services.py -v`
Expected: PASS (existing create_booking tests + 4 new cancel tests).

- [ ] **Step 5: Commit (model + service)**

```bash
git add apps/booking/models.py apps/booking/services.py \
        tests/booking/test_models.py tests/booking/test_services.py
git commit -m "$(cat <<'EOF'
feat(FR-10): add can_be_cancelled + cancel_booking service

Booking.can_be_cancelled() encodes the FR-10 rule (PENDING up to 1h before the
screening; US-27 broadens to CONFIRMED). cancel_booking locks the booking row,
re-checks under the lock, flips status to CANCELLED and clears expires_at, or
raises BookingNotCancellableError. Mirrors create_booking; US-27 adds the refund
branch.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `BookingCancelView` + URL + template

**Files:**
- Test: `tests/booking/test_cancel_view.py` (Create)
- Modify: `apps/booking/views.py`, `apps/booking/urls.py`, `templates/booking/my_bookings.html`

- [ ] **Step 1: Write the failing tests** (`tests/booking/test_cancel_view.py`)

```python
"""Tests for BookingCancelView (US-23 / FR-10)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.booking.models import BookingStatus
from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import ScreeningFactory

pytestmark = pytest.mark.django_db


def _cancel_url(booking):
    return reverse("booking:cancel", kwargs={"pk": booking.pk})


class TestBookingCancelView:
    def test_anonymous_redirected_to_login(self, client):
        booking = BookingFactory()
        resp = client.post(_cancel_url(booking))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url

    def test_get_not_allowed(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_cancel_url(booking))
        assert resp.status_code == 405

    def test_owner_cancels_pending(self, client):
        booking = BookingFactory()  # PENDING, future +7d
        client.force_login(booking.user)
        resp = client.post(_cancel_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:my_bookings")
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED
        assert any("anulowana" in str(m).lower() for m in resp.context["messages"])

    def test_non_owner_404(self, client):
        booking = BookingFactory()
        client.force_login(UserFactory())  # different user
        resp = client.post(_cancel_url(booking))
        assert resp.status_code == 404
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING

    def test_not_cancellable_flashes_error(self, client):
        booking = ConfirmedBookingFactory()  # CONFIRMED → not cancellable in US-23
        client.force_login(booking.user)
        resp = client.post(_cancel_url(booking), follow=True)
        assert resp.redirect_chain[-1][0] == reverse("booking:my_bookings")
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert any("nie można" in str(m).lower() for m in resp.context["messages"])

    def test_404_for_missing_booking(self, client):
        client.force_login(UserFactory())
        resp = client.post(reverse("booking:cancel", kwargs={"pk": 999999}))
        assert resp.status_code == 404
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_cancel_view.py -v`
Expected: FAIL — `NoReverseMatch` for `booking:cancel`.

- [ ] **Step 3: Append `BookingCancelView` to `apps/booking/views.py`** (user pastes)

Add `cancel_booking` to the services import:

```python
from apps.booking.services import BookingError, cancel_booking, create_booking
```

Append the view:

```python
class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        try:
            cancel_booking(booking=booking)
        except BookingError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Rezerwacja została anulowana.")
        return redirect("booking:my_bookings")
```

> mypy: `get_object_or_404(Booking, pk=pk, user=request.user)` hits the same django-stubs `user` lookup issue as US-22 (dev pitfall #12). If flagged, cast: `user=cast("User", request.user)` (the `TYPE_CHECKING`/`cast` imports already exist from US-22) or `user=request.user.pk`.

- [ ] **Step 4: Add the route to `apps/booking/urls.py`** (user edits)

```python
from django.urls import path

from apps.booking.views import (
    BookingCancelView,
    BookingCreateView,
    BookingDetailView,
    MyBookingsView,
)

app_name = "booking"

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="detail"),
    path("bookings/<int:pk>/cancel/", BookingCancelView.as_view(), name="cancel"),
    path("my-bookings/", MyBookingsView.as_view(), name="my_bookings"),
]
```

- [ ] **Step 5: Wire the "Anuluj" button in `templates/booking/my_bookings.html`** (user edits)

Replace the disabled placeholder line:

```django
            {% if active_tab == 'upcoming' and booking.status != 'CANCELLED' %}<button class="btn btn-sm btn-outline-danger" disabled title="Dostępne wkrótce">Anuluj</button>{% endif %}
```

with a real POST form gated on `can_be_cancelled` (single line — Django tag rules):

```django
            {% if booking.can_be_cancelled %}<form method="post" action="{% url 'booking:cancel' pk=booking.pk %}" class="d-inline">{% csrf_token %}<button type="submit" class="btn btn-sm btn-outline-danger">Anuluj</button></form>{% endif %}
```

- [ ] **Step 6: Run → GREEN**

Run: `poetry run pytest tests/booking/test_cancel_view.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit (view + url + template)**

```bash
git add apps/booking/views.py apps/booking/urls.py \
        templates/booking/my_bookings.html tests/booking/test_cancel_view.py
git commit -m "$(cat <<'EOF'
feat(FR-10): add BookingCancelView at /bookings/<id>/cancel/

POST-only, owner-scoped (404 for non-owners) view that calls cancel_booking and
flashes success/error before redirecting to my-bookings. Wires the US-22 "Anuluj"
placeholder into a real POST form gated on can_be_cancelled (PENDING + >1h).

Closes US-23.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Quality gates

- [ ] **Step 1: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/booking tests/booking
poetry run ruff format --check apps/booking tests/booking
poetry run mypy apps/booking
poetry run python manage.py makemigrations --check --dry-run   # expect: no changes
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; `makemigrations --check` exits 0 (method, not field); full suite green (incl. US-22 my-bookings budget cap 6 — `can_be_cancelled` reads prefetched screening, no new query); coverage ≥80%.

---

## Task 5: Backlog + PR

- [ ] **Step 1: Update `.Claude/backlog.md` status board**

- `Done` → append US-23; M3 count → 6/11
- `Ready (DoR ✅)` → US-26 (`expire_pending_bookings` command) — plan-directly per m3_planning (next non-Stripe task; US-24/25 Stripe come after)

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-23 done — cancel booking (PENDING) shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-10-booking-cancel
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-23) / DoD checklist / Test plan / Out of scope (US-27 CONFIRMED refund, US-26 auto-expire).

---

## Self-Review (wykonane)

**Spec coverage:** §3 model method → Task 1. §4 service → Task 2. §5 view → Task 3 Step 3. §6 URL → Task 3 Step 4. §7 template → Task 3 Step 5. §8 tests → Tasks 1-3 (model 5 + service 4 + view 6 = 15). §9 DoD → covered. §10 risk #1 (race) → `test_raises_when_already_cancelled` + select_for_update. §10 risk #2 (mypy user lookup) → Task 3 Step 3 note. §10 risk #4 (N+1 budget) → Task 4 note.

**Placeholder scan:** Task 2 Step 1 intentionally shows an awkward `__import__` line then replaces it with the clean version — the clean block is what gets pasted; no real placeholder remains. No TBD/TODO elsewhere; every step has full code/command.

**Type consistency:** `can_be_cancelled()` (method, no args, bool) used in model, template (`booking.can_be_cancelled`), service re-check, and tests. `cancel_booking(*, booking) -> Booking` consistent across service def, view call, tests. `BookingNotCancellableError(BookingError)` raised in service, caught as `BookingError` in view, asserted in service tests. URL `booking:cancel` consistent in urls, view tests, template.
