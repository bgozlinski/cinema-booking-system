# US-20 — Booking create view Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Race-safe booking creation (FR-07): logged-in user opens `/screenings/<id>/book/`, submits seats, gets a PENDING booking (15-min window) + redirect to a stubbed checkout, all guarded by `transaction.atomic()` + `select_for_update()` on the Screening row.

**Architecture:** Three layers — thin `BookingCreateView` (HTTP/auth/form), a shared `apps/booking/services.py::create_booking` (atomic + lock + authoritative re-check + PENDING create, reused by the M4 API), and a `apps/payments/services.py::create_checkout_session` stub (returns `(url, session_id)`; US-24 fills it with the real Stripe SDK). Stripe call sits AFTER commit so the row lock is never held across a network call.

**Tech Stack:** Django 6 CBV (`LoginRequiredMixin`, `View`), `transaction.atomic` + `select_for_update`, pytest-django (incl. one `transaction=True` threaded test), factory_boy, vanilla JS for live total.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-23-us20-booking-create-design.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (`tests/payments/test_services.py`, `tests/booking/test_services.py`, `tests/booking/test_services_concurrency.py`, `tests/booking/test_views.py`) — testy są jego scope.
- Kod aplikacji (`apps/payments/services.py`, `apps/booking/services.py`, `apps/booking/views.py`, `apps/booking/urls.py`, edycja `settings/urls.py`, `templates/booking/booking_form.html`, edycja 2 cinema templateów) — **default: user wkleja** content z planu. Jeśli user poprosi "popraw sam" — Claude edytuje.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

```bash
git checkout main && git pull
git checkout -b feat/FR-07-booking-create
git branch --show-current   # → feat/FR-07-booking-create
```

