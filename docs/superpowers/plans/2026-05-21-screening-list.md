# Daily ScreeningList View Implementation Plan (US-14 — FR-04)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py`, `.html`, settings edits). **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Add `ScreeningListView(TemplateView)` at `/screenings/?date=YYYY-MM-DD` rendering a daily schedule grouped by movie. Out-of-range date silently clamps to `today..today+30` with a flash warning. Wires the navbar "Seanse" link (currently disabled). Closes US-14. Last user-facing M2 view — only US-17 (perf pass) remains in the milestone.

**Architecture:** A `TemplateView` (not `ListView`, because output is grouped — no pagination). View has a private `_resolve_date()` returning `(effective_date, was_clamped, raw_input)`; `get_context_data` flashes a warning via `django.contrib.messages` when clamped, then builds the day window via `timezone.make_aware(combine(date, time.min))` + 1 day (DST-safe). Screening queryset uses `select_related("movie", "hall")` + `prefetch_related("movie__genres")`, then groups in Python into an `OrderedDict` sorted by each movie's earliest screening that day. Template renders one Bootstrap card per movie with poster thumb + title link + embedded mini-table of screening rows. No new form class — date input is hand-rolled HTML5 `<input type="date" min max>` with server-side `_resolve_date` as the actual gate.

**Tech Stack:** Django 6 `TemplateView`, `django.contrib.messages` (already wired through `base.html:42-50`), `timezone.make_aware`/`localdate`, `datetime.date.fromisoformat`, `collections.OrderedDict`, pytest-django (`client`, `django_assert_max_num_queries`).

**Branch:** `feat/FR-04-screening-list` (per backlog US-14).

---

## Pre-flight checklist (read these first)

- [ ] `docs/superpowers/specs/2026-05-21-screening-list-design.md` — design decisions (Q1, Q2)
- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-04 — spec source of truth (lines ~224-229)
- [ ] `apps/cinema/views.py` — current `MovieListView`/`MovieDetailView` patterns
- [ ] `apps/cinema/urls.py` — URL config to extend
- [ ] `apps/cinema/models.py` — `Screening.start_time`, `Screening.movie` (FK with `related_name="screenings"`), `Screening.hall` (FK), `Screening.available_seats_count()` stub
- [ ] `templates/base.html` — navbar Seanse link (line 21) + messages block (lines 42-50)
- [ ] `tests/cinema/test_base_template.py` — existing Seanse-disabled assertion to swap
- [ ] `tests/cinema/factories.py` — `MovieFactory`, `HallFactory`, `ScreeningFactory`, `GenreFactory`
- [ ] `tests/cinema/test_movie_list.py` — N+1 pattern (`django_assert_max_num_queries`)

---

## File structure

```
apps/cinema/
├── views.py                                  ✎ + ScreeningListView (Task 2)
└── urls.py                                   ✎ + path("screenings/", ...) (Task 2)

templates/
├── cinema/screening_list.html                ★ NEW (Task 2 scaffold → Task 3 full markup)
└── base.html                                 ✎ navbar Seanse: drop disabled + add href (Task 4)

tests/cinema/
├── test_screening_list.py                    ★ NEW (Tasks 2 + 3 + 5, ~22 tests)
└── test_base_template.py                     ✎ swap Seanse-disabled → Seanse-active (Task 4)

.Claude/backlog.md                            ✎ status board (Task 1 + Task 5)
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress (Task 5)
```

No new deps. No new migrations. No new forms. No settings edits.

---

## Task 1: Branch + backlog DoR

**Files:**
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (user): branch off main**

```bash
git checkout main
git pull
git checkout -b feat/FR-04-screening-list
```

- [ ] **Step 2 (user): commit the spec** (untracked from brainstorming)

```bash
git add docs/superpowers/specs/2026-05-21-screening-list-design.md
git commit -m "docs(M2): add design spec for US-14 daily screening list"
```

- [ ] **Step 3 (Claude): move US-14 from Ready to In Progress in `.Claude/backlog.md` §7; queue US-17 next**

