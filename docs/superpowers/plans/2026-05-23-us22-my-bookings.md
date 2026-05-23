# US-22 — My bookings panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Logged-in user's bookings panel (FR-09): `/my-bookings/` lists the user's bookings in two server-rendered tabs — Nadchodzące (`start_time >= now`) and Historia — switched via `?tab=upcoming|history`, newest first.

**Architecture:** `MyBookingsView(LoginRequiredMixin, ListView)` appended to `apps/booking/views.py`; queryset filters by `user` + tab and `select_related`s screening/movie/hall. New `booking:my_bookings` route, a `my_bookings.html` template (tab pills + cards + disabled "Anuluj" placeholder for US-23), and an auth-gated navbar link.

**Tech Stack:** Django 6 `ListView` + `LoginRequiredMixin`, pytest-django, factory_boy.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-23-us22-my-bookings.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (`tests/booking/test_my_bookings.py`).
- Kod aplikacji (`apps/booking/views.py` append, `apps/booking/urls.py` edit, `templates/booking/my_bookings.html`, `templates/base.html` edit) — **default: user wkleja** z planu. Jeśli user poprosi "popraw sam" — Claude edytuje.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

```bash
git checkout main && git pull
git checkout -b feat/FR-09-my-bookings
git branch --show-current   # → feat/FR-09-my-bookings
```

Spec + plan jako pierwszy commit na branchu:

```bash
git add docs/superpowers/specs/2026-05-23-us22-my-bookings.md \
        docs/superpowers/plans/2026-05-23-us22-my-bookings.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-22 my-bookings panel spec and plan

Planning artifacts for US-22 (FR-09) — MyBookingsView at /my-bookings/ listing the
user's bookings in two tabs (Nadchodzące/Historia) via ?tab=, newest first.
ListView + LoginRequiredMixin + select_related. Auth-gated navbar link. "Anuluj"
is a disabled placeholder (cancel logic = US-23). No migrations.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/views.py` | Modify | + `MyBookingsView` |
| `apps/booking/urls.py` | Modify | + `booking:my_bookings` route |
| `templates/booking/my_bookings.html` | Create | tab pills + cards + empty state |
| `templates/base.html` | Modify | + auth-gated "Moje rezerwacje" nav item |
| `tests/booking/test_my_bookings.py` | Create | access/scoping/tabs/ordering/content/budget |
| `.Claude/backlog.md` | Modify | US-22 → Done (po merge) |

No migrations.

---

## Task 1: MyBookingsView + URL + template

**Files:**
- Test: `tests/booking/test_my_bookings.py` (Create)
- Modify: `apps/booking/views.py`, `apps/booking/urls.py`
- Create: `templates/booking/my_bookings.html`

- [ ] **Step 1: Write the failing tests** (`tests/booking/test_my_bookings.py`)

```python
"""Tests for MyBookingsView (US-22 / FR-09)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory
from tests.cinema.factories import ScreeningFactory

pytestmark = pytest.mark.django_db


def _url():
    return reverse("booking:my_bookings")


def _past_screening():
    return ScreeningFactory(start_time=timezone.now() - timedelta(days=1))


class TestMyBookingsAccess:
    def test_anonymous_redirected_to_login(self, client):
        resp = client.get(_url())
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert "next=" in resp.url


class TestMyBookingsScoping:
    def test_shows_only_own_bookings(self, client):
        me = UserFactory()
        BookingFactory(user=me)  # future (factory default +7d)
        BookingFactory()  # another user
        client.force_login(me)
        resp = client.get(_url())
        bookings = list(resp.context["bookings"])
        assert len(bookings) == 1
        assert bookings[0].user == me


class TestMyBookingsTabs:
    def test_upcoming_is_default(self, client):
        me = UserFactory()
        future = BookingFactory(user=me)
        BookingFactory(user=me, screening=_past_screening())
        client.force_login(me)
        resp = client.get(_url())
        assert resp.context["active_tab"] == "upcoming"
        ids = {b.id for b in resp.context["bookings"]}
        assert ids == {future.id}

    def test_history_tab_shows_past(self, client):
        me = UserFactory()
        BookingFactory(user=me)  # future
        past = BookingFactory(user=me, screening=_past_screening())
        client.force_login(me)
        resp = client.get(_url(), {"tab": "history"})
        assert resp.context["active_tab"] == "history"
        ids = {b.id for b in resp.context["bookings"]}
        assert ids == {past.id}

    def test_unknown_tab_falls_back_to_upcoming(self, client):
        client.force_login(UserFactory())
        resp = client.get(_url(), {"tab": "garbage"})
        assert resp.context["active_tab"] == "upcoming"


class TestMyBookingsOrdering:
    def test_newest_first(self, client):
        me = UserFactory()
        first = BookingFactory(user=me)
        second = BookingFactory(user=me)
        client.force_login(me)
        resp = client.get(_url())
        bookings = list(resp.context["bookings"])
        assert bookings[0] == second  # later created_at first
        assert bookings[1] == first


class TestMyBookingsContent:
    def test_empty_state(self, client):
        client.force_login(UserFactory())
        resp = client.get(_url())
        assert resp.status_code == 200
        assert list(resp.context["bookings"]) == []

    def test_links_to_detail(self, client):
        me = UserFactory()
        booking = BookingFactory(user=me)
        client.force_login(me)
        resp = client.get(_url())
        assert reverse("booking:detail", kwargs={"pk": booking.pk}) in resp.content.decode()

    def test_template_used(self, client):
        client.force_login(UserFactory())
        resp = client.get(_url())
        assert "booking/my_bookings.html" in [t.name for t in resp.templates]

    def test_cancel_button_disabled_placeholder(self, client):
        me = UserFactory()
        BookingFactory(user=me)  # PENDING, future → cancellable-looking
        client.force_login(me)
        content = client.get(_url()).content.decode()
        assert "Anuluj" in content
        assert "disabled" in content


class TestMyBookingsBudget:
    def test_query_budget(self, client, django_assert_max_num_queries):
        me = UserFactory()
        for _ in range(3):
            BookingFactory(user=me)
        client.force_login(me)
        with django_assert_max_num_queries(6):
            client.get(_url())
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/booking/test_my_bookings.py -v`
Expected: FAIL — `NoReverseMatch` for `booking:my_bookings`.

