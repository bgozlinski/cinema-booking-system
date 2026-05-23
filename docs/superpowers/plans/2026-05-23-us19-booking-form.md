# US-19 — BookingForm + validation logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dostarczyć `BookingForm` (plain `forms.Form`) z polem `seats_count` ∈ [1,10] i dwiema walidacjami serwerowymi FR-07 (dostępność miejsc + seans nie w przeszłości). Form-only US — bez widoku, bez Stripe.

**Architecture:** `apps/booking/forms.py` z `BookingForm`; `screening` wstrzykiwany przez `__init__` (keyword-only). `clean_seats_count` sprawdza `seats_count <= screening.available_seats_count()` (błąd przy polu, z liczbą dostępnych); `clean()` sprawdza `not screening.is_in_past()` (błąd non-field). Walidacja business celowo w form layer, nie w `Booking.clean()` (per spec US-18).

**Tech Stack:** Django 6 `forms.Form` + `IntegerField(min_value/max_value)` + `clean_*`, `gettext_lazy`, pytest-django, factory_boy (`ScreeningFactory`/`HallFactory`/`BookingFactory`/`ConfirmedBookingFactory`).

**Spec źródłowy:** `docs/superpowers/specs/2026-05-23-us19-booking-form.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (`tests/booking/test_forms.py`) — testy są jego scope.
- `apps/booking/forms.py` (kod aplikacji) — **default: user wkleja** pełen content z planu (Task 3). Jeśli user wybierze "sam popraw" — Claude edytuje.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

Pre-Task-1 — nowy branch off main:

```bash
git checkout main && git pull
git checkout -b feat/FR-07-booking-form
git branch --show-current   # → feat/FR-07-booking-form
```

Spec + plan (uncommitted na main) commitujemy jako pierwszy commit NA branchu (pattern PR #18..#21):

```bash
git add docs/superpowers/specs/2026-05-23-us19-booking-form.md \
        docs/superpowers/plans/2026-05-23-us19-booking-form.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-19 BookingForm spec and implementation plan