- [ ] **Step 4 (user): commit plan + backlog**

```bash
git add docs/superpowers/plans/2026-05-21-screening-list.md .Claude/backlog.md
git commit -m "docs(M2): add implementation plan for US-14 + mark in progress"
```

---

## Task 2: `ScreeningListView` + URL + view-level tests + scaffold template

**Files:**
- Create: `tests/cinema/test_screening_list.py`
- Modify: `apps/cinema/views.py`
- Modify: `apps/cinema/urls.py`
- Create: `templates/cinema/screening_list.html` (minimal scaffold)

**Why one big task:** The view, URL config, scaffold template, and all view-level tests (routing + date clamping + grouping + day-window boundary) form a single coherent unit. The view is ~30 lines and the template scaffold is trivial. Task 3 expands the template; Task 5 adds the N+1 budget.

- [ ] **Step 1 (Claude): create `tests/cinema/test_screening_list.py`**

```python
"""Tests for ScreeningListView (US-14 / FR-04)."""

import datetime as dt
from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from tests.cinema.factories import (
    HallFactory,
    MovieFactory,
    ScreeningFactory,
)


pytestmark = pytest.mark.django_db


def _make_local_dt(date, hour=18, minute=0, second=0):
    return timezone.make_aware(dt.datetime.combine(date, dt.time(hour, minute, second)))


class TestRouting:
    def test_url_returns_200_anon(self, client):
        response = client.get("/screenings/")
        assert response.status_code == 200

    def test_url_returns_200_authenticated(self, client, django_user_model):
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get("/screenings/")
        assert response.status_code == 200

    def test_url_name_reverses(self):
        assert reverse("cinema:screening_list") == "/screenings/"

    def test_uses_screening_list_template(self, client):
        response = client.get("/screenings/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/screening_list.html" in template_names


class TestResolveDate:
    def test_no_date_param_defaults_to_today(self, client):
        response = client.get("/screenings/")
        assert response.context["effective_date"] == timezone.localdate()
        assert len(list(get_messages(response.wsgi_request))) == 0

    def test_explicit_today_renders_today(self, client):
        today = timezone.localdate()
        response = client.get(f"/screenings/?date={today.isoformat()}")
        assert response.context["effective_date"] == today
        assert len(list(get_messages(response.wsgi_request))) == 0

    def test_future_within_30_days_passes_through(self, client):
        target = timezone.localdate() + timedelta(days=15)
        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert response.context["effective_date"] == target
        assert len(list(get_messages(response.wsgi_request))) == 0

    def test_past_date_clamps_to_today(self, client):
        past = timezone.localdate() - timedelta(days=5)
        response = client.get(f"/screenings/?date={past.isoformat()}")
        assert response.context["effective_date"] == timezone.localdate()
        msgs = list(get_messages(response.wsgi_request))
        assert len(msgs) == 1
        assert "poza zakresem" in str(msgs[0])

    def test_far_future_clamps_to_today_plus_30(self, client):
        far = timezone.localdate() + timedelta(days=90)
        response = client.get(f"/screenings/?date={far.isoformat()}")
        assert response.context["effective_date"] == timezone.localdate() + timedelta(days=30)
        msgs = list(get_messages(response.wsgi_request))
        assert len(msgs) == 1
        assert "poza zakresem" in str(msgs[0])

    def test_malformed_date_clamps_to_today(self, client):
        response = client.get("/screenings/?date=not-a-date")
        assert response.context["effective_date"] == timezone.localdate()
        msgs = list(get_messages(response.wsgi_request))
        assert len(msgs) == 1

    def test_empty_date_string_defaults_to_today_no_warning(self, client):
        response = client.get("/screenings/?date=")
        assert response.context["effective_date"] == timezone.localdate()
        assert len(list(get_messages(response.wsgi_request))) == 0


class TestGroupingAndOrdering:
    def test_screenings_grouped_by_movie(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie_a = MovieFactory(title="A")
        movie_b = MovieFactory(title="B")
        ScreeningFactory(movie=movie_a, start_time=_make_local_dt(tomorrow, 14))
        ScreeningFactory(movie=movie_a, start_time=_make_local_dt(tomorrow, 18))
        ScreeningFactory(movie=movie_b, start_time=_make_local_dt(tomorrow, 16))
        ScreeningFactory(movie=movie_b, start_time=_make_local_dt(tomorrow, 20))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        groups = response.context["movie_groups"]

        assert len(groups) == 2
        movies_in_groups = {g[0] for g in groups}
        assert movies_in_groups == {movie_a, movie_b}
        for _, screenings in groups:
            assert len(screenings) == 2

    def test_movies_ordered_by_earliest_screening(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie_late = MovieFactory(title="Late")
        movie_early = MovieFactory(title="Early")
        ScreeningFactory(movie=movie_late, start_time=_make_local_dt(tomorrow, 21))
        ScreeningFactory(movie=movie_early, start_time=_make_local_dt(tomorrow, 14))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        groups = response.context["movie_groups"]

        assert groups[0][0] == movie_early
        assert groups[1][0] == movie_late

    def test_screenings_within_group_sorted_by_start_time(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 21))
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 14))
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 18))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        screenings = response.context["movie_groups"][0][1]

        hours = [s.start_time.astimezone(timezone.get_current_timezone()).hour for s in screenings]
        assert hours == [14, 18, 21]

    def test_past_screenings_for_today_still_included(self, client):
        # A screening at 06:00 local today — even if it's past now, the day filter still includes it.
        today = timezone.localdate()
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(today, 6))

        response = client.get(f"/screenings/?date={today.isoformat()}")
        groups = response.context["movie_groups"]

        assert any(g[0] == movie for g in groups)


class TestDayWindowBoundary:
    def test_boundary_inclusive_at_midnight(self, client):
        target = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(target, 0, 0, 0))

        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert any(g[0] == movie for g in response.context["movie_groups"])

    def test_boundary_inclusive_at_end_of_day(self, client):
        target = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(target, 23, 59, 59))

        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert any(g[0] == movie for g in response.context["movie_groups"])

    def test_boundary_excludes_next_day_midnight(self, client):
        target = timezone.localdate() + timedelta(days=1)
        next_day = target + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(next_day, 0, 0, 0))

        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert not any(g[0] == movie for g in response.context["movie_groups"])
```