Spec + plan jako pierwszy commit na branchu (pattern PR #18..#21):

```bash
git add docs/superpowers/specs/2026-05-23-us20-booking-create-design.md \
        docs/superpowers/plans/2026-05-23-us20-booking-create.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-20 booking create view design and plan

Brainstorming + planning artifacts for US-20 (FR-07). Three layers: thin
BookingCreateView, shared booking.services.create_booking (atomic +
select_for_update + PENDING), payments.services.create_checkout_session stub
(real Stripe in US-24). Stripe call after commit; race-loss → form re-render;
one threaded concurrency test. No migrations.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/payments/services.py` | Create | `create_checkout_session(booking)` stub → `(url, session_id)` |
| `apps/booking/services.py` | Create | `create_booking` + `BookingError`/`NotEnoughSeatsError`/`ScreeningInPastError` |
| `apps/booking/views.py` | Create | `BookingCreateView(LoginRequiredMixin, View)` |
| `apps/booking/urls.py` | Create | `app_name="booking"` + `booking:create` |
| `settings/urls.py` | Modify | include booking urls |
| `templates/booking/booking_form.html` | Create | summary + form + JS live total |
| `templates/cinema/screening_list.html` | Modify:46-48 | time-pill → `booking:create` |
| `templates/cinema/movie_detail.html` | Modify:135 | time-pill → `booking:create` |
| `tests/payments/test_services.py` | Create | stub test |
| `tests/booking/test_services.py` | Create | service happy/errors (deterministic) |
| `tests/booking/test_services_concurrency.py` | Create | 1 threaded race test |
| `tests/booking/test_views.py` | Create | view auth/render/POST tests |
| `.Claude/backlog.md` | Modify | US-20 → Done (po merge) |

No migrations (zero zmian modeli).

---

## Task 1: Payments checkout stub

**Files:**
- Test: `tests/payments/test_services.py` (Create)
- Create: `apps/payments/services.py`

- [ ] **Step 1: Write the failing test** (`tests/payments/test_services.py`)

```python
"""Unit test for the Stripe checkout stub (US-20 / FR-21 placeholder)."""

import pytest
from django.urls import reverse

from apps.payments.services import create_checkout_session
from tests.booking.factories import BookingFactory

pytestmark = pytest.mark.django_db


def test_create_checkout_session_returns_movie_detail_url_and_empty_session():
    booking = BookingFactory()
    url, session_id = create_checkout_session(booking)
    assert url == reverse("cinema:movie_detail", kwargs={"pk": booking.screening.movie_id})
    assert session_id == ""
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/payments/test_services.py -v`
Expected: `ModuleNotFoundError: No module named 'apps.payments.services'`.

- [ ] **Step 3: Create `apps/payments/services.py`** (user pastes)

```python
from django.urls import reverse

from apps.booking.models import Booking


def create_checkout_session(booking: Booking) -> tuple[str, str]:
    """Return (checkout_url, session_id) for a PENDING booking.

    STUB (US-20): returns the screening's movie detail URL and an empty session
    id — no Stripe call yet. US-24 replaces the body with
    stripe.checkout.Session.create(...) per FR-21 and returns (session.url, session.id).
    """
    checkout_url = reverse("cinema:movie_detail", kwargs={"pk": booking.screening.movie_id})
    return checkout_url, ""
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/payments/test_services.py -v`
Expected: PASS.

---

## Task 2: Booking service (deterministic)

**Files:**
- Test: `tests/booking/test_services.py` (Create)
- Create: `apps/booking/services.py`

- [ ] **Step 1: Write the failing tests** (`tests/booking/test_services.py`)

```python
"""Tests for booking.services.create_booking (US-20 / FR-07)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.booking.services import (
    NotEnoughSeatsError,
    ScreeningInPastError,
    create_booking,
)
from tests.accounts.factories import UserFactory
from tests.booking.factories import ConfirmedBookingFactory
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _future_screening(capacity: int = 100):
    return ScreeningFactory(hall=HallFactory(capacity=capacity))


class TestCreateBookingSuccess:
    def test_creates_pending_with_expiry(self):
        user = UserFactory()
        screening = _future_screening(capacity=50)
        before = timezone.now()
        booking, _url = create_booking(user=user, screening=screening, seats_count=3)
        assert booking.status == BookingStatus.PENDING
        assert booking.seats_count == 3
        assert booking.user == user
        assert booking.screening == screening
        assert booking.expires_at is not None
        delta = booking.expires_at - before
        assert timedelta(minutes=14) <= delta <= timedelta(minutes=16)

    def test_returns_movie_detail_checkout_url(self):
        screening = _future_screening()
        _booking, url = create_booking(user=UserFactory(), screening=screening, seats_count=1)
        assert url == reverse("cinema:movie_detail", kwargs={"pk": screening.movie_id})

    def test_does_not_set_session_id_with_stub(self):
        screening = _future_screening()
        booking, _url = create_booking(user=UserFactory(), screening=screening, seats_count=1)
        assert booking.stripe_session_id == ""


class TestCreateBookingErrors:
    def test_raises_when_seats_exceed_available(self):
        screening = _future_screening(capacity=10)
        ConfirmedBookingFactory(screening=screening, seats_count=8)  # available 2
        with pytest.raises(NotEnoughSeatsError) as exc:
            create_booking(user=UserFactory(), screening=screening, seats_count=3)
        assert exc.value.available == 2
        assert Booking.objects.filter(status=BookingStatus.PENDING).count() == 0

    def test_raises_for_past_screening(self):
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        with pytest.raises(ScreeningInPastError):
            create_booking(user=UserFactory(), screening=screening, seats_count=1)

    def test_sequential_overbooking_impossible(self):
        screening = _future_screening(capacity=5)
        create_booking(user=UserFactory(), screening=screening, seats_count=4)
        with pytest.raises(NotEnoughSeatsError):
            create_booking(user=UserFactory(), screening=screening, seats_count=2)
        booked = sum(
            b.seats_count
            for b in Booking.objects.filter(screening=screening, status=BookingStatus.PENDING)
        )
        assert booked <= screening.hall.capacity
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_services.py -v`
Expected: `ImportError`/`ModuleNotFoundError` — `apps.booking.services` missing.

- [ ] **Step 3: Create `apps/booking/services.py`** (user pastes)

```python
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.cinema.models import Screening
from apps.payments.services import create_checkout_session


class BookingError(Exception):
    """Base for booking-creation domain errors (caught by the view)."""


class NotEnoughSeatsError(BookingError):
    """Requested seats exceed availability at lock time (race lost or sold out)."""

    def __init__(self, available: int) -> None:
        self.available = available
        super().__init__(
            f"Dostępnych jest tylko {available} miejsc — wybierz mniejszą liczbę."
        )


class ScreeningInPastError(BookingError):
    """Screening already started by lock time."""

    def __init__(self) -> None:
        super().__init__("Seans już się rozpoczął — nie można zarezerwować miejsc.")


def create_booking(*, user, screening: Screening, seats_count: int) -> tuple[Booking, str]:
    """Create a PENDING booking race-safely and return (booking, checkout_url).

    Locks the Screening row, re-checks availability + start time under the lock
    (authoritative — the form check in US-19 is a pre-check), creates the PENDING
    booking with a 15-minute expiry, commits, then (outside the lock) creates the
    Stripe checkout session (stubbed until US-24).

    Caller (BookingForm / API serializer) owns seats_count range [1, 10]; this
    service enforces only the lock-dependent rules.
    """
    with transaction.atomic():
        locked = Screening.objects.select_for_update().get(pk=screening.pk)
        if locked.is_in_past():
            raise ScreeningInPastError()
        available = locked.available_seats_count()
        if seats_count > available:
            raise NotEnoughSeatsError(available=available)
        booking = Booking.objects.create(
            user=user,
            screening=locked,
            seats_count=seats_count,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

    # Lock released on commit — external call must NOT hold the row lock (US-24).
    checkout_url, session_id = create_checkout_session(booking)
    if session_id:
        booking.stripe_session_id = session_id
        booking.save(update_fields=["stripe_session_id"])

    return booking, checkout_url
```

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/booking/test_services.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit (service layer + stub)**

```bash
git add apps/payments/services.py apps/booking/services.py \
        tests/payments/test_services.py tests/booking/test_services.py
git commit -m "$(cat <<'EOF'
feat(FR-07): add create_booking service + Stripe checkout stub

booking.services.create_booking locks the Screening row, re-checks availability
and start time under the lock, creates a PENDING booking (expires_at = now+15m),
then creates the checkout session AFTER commit (lock never held across the
network call). NotEnoughSeatsError/ScreeningInPastError signal failures.
payments.services.create_checkout_session is a stub returning the movie detail
URL + empty session id — US-24 fills it with the real Stripe SDK.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Concurrency proof (threaded)

**Files:**
- Test: `tests/booking/test_services_concurrency.py` (Create)

> No new app code — proves the Task 2 `select_for_update` lock under real concurrency.

- [ ] **Step 1: Write the test** (`tests/booking/test_services_concurrency.py`)

```python
"""Concurrency proof for create_booking row-locking (US-20 / §5.2).

Requires a real DB transaction (transaction=True) + Postgres row locks; SQLite
won't truly serialize. Each thread uses its own connection and must close it.
"""

import threading

import pytest
from django.db import connection

from apps.booking.models import Booking, BookingStatus
from apps.booking.services import NotEnoughSeatsError, create_booking
from tests.accounts.factories import UserFactory
from tests.cinema.factories import HallFactory, ScreeningFactory


@pytest.mark.django_db(transaction=True)
def test_concurrent_booking_no_overbooking():
    screening = ScreeningFactory(hall=HallFactory(capacity=5))
    users = [UserFactory(), UserFactory()]
    barrier = threading.Barrier(2)
    results: dict[int, str] = {}

    def worker(idx: int) -> None:
        barrier.wait()  # release both threads together to maximize contention
        try:
            create_booking(user=users[idx], screening=screening, seats_count=3)
            results[idx] = "ok"
        except NotEnoughSeatsError:
            results[idx] = "rejected"
        finally:
            connection.close()  # close this thread's connection

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # capacity 5, both want 3 → exactly one wins, the other is rejected
    assert sorted(results.values()) == ["ok", "rejected"]
    booked = sum(
        b.seats_count
        for b in Booking.objects.filter(screening=screening, status=BookingStatus.PENDING)
    )
    assert booked == 3
    assert booked <= 5
```

- [ ] **Step 2: Run → GREEN** (impl already exists from Task 2)

Run: `poetry run pytest tests/booking/test_services_concurrency.py -v`
Expected: PASS. If it errors with a DB-locking/connection issue, confirm tests run against Postgres (not SQLite) — see "Dev pitfall #11" note below.

- [ ] **Step 3: Commit**

```bash
git add tests/booking/test_services_concurrency.py
git commit -m "$(cat <<'EOF'
test(FR-07): prove create_booking prevents concurrent overbooking

Threaded test (transaction=True + Barrier) — two users race to book 3 seats on a
5-seat screening; exactly one wins, total booked stays within capacity. Proves
the select_for_update row lock actually serializes the re-check.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

> **Dev pitfall #11:** pytest-django wraps each test in a transaction by default, so `select_for_update` won't serialize across threads. This test needs `@pytest.mark.django_db(transaction=True)` (truncate-based, slower), a separate DB connection per thread, and `connection.close()` in `finally`. Real row locks need Postgres — SQLite won't truly serialize.

---

## Task 4: View + URLs

**Files:**
- Test: `tests/booking/test_views.py` (Create)
- Create: `apps/booking/views.py`, `apps/booking/urls.py`
- Modify: `settings/urls.py:10`

- [ ] **Step 1: Write the failing tests** (`tests/booking/test_views.py`)

```python
"""Tests for BookingCreateView (US-20 / FR-07)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.booking.services import NotEnoughSeatsError
from tests.accounts.factories import UserFactory
from tests.booking.factories import ConfirmedBookingFactory
from tests.cinema.factories import HallFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _future_screening(capacity: int = 100):
    return ScreeningFactory(hall=HallFactory(capacity=capacity))


def _book_url(screening):
    return reverse("booking:create", kwargs={"pk": screening.pk})


class TestAuth:
    def test_get_requires_login(self, client):
        screening = _future_screening()
        resp = client.get(_book_url(screening))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert "next=" in resp.url

    def test_post_requires_login(self, client):
        screening = _future_screening()
        resp = client.post(_book_url(screening), {"seats_count": 2})
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert Booking.objects.count() == 0


class TestGet:
    def test_renders_form_and_summary(self, client):
        client.force_login(UserFactory())
        screening = _future_screening()
        resp = client.get(_book_url(screening))
        assert resp.status_code == 200
        assert "form" in resp.context
        assert resp.context["screening"] == screening
        assert "booking/booking_form.html" in [t.name for t in resp.templates]

    def test_404_for_missing_screening(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse("booking:create", kwargs={"pk": 999999}))
        assert resp.status_code == 404


class TestPost:
    def test_valid_creates_booking_and_redirects(self, client):
        user = UserFactory()
        client.force_login(user)
        screening = _future_screening(capacity=50)
        resp = client.post(_book_url(screening), {"seats_count": 3})
        assert resp.status_code == 302
        assert resp.url == reverse("cinema:movie_detail", kwargs={"pk": screening.movie_id})
        booking = Booking.objects.get(user=user, screening=screening)
        assert booking.status == BookingStatus.PENDING
        assert booking.seats_count == 3

    def test_valid_sets_success_message(self, client):
        client.force_login(UserFactory())
        screening = _future_screening()
        resp = client.post(_book_url(screening), {"seats_count": 1}, follow=True)
        msgs = [str(m) for m in resp.context["messages"]]
        assert any("Rezerwacja" in m for m in msgs)

    def test_invalid_form_rerenders_no_booking(self, client):
        client.force_login(UserFactory())
        screening = _future_screening()
        resp = client.post(_book_url(screening), {"seats_count": 0})
        assert resp.status_code == 200
        assert "seats_count" in resp.context["form"].errors
        assert Booking.objects.count() == 0

    def test_service_error_rerenders_with_nonfield_error(self, client):
        client.force_login(UserFactory())
        screening = _future_screening(capacity=50)
        with patch(
            "apps.booking.views.create_booking",
            side_effect=NotEnoughSeatsError(available=2),
        ):
            resp = client.post(_book_url(screening), {"seats_count": 3})
        assert resp.status_code == 200
        assert resp.context["form"].non_field_errors()
        assert Booking.objects.count() == 0

    def test_past_screening_rerenders_with_error(self, client):
        client.force_login(UserFactory())
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        resp = client.post(_book_url(screening), {"seats_count": 1})
        assert resp.status_code == 200
        assert resp.context["form"].non_field_errors()
        assert Booking.objects.count() == 0
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_views.py -v`
Expected: FAIL — `NoReverseMatch` for `booking:create` (URL not registered) / view missing.

- [ ] **Step 3: Create `apps/booking/views.py`** (user pastes)

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.booking.forms import BookingForm
from apps.booking.services import BookingError, create_booking
from apps.cinema.models import Screening


class BookingCreateView(LoginRequiredMixin, View):
    template_name = "booking/booking_form.html"

    def _get_screening(self, pk: int) -> Screening:
        return get_object_or_404(
            Screening.objects.select_related("movie", "hall"), pk=pk
        )

    def get(self, request, pk: int):
        screening = self._get_screening(pk)
        form = BookingForm(screening=screening)
        return render(request, self.template_name, {"screening": screening, "form": form})

    def post(self, request, pk: int):
        screening = self._get_screening(pk)
        form = BookingForm(request.POST, screening=screening)
        if not form.is_valid():
            return render(request, self.template_name, {"screening": screening, "form": form})
        try:
            _booking, checkout_url = create_booking(
                user=request.user,
                screening=screening,
                seats_count=form.cleaned_data["seats_count"],
            )
        except BookingError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"screening": screening, "form": form})

        messages.success(request, "Rezerwacja utworzona (PENDING) — dokończ płatność.")
        return redirect(checkout_url)
