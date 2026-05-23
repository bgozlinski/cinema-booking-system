# US-21 — Booking detail view Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Booking confirmation page (FR-08): `/bookings/<int:pk>/` shows a booking's details to its owner or staff (403 for other users, login redirect for anonymous).

**Architecture:** `BookingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView)` appended to `apps/booking/views.py`; owner-or-staff guard via `test_func`; `get_object` cached + `select_related` to keep it single-query. New `booking:detail` route + a `booking_detail.html` template with a status badge.

**Tech Stack:** Django 6 `DetailView` + auth mixins, pytest-django, factory_boy.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-23-us21-booking-detail.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (`tests/booking/test_detail_view.py`).
- Kod aplikacji (`apps/booking/views.py` append, `apps/booking/urls.py` edit, `templates/booking/booking_detail.html`) — **default: user wkleja** z planu. Jeśli user poprosi "popraw sam" — Claude edytuje.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

```bash
git checkout main && git pull
git checkout -b feat/FR-08-booking-detail
git branch --show-current   # → feat/FR-08-booking-detail
```

Spec + plan jako pierwszy commit na branchu:

```bash
git add docs/superpowers/specs/2026-05-23-us21-booking-detail.md \
        docs/superpowers/plans/2026-05-23-us21-booking-detail.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-21 booking detail view spec and plan

Planning artifacts for US-21 (FR-08) — BookingDetailView at /bookings/<id>/ with
owner-or-staff permission (403 for others, login redirect for anon). Standard
DetailView + LoginRequiredMixin + UserPassesTestMixin, cached get_object +
select_related. No migrations. ?stripe= flash deferred to US-24.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/views.py` | Modify | + `BookingDetailView` |
| `apps/booking/urls.py` | Modify | + `booking:detail` route |
| `templates/booking/booking_detail.html` | Create | detail render + status badge |
| `tests/booking/test_detail_view.py` | Create | access matrix + content + budget |
| `.Claude/backlog.md` | Modify | US-21 → Done (po merge) |

No migrations.

---

## Task 1: BookingDetailView + URL + template

**Files:**
- Test: `tests/booking/test_detail_view.py` (Create)
- Modify: `apps/booking/views.py`, `apps/booking/urls.py`
- Create: `templates/booking/booking_detail.html`

- [ ] **Step 1: Write the failing tests** (`tests/booking/test_detail_view.py`)

```python
"""Tests for BookingDetailView (US-21 / FR-08)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import MovieFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _detail_url(booking):
    return reverse("booking:detail", kwargs={"pk": booking.pk})


class TestBookingDetailAccess:
    def test_anonymous_redirected_to_login(self, client):
        booking = BookingFactory()
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert "next=" in resp.url

    def test_owner_gets_200(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 200
        assert resp.context["booking"] == booking

    def test_staff_non_owner_gets_200(self, client):
        booking = BookingFactory()
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 200

    def test_other_user_forbidden(self, client):
        booking = BookingFactory()
        other = UserFactory()
        client.force_login(other)
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 403

    def test_404_for_missing_booking(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse("booking:detail", kwargs={"pk": 999999}))
        assert resp.status_code == 404


class TestBookingDetailContent:
    def test_renders_booking_fields(self, client):
        screening = ScreeningFactory(movie=MovieFactory(title="Diuna"), price=Decimal("25.00"))
        booking = ConfirmedBookingFactory(screening=screening, seats_count=3)
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking))
        content = resp.content.decode()
        assert "Diuna" in content
        assert "75" in content  # total_price 3×25, locale-agnostic integer part
        assert "Potwierdzona" in content  # CONFIRMED display

    def test_template_used(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking))
        assert "booking/booking_detail.html" in [t.name for t in resp.templates]


class TestBookingDetailBudget:
    def test_query_budget(self, client, django_assert_max_num_queries):
        booking = BookingFactory()
        client.force_login(booking.user)
        with django_assert_max_num_queries(5):
            client.get(_detail_url(booking))
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_detail_view.py -v`
Expected: FAIL — `NoReverseMatch` for `booking:detail` (route/view missing).

- [ ] **Step 3: Append `BookingDetailView` to `apps/booking/views.py`** (user pastes)

Add these imports to the existing import block:

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView

from apps.booking.models import Booking
```

Append the view at the end of the file:

```python
class BookingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Booking
    template_name = "booking/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        return Booking.objects.select_related(
            "screening__movie", "screening__hall", "user"
        )

    def get_object(self, queryset=None):
        # Cache so test_func + DetailView.get don't fetch the booking twice.
        if not hasattr(self, "_booking"):
            self._booking = super().get_object(queryset)
        return self._booking

    def test_func(self) -> bool:
        booking = self.get_object()
        return self.request.user == booking.user or self.request.user.is_staff