- [ ] **Step 2 (user): run — expect ~18 FAIL** (no `/screenings/` URL yet, no `ScreeningListView`)

```bash
poetry run pytest tests/cinema/test_screening_list.py -v
```

- [ ] **Step 3 (user): add `ScreeningListView` to `apps/cinema/views.py`** (append below existing classes; **keep `MovieListView` and `MovieDetailView` untouched**). Reference impl:

```python
import datetime
from collections import OrderedDict
from datetime import time, timedelta

from django.contrib import messages
from django.db.models import Min, Q
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from apps.cinema.forms import MovieFilterForm
from apps.cinema.models import Movie, Screening
from apps.cinema.utils import youtube_embed_url


# ... existing MovieListView and MovieDetailView stay above ...


class ScreeningListView(TemplateView):
    template_name = "cinema/screening_list.html"

    def _resolve_date(self):
        """Parse ?date= and clamp to today..today+30. Returns (effective_date, was_clamped, raw_input)."""
        today = timezone.localdate()
        max_date = today + timedelta(days=30)
        raw = self.request.GET.get("date", "")
        if not raw:
            return today, False, ""
        try:
            requested = datetime.date.fromisoformat(raw)
        except ValueError:
            return today, True, raw
        if requested < today:
            return today, True, raw
        if requested > max_date:
            return max_date, True, raw
        return requested, False, raw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        effective, clamped, _raw = self._resolve_date()
        if clamped:
            messages.warning(
                self.request,
                f"Data poza zakresem; pokazano dla {effective.isoformat()}.",
            )
        day_start = timezone.make_aware(
            datetime.datetime.combine(effective, time.min)
        )
        day_end = day_start + timedelta(days=1)

        screenings = (
            Screening.objects
            .filter(start_time__gte=day_start, start_time__lt=day_end)
            .select_related("movie", "hall")
            .prefetch_related("movie__genres")
            .order_by("movie__title", "start_time")
        )

        grouped: "OrderedDict" = OrderedDict()
        for s in screenings:
            grouped.setdefault(s.movie, []).append(s)
        movie_groups = sorted(grouped.items(), key=lambda item: item[1][0].start_time)

        ctx["effective_date"] = effective
        ctx["today"] = timezone.localdate()
        ctx["max_date"] = timezone.localdate() + timedelta(days=30)
        ctx["movie_groups"] = movie_groups
        return ctx
```