```

- [ ] **Step 4: Create `apps/booking/urls.py`** (user pastes)

```python
from django.urls import path

from apps.booking.views import BookingCreateView

app_name = "booking"

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
]
```

- [ ] **Step 5: Edit `settings/urls.py`** — add the booking include after the cinema include (user edits)

Current `settings/urls.py:10`:

```python
    path("", include("apps.cinema.urls", namespace="cinema")),  # ← new
```

Add the line directly below it:

```python
    path("", include("apps.cinema.urls", namespace="cinema")),  # ← new
    path("", include("apps.booking.urls", namespace="booking")),
```

- [ ] **Step 6: Run → GREEN**

Run: `poetry run pytest tests/booking/test_views.py -v`
Expected: PASS (9 tests). The booking page renders because Task 5 creates the template — if `test_renders_form_and_summary` fails with `TemplateDoesNotExist`, do Task 5 first, then re-run.

> **Ordering note:** `TestGet.test_renders_form_and_summary` and the POST re-render tests need `templates/booking/booking_form.html` (Task 5). Either create the template (Task 5 Step 1) before running Step 6, or expect those template-dependent tests to fail until Task 5 lands. The redirect/auth/404/no-booking assertions pass without the template.

---

## Task 5: Booking form template

**Files:**
- Create: `templates/booking/booking_form.html`

> Verified by `tests/booking/test_views.py` (Task 4). No separate test file — the view tests assert render + context.

- [ ] **Step 1: Create `templates/booking/booking_form.html`** (user pastes)

```django
{% extends "base.html" %}