- [ ] **Step 3: Append `MyBookingsView` to `apps/booking/views.py`** (user pastes)

Ensure these imports exist (US-21 already added `DetailView`; add `ListView` + `timezone`):

```python
from django.utils import timezone
from django.views.generic import DetailView, ListView
```

Append the view at the end of the file:

```python
class MyBookingsView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = "booking/my_bookings.html"
    context_object_name = "bookings"

    def _active_tab(self) -> str:
        return "history" if self.request.GET.get("tab") == "history" else "upcoming"

    def get_queryset(self):
        qs = Booking.objects.filter(user=self.request.user).select_related(
            "screening__movie", "screening__hall"
        )
        now = timezone.now()
        if self._active_tab() == "history":
            qs = qs.filter(screening__start_time__lt=now)
        else:
            qs = qs.filter(screening__start_time__gte=now)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_tab"] = self._active_tab()
        return ctx
```

- [ ] **Step 4: Add the route to `apps/booking/urls.py`** (user edits)

```python
from django.urls import path

from apps.booking.views import BookingCreateView, BookingDetailView, MyBookingsView

app_name = "booking"

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="detail"),
    path("my-bookings/", MyBookingsView.as_view(), name="my_bookings"),
]
```

- [ ] **Step 5: Create `templates/booking/my_bookings.html`** (user pastes)

```django
{% extends "base.html" %}

{% block content %}
<article class="container py-4">
  <h1 class="mb-4">Moje rezerwacje</h1>

  <ul class="nav nav-pills mb-4">
    <li class="nav-item">
      <a class="nav-link {% if active_tab == 'upcoming' %}active{% endif %}" href="?tab=upcoming">Nadchodzące</a>
    </li>
    <li class="nav-item">
      <a class="nav-link {% if active_tab == 'history' %}active{% endif %}" href="?tab=history">Historia</a>
    </li>
  </ul>

  {% if bookings %}
  <div class="row row-cols-1 g-3">
    {% for booking in bookings %}
    <div class="col">
      <div class="card">
        <div class="card-body d-flex justify-content-between align-items-center flex-wrap gap-2">
          <div>
            <a href="{% url 'booking:detail' pk=booking.pk %}" class="h6 text-decoration-none">{{ booking.screening.movie.title }}</a>
            <div class="text-muted small">{{ booking.screening.start_time|date:"d.m.Y H:i" }} · Sala {{ booking.screening.hall.name }} · {{ booking.seats_count }} miejsc · {{ booking.total_price }} zł</div>
          </div>
          <div class="d-flex align-items-center gap-2">
            <span class="badge {% if booking.status == 'PENDING' %}bg-warning text-dark{% elif booking.status == 'CONFIRMED' %}bg-success{% else %}bg-secondary{% endif %}">{{ booking.get_status_display }}</span>
            {% if active_tab == 'upcoming' and booking.status != 'CANCELLED' %}<button class="btn btn-sm btn-outline-danger" disabled title="Dostępne wkrótce">Anuluj</button>{% endif %}
          </div>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="alert alert-info">{% if active_tab == 'history' %}Brak historycznych rezerwacji.{% else %}Nie masz nadchodzących rezerwacji. <a href="{% url 'cinema:movie_list' %}">Przeglądaj repertuar</a>.{% endif %}</div>
  {% endif %}
</article>
{% endblock %}
```