- [ ] **Step 4 (user): update `apps/cinema/urls.py`**:

```python
from apps.cinema.views import MovieDetailView, MovieListView, ScreeningListView

urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
    path("movies/<int:pk>/", MovieDetailView.as_view(), name="movie_detail"),
    path("screenings/", ScreeningListView.as_view(), name="screening_list"),
]
```

- [ ] **Step 5 (user): create `templates/cinema/screening_list.html`** (minimal scaffold — Task 3 expands):

```html
{% extends "base.html" %}

{% block title %}Seanse — KinoMania{% endblock %}

{% block content %}
<h1 class="h2 mb-4">Seanse</h1>
{% endblock %}
```

- [ ] **Step 6 (user): rerun — expect 18 PASS**

```bash
poetry run pytest tests/cinema/test_screening_list.py -v
```

- [ ] **Step 7 (user): commit**

```bash
git add tests/cinema/test_screening_list.py apps/cinema/views.py apps/cinema/urls.py templates/cinema/screening_list.html
git commit -m "feat(FR-04): ScreeningListView with date clamping + grouped queryset"
```

---

## Task 3: Template — date form + movie cards + empty state

**Files:**
- Modify: `tests/cinema/test_screening_list.py`
- Modify: `templates/cinema/screening_list.html`

- [ ] **Step 1 (Claude): append `TestRendering` to `tests/cinema/test_screening_list.py`**

Add to top-of-file imports (after existing):

```python
from decimal import Decimal

from tests.cinema.factories import GenreFactory
```

Append at end of file:

```python
class TestRendering:
    def test_movie_title_links_to_detail_page(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory(title="Linked Movie")
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 18))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert "Linked Movie" in content
        assert f'href="/movies/{movie.pk}/"' in content

    def test_screening_row_shows_hour_hall_price_seats(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        hall = HallFactory(name="Sala A", capacity=100)
        movie = MovieFactory()
        ScreeningFactory(
            movie=movie, hall=hall,
            start_time=_make_local_dt(tomorrow, 18),
            price=Decimal("42.50"),
        )

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert "18:00" in content
        assert "Sala A" in content
        # Polish locale renders Decimal with comma; accept either form.
        assert ("42,50" in content) or ("42.50" in content)
        assert "zł" in content
        # available_seats_count stub returns hall.capacity (100) until US-18.
        assert "100" in content
        assert "Zarezerwuj" in content
        assert "disabled" in content

    def test_genre_badges_render_on_card_header(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        movie.genres.add(GenreFactory(name="Drama"), GenreFactory(name="Sci-Fi"))
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 18))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert "Drama" in content
        assert "Sci-Fi" in content
        assert content.count('class="badge bg-secondary"') >= 2

    def test_empty_state_when_no_screenings_for_day(self, client):
        # No screenings anywhere → empty state for today.
        response = client.get("/screenings/")
        content = response.content.decode()

        assert "Brak seansów na dzień" in content
        assert "<table" not in content

    def test_dzisiaj_link_visible_when_date_param_present(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert ">Dzisiaj<" in content
        assert 'href="/screenings/"' in content

    def test_dzisiaj_link_hidden_without_date_param(self, client):
        response = client.get("/screenings/")
        content = response.content.decode()

        assert ">Dzisiaj<" not in content

    def test_clamp_warning_shows_in_messages_block(self, client):
        past = (timezone.localdate() - timedelta(days=5)).isoformat()
        response = client.get(f"/screenings/?date={past}", follow=True)
        # Messages render inline in base.html via {% if messages %}.
        content = response.content.decode()
        assert "Data poza zakresem" in content

    def test_date_input_min_max_set_for_browser_picker(self, client):
        response = client.get("/screenings/")
        content = response.content.decode()
        today_iso = timezone.localdate().isoformat()
        max_iso = (timezone.localdate() + timedelta(days=30)).isoformat()
        assert f'min="{today_iso}"' in content
        assert f'max="{max_iso}"' in content
```