{% block content %}
<article class="container py-4" style="max-width: 640px;">
  <a href="{{ screening.movie.get_absolute_url }}" class="text-decoration-none">← {{ screening.movie.title }}</a>
  <h1 class="mt-2 mb-4">Rezerwacja</h1>

  <div class="card mb-4">
    <div class="card-body">
      <h2 class="h5 card-title">{{ screening.movie.title }}</h2>
      <dl class="row mb-0">
        <dt class="col-5">Termin</dt><dd class="col-7">{{ screening.start_time|date:"d.m.Y H:i" }}</dd>
        <dt class="col-5">Sala</dt><dd class="col-7">{{ screening.hall.name }}</dd>
        <dt class="col-5">Cena za miejsce</dt><dd class="col-7">{{ screening.price }} zł</dd>
        <dt class="col-5">Dostępne miejsca</dt><dd class="col-7">{{ screening.available_seats_count }}</dd>
      </dl>
    </div>
  </div>

  <form method="post" novalidate>
    {% csrf_token %}
    {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors }}</div>{% endif %}
    <div class="mb-3">
      <label for="{{ form.seats_count.id_for_label }}" class="form-label">{{ form.seats_count.label }}</label>
      {{ form.seats_count }}
      {% if form.seats_count.errors %}<div class="text-danger small mt-1">{{ form.seats_count.errors }}</div>{% endif %}
    </div>
    <p class="fs-5">Razem: <strong id="booking-total">—</strong> zł</p>
    <button type="submit" class="btn btn-primary">Zarezerwuj i zapłać</button>
  </form>