- [ ] **Step 6: Run → GREEN**

Run: `poetry run pytest tests/booking/test_my_bookings.py -v`
Expected: PASS (10 tests).

- [ ] **Step 7: Commit**

```bash
git add apps/booking/views.py apps/booking/urls.py \
        templates/booking/my_bookings.html tests/booking/test_my_bookings.py
git commit -m "$(cat <<'EOF'
feat(FR-09): add MyBookingsView at /my-bookings/

ListView (LoginRequiredMixin) of the user's own bookings, split into Nadchodzące
(start_time >= now) and Historia tabs via ?tab=, newest first, select_related to
stay single-query. Each card links to the booking detail; "Anuluj" is a disabled
placeholder until US-23 wires the cancel action. Empty state per tab.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire navbar link

**Files:**
- Modify: `templates/base.html` (inside the `me-auto` ul, after the "Seanse" li)

- [ ] **Step 1: Add the auth-gated nav item** (user edits)

Insert before the closing `</ul>` of the left nav (the `{% with un=... %}` block, ~line 49):

```django
                {% if user.is_authenticated %}
                <li class="nav-item">
                    {% if un == 'my_bookings' %}
                    <a class="nav-link active" href="{% url 'booking:my_bookings' %}">Moje rezerwacje</a>
                    {% else %}
                    <a class="nav-link" href="{% url 'booking:my_bookings' %}">Moje rezerwacje</a>
                    {% endif %}
                </li>
                {% endif %}
```

- [ ] **Step 2: Smoke + full suite**

```bash
poetry run pytest          # full suite green (base.html renders across pages)
```

Manual: `runserver`, log in → navbar shows "Moje rezerwacje" → links to `/my-bookings/`; log out → link gone.

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "$(cat <<'EOF'
feat(FR-09): add "Moje rezerwacje" navbar link for logged-in users

Auth-gated nav item linking to booking:my_bookings, active on the my-bookings
page. Hidden for anonymous visitors.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Quality gates

- [ ] **Step 1: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/booking tests/booking
poetry run ruff format --check apps/booking tests/booking
poetry run mypy apps/booking
poetry run python manage.py makemigrations --check --dry-run   # expect: no changes
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; `makemigrations --check` exits 0; full suite green; coverage ≥80%.

> If mypy flags `get_queryset`/`get_context_data` return types, match the signatures shown (they mirror Django's stubs and the existing `MovieListView`/`BookingDetailView` patterns). Decide per the actual mypy output.

---

## Task 4: Backlog + PR

- [ ] **Step 1: Update `.Claude/backlog.md` status board**

- `Done` → append US-22; M3 count → 5/11
- `Ready (DoR ✅)` → US-23 (Cancel booking, PENDING-only) — plan-directly per m3_planning (POST endpoint + status update; refund deferred to US-27)

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-22 done — my-bookings panel shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-09-my-bookings
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-22) / DoD checklist / Test plan / Out of scope (US-23 cancel action, US-24 ?stripe flash).

---

## Self-Review (wykonane)

**Spec coverage:** §3 view → Task 1 Step 3. §4 URL → Task 1 Step 4. §5 template → Task 1 Step 5. §6 navbar → Task 2. §7 tests → Task 1 Step 1 (access 1 + scoping 1 + tabs 3 + ordering 1 + content 4 + budget 1 = 11; covers the ~10 in the spec). §8 DoD → covered. §9 risk #1 (module-level reverse) → tests use `_url()` helper. §9 risk #2 (ordering) → `test_newest_first`. §9 risk #3 (Anuluj placeholder) → `test_cancel_button_disabled_placeholder`.

**Placeholder scan:** no TBD/TODO; every step has full code/command; the mypy note in Task 3 is a conditional decision.

**Type consistency:** view `MyBookingsView`, URL `booking:my_bookings`, `context_object_name="bookings"`, `active_tab` context key, template `booking/my_bookings.html` — consistent across view, urls, template, navbar (`un == 'my_bookings'`), and all tests. `?tab=history`/`upcoming` literals match `_active_tab()`. `booking.status` literals `'PENDING'`/`'CONFIRMED'`/`'CANCELLED'` match `BookingStatus`.