- [ ] **Step 2 (user): run — expect 8 FAIL** (template is minimal scaffold)

```bash
poetry run pytest tests/cinema/test_screening_list.py::TestRendering -v
```

- [ ] **Step 3 (user): rewrite `templates/cinema/screening_list.html`** (reference impl):

```html
{% extends "base.html" %}

{% block title %}Seanse — {{ effective_date|date:"d.m.Y" }} — KinoMania{% endblock %}

{% block content %}
<h1 class="h2 mb-4">Seanse</h1>

<form method="get" class="row g-2 mb-4 align-items-end" role="search">
  <div class="col-auto">
    <label for="date-input" class="form-label small mb-1">Data</label>
    <input type="date" id="date-input" name="date" class="form-control"
           min="{{ today|date:'Y-m-d' }}"
           max="{{ max_date|date:'Y-m-d' }}"
           value="{{ effective_date|date:'Y-m-d' }}">
  </div>
  <div class="col-auto">
    <button type="submit" class="btn btn-primary">Pokaż</button>
  </div>
  {% if request.GET.date %}
    <div class="col-auto">
      <a href="{% url 'cinema:screening_list' %}" class="btn btn-outline-secondary"
         title="Wróć do dzisiejszego dnia">Dzisiaj</a>
    </div>
  {% endif %}
</form>

{% if movie_groups %}
  {% for movie, screenings in movie_groups %}
    <div class="card mb-4">
      <div class="card-body">
        <div class="row g-3 align-items-center mb-3">
          <div class="col-auto">
            {% if movie.poster %}
              <img src="{{ movie.poster.url }}" alt="{{ movie.title }}"
                   class="rounded"
                   style="width:80px; height:120px; object-fit:cover;">
            {% else %}
              <div class="bg-light rounded d-flex align-items-center justify-content-center"
                   style="width:80px; height:120px; font-size:2rem;" aria-hidden="true">🎬</div>
            {% endif %}
          </div>
          <div class="col">
            <h2 class="h5 mb-1">
              <a href="{{ movie.get_absolute_url }}" class="text-decoration-none">
                {{ movie.title }}
              </a>
            </h2>
            <p class="mb-0">
              {% for genre in movie.genres.all %}
                <span class="badge bg-secondary">{{ genre.name }}</span>
              {% endfor %}
            </p>
          </div>
        </div>

        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead>
              <tr>
                <th>Godzina</th>
                <th>Sala</th>
                <th>Cena</th>
                <th>Dostępne miejsca</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {% for s in screenings %}
                <tr>
                  <td>{{ s.start_time|date:"H:i" }}</td>
                  <td>{{ s.hall.name }}</td>
                  <td>{{ s.price }} zł</td>
                  <td>{{ s.available_seats_count }}</td>
                  <td>
                    <a href="#" class="btn btn-primary btn-sm disabled">Zarezerwuj</a>
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  {% endfor %}
{% else %}
  <div class="alert alert-info">
    Brak seansów na dzień {{ effective_date|date:"d.m.Y" }}.
  </div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4 (user): rerun — expect 8 PASS** (plus 18 from Task 2 still green)

```bash
poetry run pytest tests/cinema/test_screening_list.py -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_screening_list.py templates/cinema/screening_list.html
git commit -m "feat(FR-04): screening_list.html template with date form + movie cards"
```

---

## Task 4: Wire Seanse navbar link

**Files:**
- Modify: `tests/cinema/test_base_template.py`
- Modify: `templates/base.html`

- [ ] **Step 1 (Claude): swap the existing "Seanse disabled" test**

Open `tests/cinema/test_base_template.py`. Find the test that asserts the Seanse anchor has `disabled` class / `href="#"`. Replace it with:

```python
def test_navbar_seanse_links_to_screening_list(client):
    response = client.get("/")
    content = response.content.decode()
    import re
    match = re.search(r"<a[^>]*>\s*Seanse\s*</a>", content)
    assert match is not None, "Seanse nav anchor not found"
    anchor = match.group(0)
    assert 'href="/screenings/"' in anchor, f"Seanse should link to /screenings/, got: {anchor}"
    assert "disabled" not in anchor, f"Seanse should not be disabled, got: {anchor}"