</article>

<script>
  (function () {
    var price = parseFloat("{{ screening.price|stringformat:'f' }}");
    var input = document.getElementById("{{ form.seats_count.id_for_label }}");
    var out = document.getElementById("booking-total");
    function update() {
      var n = parseInt(input.value, 10);
      out.textContent = (n > 0) ? (price * n).toFixed(2) : "—";
    }
    input.addEventListener("input", update);
    update();
  })();
</script>
{% endblock %}
```

> **Note (dev pitfall #5 dodge):** `price|stringformat:'f'` renders a dot-decimal ("25.000000"), locale-independent — avoids the `pl_PL` comma that would break `parseFloat`. Keep each `{{ }}`/`{% %}` on one line (PyCharm hard-wrap / Django tag rules).

- [ ] **Step 2: Run → GREEN** (full view suite now passes)

Run: `poetry run pytest tests/booking/test_views.py -v`
Expected: PASS (9 tests).

- [ ] **Step 3: Commit (view + urls + template)**

```bash
git add apps/booking/views.py apps/booking/urls.py settings/urls.py \
        templates/booking/booking_form.html tests/booking/test_views.py
git commit -m "$(cat <<'EOF'
feat(FR-07): add BookingCreateView at /screenings/<id>/book/

LoginRequiredMixin View: GET renders the booking form + screening summary, POST
validates BookingForm then calls create_booking. Invalid form or BookingError
re-renders the page (200, errors shown); success flashes a message and redirects
to the stub checkout URL. Template shows the summary + a vanilla-JS live total.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Wire time-pill CTAs