Planning artifacts for US-19 (FR-07) — pure-Django BookingForm with
seats_count [1,10] and two server-side validations: seats within
screening.available_seats_count() and screening not in the past. Form-only US;
create view + select_for_update + Stripe come in US-20. Validation lives in the
form layer (Booking.clean() intentionally empty per US-18 spec).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/forms.py` | Create | `BookingForm` — pole `seats_count` + 2 walidacje FR-07 |
| `tests/booking/test_forms.py` | Create | Unit testy `BookingForm` (~17) |
| `.Claude/backlog.md` | Modify | Status board: US-19 → Done, In Progress → US-20 (po merge) |

---

## Task 1: Write the failing test file

**Files:**
- Test: `tests/booking/test_forms.py` (Create)

- [ ] **Step 1: Write the failing tests**

```python
"""Unit tests for BookingForm (US-19 / FR-07)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.booking.forms import BookingForm
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _future_screening(capacity: int = 100):
    """Future screening (start +7d via factory default) with given hall capacity."""
    return ScreeningFactory(hall=HallFactory(capacity=capacity))


class TestBookingFormValid:
    def test_valid_seats_within_availability(self):
        screening = _future_screening(capacity=100)
        form = BookingForm(data={"seats_count": 3}, screening=screening)
        assert form.is_valid()
        assert form.cleaned_data["seats_count"] == 3

    def test_one_seat_boundary_valid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": 1}, screening=screening)
        assert form.is_valid()

    def test_ten_seats_boundary_valid(self):
        screening = _future_screening(capacity=100)
        form = BookingForm(data={"seats_count": 10}, screening=screening)
        assert form.is_valid()

    def test_seats_equal_to_available_valid(self):
        screening = _future_screening(capacity=5)
        form = BookingForm(data={"seats_count": 5}, screening=screening)
        assert form.is_valid()


class TestBookingFormFieldRange:
    def test_zero_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": 0}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_eleven_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": 11}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_missing_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_non_integer_seats_invalid(self):
        screening = _future_screening()
        form = BookingForm(data={"seats_count": "abc"}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors


class TestBookingFormAvailability:
    def test_seats_exceed_capacity_invalid(self):
        # field max_value is 10, so 6 passes field validation; availability fails
        screening = _future_screening(capacity=5)
        form = BookingForm(data={"seats_count": 6}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_error_message_includes_available_count(self):
        screening = _future_screening(capacity=4)
        form = BookingForm(data={"seats_count": 5}, screening=screening)
        assert not form.is_valid()
        assert "4" in str(form.errors["seats_count"])

    def test_confirmed_bookings_reduce_availability(self):
        screening = _future_screening(capacity=10)
        ConfirmedBookingFactory(screening=screening, seats_count=7)
        # available now 3; requesting 4 fails
        form = BookingForm(data={"seats_count": 4}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_active_pending_reduces_availability(self):
        screening = _future_screening(capacity=10)
        BookingFactory(screening=screening, seats_count=8)  # PENDING, expires +15m
        # available now 2; requesting 3 fails
        form = BookingForm(data={"seats_count": 3}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors

    def test_expired_pending_does_not_reduce_availability(self):
        screening = _future_screening(capacity=10)
        BookingFactory(
            screening=screening,
            seats_count=8,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        # expired PENDING not counted → 10 available; request 9 ok
        form = BookingForm(data={"seats_count": 9}, screening=screening)
        assert form.is_valid()

    def test_sold_out_screening_invalid(self):
        screening = _future_screening(capacity=5)
        ConfirmedBookingFactory(screening=screening, seats_count=5)
        form = BookingForm(data={"seats_count": 1}, screening=screening)
        assert not form.is_valid()
        assert "seats_count" in form.errors


class TestBookingFormPastScreening:
    def test_past_screening_invalid(self):
        screening = ScreeningFactory(
            hall=HallFactory(capacity=100),
            start_time=timezone.now() - timedelta(hours=1),
        )
        form = BookingForm(data={"seats_count": 2}, screening=screening)
        assert not form.is_valid()

    def test_past_screening_error_is_non_field(self):
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        form = BookingForm(data={"seats_count": 2}, screening=screening)
        assert not form.is_valid()
        assert form.non_field_errors()

    def test_screening_starting_now_invalid(self):
        # is_in_past() is start_time <= now(); now() at validation is later → past
        screening = ScreeningFactory(start_time=timezone.now())
        form = BookingForm(data={"seats_count": 2}, screening=screening)
        assert not form.is_valid()
        assert form.non_field_errors()
```

- [ ] **Step 2: Run tests to verify they fail (RED)**

Run: `poetry run pytest tests/booking/test_forms.py -v`
Expected: collection error / FAIL — `ModuleNotFoundError: No module named 'apps.booking.forms'` (forms.py jeszcze nie istnieje).

---

## Task 2: Implement `BookingForm`

**Files:**
- Create: `apps/booking/forms.py`

> **Role:** kod aplikacji — domyślnie **user wkleja** poniższą zawartość do `apps/booking/forms.py`. Jeśli user poprosi "popraw sam" — Claude pisze plik.

- [ ] **Step 3: Create `apps/booking/forms.py` with exact content**

```python
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.cinema.models import Screening


class BookingForm(forms.Form):
    """Reservation input form (FR-07).

    Collects only ``seats_count``. The owning view (US-20) supplies user,
    screening, status and expires_at when persisting the Booking. The screening
    being booked is injected via ``__init__`` so the two server-side validations
    can run: seats within current availability, and the screening not in the past.
    The view re-checks availability inside ``select_for_update`` (US-20) — this
    form check is the user-facing pre-check, not the authoritative race guard.
    """

    seats_count = forms.IntegerField(
        label=_("Liczba miejsc"),
        min_value=1,
        max_value=10,
        error_messages={
            "required": _("Podaj liczbę miejsc."),
            "invalid": _("Podaj poprawną liczbę miejsc."),
            "min_value": _("Musisz zarezerwować co najmniej 1 miejsce."),
            "max_value": _("Maksymalnie możesz zarezerwować 10 miejsc."),
        },
        widget=forms.NumberInput(attrs={"min": 1, "max": 10, "class": "form-control"}),
    )

    def __init__(self, *args: Any, screening: Screening, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.screening = screening

    def clean_seats_count(self) -> int:
        seats_count: int = self.cleaned_data["seats_count"]
        available = self.screening.available_seats_count()
        if seats_count > available:
            raise forms.ValidationError(
                _("Dostępnych jest tylko %(available)d miejsc — wybierz mniejszą liczbę."),
                code="exceeds_available",
                params={"available": available},
            )
        return seats_count

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if self.screening.is_in_past():
            raise forms.ValidationError(
                _("Seans już się rozpoczął — nie można zarezerwować miejsc."),
                code="screening_in_past",
            )
        return cleaned_data
```

- [ ] **Step 4: Run tests to verify they pass (GREEN)**

Run: `poetry run pytest tests/booking/test_forms.py -v`
Expected: PASS — wszystkie ~17 testów green.

---

## Task 3: Quality gates

- [ ] **Step 5: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/booking/forms.py tests/booking/test_forms.py
poetry run ruff format --check apps/booking/forms.py tests/booking/test_forms.py
poetry run mypy apps/booking/forms.py
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; cała suite green; coverage ≥80%.

**Jeśli mypy zgłosi LSP `[override]` na `__init__`** (django-stubs widzi niekompatybilną sygnaturę): dodaj `# type: ignore[override]` na linii `def __init__` z komentarzem `# extra required kwarg: screening`, ALBO zmień na `screening: Screening | None = None` + `assert screening is not None`. Zdecyduj po zobaczeniu komunikatu — preferuj `# type: ignore[override]` (cleaner intent).

---

## Task 4: Commit

- [ ] **Step 6: Commit form + tests**

```bash
git add apps/booking/forms.py tests/booking/test_forms.py
git commit -m "$(cat <<'EOF'
feat(FR-07): add BookingForm with seats + availability validation

Pure-Django BookingForm (forms.Form) collecting seats_count [1,10] with two
server-side validations: clean_seats_count enforces
seats_count <= screening.available_seats_count() (error carries the available
count); clean() rejects screenings already started (non-field error). Screening
injected via __init__. Validation lives in the form layer — Booking.clean()
stays empty per US-18. View + select_for_update + Stripe come in US-20.

17 tests in tests/booking/test_forms.py (valid/range/availability/past).

Closes US-19.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Backlog update + PR (po merge / przy PR)

- [ ] **Step 7: Update backlog status board**

W `.Claude/backlog.md` §7 status board:
- `In Progress (WIP=1)` → `US-20` (Booking create view)
- `Ready (DoR ✅)` → `US-20`... (lub _none_ jeśli US-20 wymaga brainstormingu — patrz m3_planning)
- `Done` → dopisz US-19

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-19 done — BookingForm shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 8: Push + PR**

```bash
git push -u origin feat/FR-07-booking-form
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-19) / DoD checklist / Test plan / Out of scope (US-20 view).

---

## Self-Review (wykonane)

**Spec coverage:** FR-07 form requirements → pokryte. Pole `seats_count` [1,10] (Task 2 IntegerField); `seats_count <= available` z liczbą dostępnych (clean_seats_count + test `test_error_message_includes_available_count`); `start_time > now()` (clean + `TestBookingFormPastScreening`). PENDING-with-expires liczone jako zajęte → delegowane do `available_seats_count()` (US-18) + test `test_active_pending_reduces_availability` / `test_expired_pending_does_not_reduce_availability`.

**Placeholder scan:** brak TBD/TODO — każdy step ma pełny kod/komendę.

**Type consistency:** `BookingForm(data=..., screening=...)` spójne w teście i implementacji; `seats_count` field name spójny; `available_seats_count()` / `is_in_past()` to istniejące metody `Screening` (zweryfikowane w `apps/cinema/models.py:150,153`).