```

If the existing test name was different (e.g., `test_navbar_seanse_link_disabled`), delete that test entirely and add the new one.

- [ ] **Step 2 (user): run — expect 1 FAIL** (anchor still has `disabled`)

```bash
poetry run pytest tests/cinema/test_base_template.py -v -k "seanse"
```

- [ ] **Step 3 (user): update `templates/base.html` line 21** — change:

```html
<li class="nav-item"><a class="nav-link disabled" href="#">Seanse</a></li>
```

to:

```html
<li class="nav-item"><a class="nav-link" href="{% url 'cinema:screening_list' %}">Seanse</a></li>
```

- [ ] **Step 4 (user): rerun + full base-template suite:**

```bash
poetry run pytest tests/cinema/test_base_template.py -v
```

Expected: all green (the rewritten test + Repertuar/login/logout assertions unchanged).

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_base_template.py templates/base.html
git commit -m "feat(FR-04): wire Seanse navbar link to screening list"
```

---

## Task 5: N+1 budget + coverage + smoke + PR

**Files:**
- Modify: `tests/cinema/test_screening_list.py`
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (Claude): append `TestQueryBudget`**

```python
class TestQueryBudget:
    def test_full_day_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """5 movies × 3 screenings each = 15 rows. select_related("movie", "hall")
        joins on the screenings query; prefetch_related("movie__genres") loads genres
        in a single batched query. Budget cap 3 absorbs harness overhead."""
        tomorrow = timezone.localdate() + timedelta(days=1)
        for i in range(5):
            movie = MovieFactory()
            movie.genres.add(GenreFactory(), GenreFactory())
            for hour in (12, 16, 20):
                ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, hour))

        with django_assert_max_num_queries(3):
            client.get(f"/screenings/?date={tomorrow.isoformat()}")
```

- [ ] **Step 2 (user): run — likely PASS** (queryset already has select_related + prefetch from Task 2)

```bash
poetry run pytest tests/cinema/test_screening_list.py::TestQueryBudget -v
```

If FAIL with count > 3, inspect printed queries. Common culprit: template iterating `movie.genres.all` without the prefetch in place, or an unprefetched `s.hall.something` access. Bump cap to 4 only if confident the extra query is harness-injected.

- [ ] **Step 3 (user): full suite + coverage**

```bash
poetry run pytest --cov=apps --cov-report=term-missing
```

Expected: all tests pass; `apps/cinema/views.py` 100%; project ≥80%.

- [ ] **Step 4 (user): manual smoke**

```bash
poetry run python manage.py seed_db --flush
poetry run python manage.py runserver
```

Visit `http://127.0.0.1:8000/screenings/`:
- Default (no `?date=`) → today's screenings (if any). Seed places screenings randomly in `-7..+30` days range, so today often has some.
- Date input lets you pick today..today+30 (browser greys out invalid dates).
- Pick a date with no screenings → "Brak seansów na dzień" alert.
- Try `?date=2030-01-01` in URL bar → page redirects display to clamped value with a yellow "Data poza zakresem" toast.
- Click a movie title → lands on `/movies/<pk>/` detail page.
- Navbar "Seanse" link now active (not greyed out) → same page.