**Files:**
- Modify: `templates/cinema/screening_list.html:46-48`
- Modify: `templates/cinema/movie_detail.html:135`

> Manual smoke verification (no new automated test — the redesign templates have no view-context assertions for pills; a render smoke is enough).

- [ ] **Step 1: Edit `templates/cinema/screening_list.html`** — replace the pill loop (lines 46-48) (user edits)

Old:

```django
                {% for s in hall_group.list %}
                <a href="#" class="time-pill {% if not s.is_available %}is-soldout{% endif %}">{{ s.start_time|date:"H:i" }}</a>
                {% endfor %}
```

New (keep `{% if %}` branches on single lines — Django tag rules):

```django
                {% for s in hall_group.list %}
                {% if s.is_available %}<a href="{% url 'booking:create' pk=s.pk %}" class="time-pill">{{ s.start_time|date:"H:i" }}</a>{% else %}<span class="time-pill is-soldout">{{ s.start_time|date:"H:i" }}</span>{% endif %}
                {% endfor %}
```

- [ ] **Step 2: Edit `templates/cinema/movie_detail.html`** — replace the pill loop (line 135) (user edits)

Old:

```django
                    {% for s in hall_group.list %}<a href="#" class="time-pill {% if not s.is_available %}is-soldout{% endif %}">{{ s.start_time|date:"H:i" }}</a>{% endfor %}
```