```

> Note: `apps/booking/views.py` already imports `LoginRequiredMixin` (US-20). Keep one import line — add only `UserPassesTestMixin` to it. The existing `from django.contrib.auth.mixins import LoginRequiredMixin` becomes `from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin`.

- [ ] **Step 4: Add the route to `apps/booking/urls.py`** (user edits)

```python
from django.urls import path

from apps.booking.views import BookingCreateView, BookingDetailView

app_name = "booking"

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="detail"),
]
```

- [ ] **Step 5: Create `templates/booking/booking_detail.html`** (user pastes)

```django
{% extends "base.html" %}

{% block content %}
<article class="container py-4" style="max-width: 640px;">
  <h1 class="mb-4">Rezerwacja #{{ booking.id }}</h1>

  <div class="card">
    <div class="card-body">
      <h2 class="h5 card-title">{{ booking.screening.movie.title }}</h2>
      <dl class="row mb-0">
        <dt class="col-5">Termin</dt><dd class="col-7">{{ booking.screening.start_time|date:"d.m.Y H:i" }}</dd>
        <dt class="col-5">Sala</dt><dd class="col-7">{{ booking.screening.hall.name }}</dd>
        <dt class="col-5">Liczba miejsc</dt><dd class="col-7">{{ booking.seats_count }}</dd>
        <dt class="col-5">Łączna cena</dt><dd class="col-7">{{ booking.total_price }} zł</dd>
        <dt class="col-5">Status</dt>
        <dd class="col-7"><span class="badge {% if booking.status == 'PENDING' %}bg-warning text-dark{% elif booking.status == 'CONFIRMED' %}bg-success{% else %}bg-secondary{% endif %}">{{ booking.get_status_display }}</span></dd>
      </dl>
    </div>
  </div>

  <a href="{% url 'cinema:movie_list' %}" class="btn btn-outline-light mt-4">← Repertuar</a>
</article>
{% endblock %}
```

- [ ] **Step 6: Run → GREEN**

Run: `poetry run pytest tests/booking/test_detail_view.py -v`
Expected: PASS (8 tests).

- [ ] **Step 7: Commit**

```bash
git add apps/booking/views.py apps/booking/urls.py \
        templates/booking/booking_detail.html tests/booking/test_detail_view.py
git commit -m "$(cat <<'EOF'
feat(FR-08): add BookingDetailView at /bookings/<id>/

DetailView with LoginRequiredMixin + UserPassesTestMixin — owner or staff get
the booking confirmation (number, movie, datetime, hall, seats, total_price,
status badge); other authenticated users get 403, anonymous users are redirected
to login. get_object is cached and the queryset uses select_related to stay
single-query. ?stripe= flash deferred to US-24.

Closes US-21.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

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

> If mypy flags `test_func`/`get_object` return or `queryset` param types, match the signatures shown (they mirror Django's stubs). If django-stubs complains about `get_object(self, queryset=None)`, annotate `queryset: QuerySet[Booking] | None = None` — decide per the actual mypy output.

---

## Task 3: Backlog + PR

- [ ] **Step 1: Update `.Claude/backlog.md` status board**

- `Done` → append US-21; M3 count → 4/11
- `Ready (DoR ✅)` → US-22 (My bookings panel) — plan-directly per m3_planning (ListView + tab filter)

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-21 done — booking detail view shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-08-booking-detail
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-21) / DoD checklist / Test plan / Out of scope (US-22 list, US-23 cancel button, US-24 ?stripe flash).

---

## Self-Review (wykonane)

**Spec coverage:** §3 view → Task 1 Step 3. §4 URL → Task 1 Step 4. §5 template → Task 1 Step 5. §6 tests → Task 1 Step 1 (access 5 + content 2 + budget 1 = 8). §7 DoD → covered. §8 risk #1 (mixin order / 403-vs-302) → tested by `test_anonymous_redirected_to_login` (302) + `test_other_user_forbidden` (403). §8 risk #2 (double-fetch) → budget test. §8 risk #3 (locale total) → content test asserts "75" substring.

**Placeholder scan:** no TBD/TODO; every step has full code/command; the mypy note in Task 2 is a conditional decision.

**Type consistency:** view name `BookingDetailView`, URL name `booking:detail`, `context_object_name="booking"`, template `booking/booking_detail.html` — consistent across view, urls, template, and all tests. `UserFactory(is_staff=True)` matches the staff-access test. `booking.status` literals `'PENDING'`/`'CONFIRMED'` in the template match `BookingStatus` values.