- [ ] **Step 5 (Claude): update `.Claude/backlog.md` §7** — US-14 → Done; queue **US-17** (performance pass, NFR) next as the final M2 task.

- [ ] **Step 6 (user): commit backlog**

```bash
git add .Claude/backlog.md
git commit -m "docs(M2): mark US-14 done, queue US-17 next"
```

- [ ] **Step 7 (user): commit budget test (if not already with Task 3)**

```bash
git add tests/cinema/test_screening_list.py
git commit -m "test(FR-04): N+1 query budget regression for screening list"
```

(Or squash with the backlog commit.)

- [ ] **Step 8 (user): push + open PR**

```bash
git push -u origin feat/FR-04-screening-list
```

PR body:

```
Title: feat(FR-04): daily screening list — US-14

## Summary
- New `ScreeningListView(TemplateView)` at `/screenings/?date=YYYY-MM-DD` (`cinema:screening_list`)
- `_resolve_date()` clamps out-of-range dates to today..today+30 with a `messages.warning` toast
- Screenings grouped by movie; movie groups ordered by earliest screening that day
- Bootstrap card per movie: poster thumb + title link (to detail) + genre badges + mini-table of screening times/hall/price/seats/"Zarezerwuj" disabled
- Wires the previously-disabled "Seanse" navbar link
- Day-window math identical to US-12 (DST-safe `make_aware(combine(date, time.min))`)
- ~26 new tests; N+1 cap at 3 (select_related + prefetch_related on movie__genres)

## Closes
- US-14 (FR-04)

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-05-21-screening-list-design.md`
- Plan: `docs/superpowers/plans/2026-05-21-screening-list.md`
- FR spec: `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-04

## Out of scope (deferred)
- Booking flow ("Zarezerwuj") → US-20 (M3, FR-07) drops `disabled` + wires href
- Real `Screening.available_seats_count` (Booking aggregation) → US-18 (M3)
- Performance pass (other views) → US-17 (NFR) — final M2 task

## Test plan
- [ ] CI green (lint, mypy, tests, ≥80% coverage)
- [ ] Manual smoke: default today, picked future date, picked date with no screenings, out-of-range `?date=` clamps + flashes warning, "Dzisiaj" reset link
- [ ] Navbar "Seanse" link active and lands on schedule page
```

- [ ] **Step 9 (after merge — separate session): update `memory/project_kinomania_bootstrap.md`** — M2 progress: 7/8 done; last task is **US-17 (performance pass)**.

---

## Self-review summary

- ✅ FR-04 acceptance criteria: URL `/screenings/?date=...` (Task 2), default today + 30-day picker (Task 2 `_resolve_date` + Task 3 input min/max), screenings grouped by movie (Task 2), each screening shows title-link + hour + hall + price + seats + button (Task 3).
- ✅ Spec §1 brainstorming decisions Q1 (clamp + flash) and Q2 (card-per-movie layout) implemented in Tasks 2 and 3.
- ✅ Spec §2 architecture (view + URL + navbar) covered Tasks 2, 4.
- ✅ Spec §3 template covered Task 3.
- ✅ Spec §4 test surface (all 7 categories) distributed across Tasks 2, 3, 4, 5.
- ✅ Spec §5 file changes: every file accounted for.
- ✅ Spec §6 commit plan: matches task structure (4 feature + 2 docs).
- ✅ Navbar "Seanse" wiring + test swap explicit in Task 4.
- ✅ N+1 regression test (Task 5) caps query budget at 3.
- ✅ Empty `?date=` vs no `?date=` both treated as "today, no warning" (explicit test).
- ✅ Past-screening-on-today still included (explicit test).
- ✅ Polish-locale Decimal rendering tolerated in the price assertion.
- ✅ No placeholders; every step has runnable code/commands.