New (single line):

```django
                    {% for s in hall_group.list %}{% if s.is_available %}<a href="{% url 'booking:create' pk=s.pk %}" class="time-pill">{{ s.start_time|date:"H:i" }}</a>{% else %}<span class="time-pill is-soldout">{{ s.start_time|date:"H:i" }}</span>{% endif %}{% endfor %}
```

- [ ] **Step 3: Smoke + full suite**

```bash
poetry run pytest          # full suite still green (movie_detail / screening_list render tests)
```

Manual: `poetry run python manage.py runserver`, open `/screenings/` and a movie detail — available pills link to `/screenings/<id>/book/`, sold-out pills are non-clickable.

- [ ] **Step 4: Commit**

```bash
git add templates/cinema/screening_list.html templates/cinema/movie_detail.html
git commit -m "$(cat <<'EOF'
feat(FR-07): wire time-pill CTAs to booking create

Available screenings' time-pills now link to booking:create; sold-out/past pills
render as non-clickable spans. Anonymous users are bounced to login (?next=).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Quality gates

- [ ] **Step 1: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/booking apps/payments tests/booking tests/payments
poetry run ruff format --check apps/booking apps/payments tests/booking tests/payments
poetry run mypy apps/booking apps/payments
poetry run python manage.py makemigrations --check --dry-run   # expect: no changes
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; `makemigrations --check` exits 0 (no model changes); full suite green; coverage ≥80%.

> If mypy flags `create_booking`'s `user` param (untyped), annotate it `user: "settings.AUTH_USER_MODEL"` via `django.contrib.auth.models.AbstractBaseUser` import, or leave untyped if the project's mypy config doesn't require it (matches existing view signatures). Decide per the actual mypy output.

---

## Task 8: Backlog + PR

- [ ] **Step 1: Update `.Claude/backlog.md` status board**

- `Done` → append US-20; M3 count → 3/11
- `Ready (DoR ✅)` → US-21 (Booking detail view) — plan-directly per m3_planning (standard DetailView + 403)

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-20 done — booking create view shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-07-booking-create
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-20) / DoD checklist / Test plan / Out of scope (US-21 detail, US-24 real Stripe).

---

## Self-Review (wykonane)

**Spec coverage:**
- §3 service → Task 2 (`create_booking` + exceptions). §4 stub → Task 1. §5 view → Task 4. §6 URLs → Task 4 (urls + settings). §7 template → Task 5. §8 CTA wiring → Task 6. §9 tests → Tasks 1-4 (payments 1, service 6, threaded 1, view 9 = 17). §10 DoD → covered across tasks. §11 risk #1 (threaded) → Task 3 + dev pitfall #11 note. §10 manual smoke → Task 6 Step 3.
- §12 plan-phase items resolved: (1) loop var = `s` in both templates (verified); (2) JS = inline `<script>` in template; (3) threaded split = cap 5 / both request 3; (4) `force_login(UserFactory())` inline per test.

**Placeholder scan:** no TBD/TODO; every code step has full content; the mypy note in Task 7 is a conditional decision, not a placeholder.

**Type consistency:** `create_booking(*, user, screening, seats_count) -> (Booking, str)` consistent in Task 2 def, Task 4 view call, and tests. `create_checkout_session(booking) -> (str, str)` consistent in Task 1 def + Task 2 call. Exception names `BookingError`/`NotEnoughSeatsError(available=)`/`ScreeningInPastError` consistent across service, view, and tests. URL name `booking:create` consistent in urls.py, view tests, template wiring.
