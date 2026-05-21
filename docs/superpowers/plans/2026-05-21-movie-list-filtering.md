# MovieList Filtering Implementation Plan (US-12 — FR-02)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py`, `.html`, settings edits). **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Extend `MovieListView` from US-11 with three GET-based filters (`q` title icontains, `genre` single dropdown, `date` exact-day match) plus pagination preservation and a filter-aware empty state. Closes US-12. Mostly extends existing surface — no new view, no new URL, no model changes.

**Architecture:** New `MovieFilterForm(forms.Form)` in `apps/cinema/forms.py` with three optional fields. `MovieListView.get_queryset()` instantiates the form from `request.GET`, narrows the existing US-11 queryset chain in three independent `if` branches. Template gains a filter bar above the grid, the empty-state alert branches by `request.GET` truthiness, and pagination links use the Django 5.1+ `{% querystring %}` tag to keep filter params across pages. The `next_screening_at` annotation from US-11 stays unchanged — the new `?date=` filter narrows the result set, not the annotation.

**Tech Stack:** Django 6 `forms.Form` (`CharField` / `ModelChoiceField` / `DateField`), `{% querystring %}` template tag (Django ≥ 5.1, available in our Django 6), `timezone.make_aware` for DST-safe day window math, pytest-django (`client`, `django_assert_max_num_queries`).

**Branch:** `feat/FR-02-movie-list-filtering` (per backlog US-12).

---

## Pre-flight checklist (read these first)

- [ ] `docs/superpowers/specs/2026-05-21-movie-list-filtering-design.md` — design decisions (Q1-Q3, day-window math)
- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-02 — spec source of truth (lines ~209-214)
- [ ] `apps/cinema/views.py` — current `MovieListView` from US-11 (the queryset chain being extended)
- [ ] `apps/cinema/models.py` — `Movie` (title, genres M2M), `Genre`, `Screening` (start_time)
- [ ] `templates/cinema/movie_list.html` — template being extended (filter bar above grid, empty-state branching, pagination)
- [ ] `tests/cinema/test_movie_list.py` — existing tests (TestRouting/TestQueryset/TestCardRendering/TestPagination/TestEmptyState/TestQueryBudget); N+1 cap at 4 will bump to 5
- [ ] `tests/cinema/factories.py` — `MovieFactory`, `GenreFactory`, `ScreeningFactory`

---

## File structure

```
apps/cinema/
├── forms.py                                  ★ NEW (Task 2)
└── views.py                                  ✎ extend MovieListView (Task 3)

templates/cinema/
└── movie_list.html                           ✎ + filter bar + empty-state branching + querystring pagination (Task 4)

tests/cinema/
├── test_movie_filter_form.py                 ★ NEW (Task 2, 6 form unit tests)
└── test_movie_list.py                        ✎ + TestFilters (12 integration) + empty-state variants (4) + pagination preservation (1) + bump N+1 cap 4 → 5 (Tasks 3 + 4)

.Claude/backlog.md                            ✎ status board (Task 1 + Task 5)
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress (Task 5)
```

No new dependencies. No new migrations. No settings edits.

---

## Task 1: Branch + backlog DoR

**Files:**
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (user): branch off main**

```bash
git checkout main
git pull
git checkout -b feat/FR-02-movie-list-filtering
```

- [ ] **Step 2 (user): commit the spec** (untracked from brainstorming)

```bash
git add docs/superpowers/specs/2026-05-21-movie-list-filtering-design.md
git commit -m "docs(M2): add design spec for US-12 movie list filtering"
```

- [ ] **Step 3 (Claude): move US-12 from Ready to In Progress in `.Claude/backlog.md` §7; queue US-14 next**

- [ ] **Step 4 (user): commit plan + backlog**

```bash
git add docs/superpowers/plans/2026-05-21-movie-list-filtering.md .Claude/backlog.md
git commit -m "docs(M2): add implementation plan for US-12 + mark in progress"
```

---

## Task 2: `MovieFilterForm`

**Files:**
- Create: `apps/cinema/forms.py`
- Create: `tests/cinema/test_movie_filter_form.py`

**Why first:** Form is self-contained. Locks in field types/required semantics before view consumes it.

- [ ] **Step 1 (Claude): create `tests/cinema/test_movie_filter_form.py`**

```python
"""Unit tests for MovieFilterForm (US-12 / FR-02)."""

from datetime import date

import pytest

from apps.cinema.forms import MovieFilterForm
from tests.cinema.factories import GenreFactory


pytestmark = pytest.mark.django_db


class TestMovieFilterForm:
    def test_empty_data_is_valid_with_empty_values(self):
        form = MovieFilterForm(data={})
        assert form.is_valid()
        assert form.cleaned_data["q"] == ""
        assert form.cleaned_data["genre"] is None
        assert form.cleaned_data["date"] is None

    def test_q_field_accepts_text(self):
        form = MovieFilterForm(data={"q": "Matrix"})
        assert form.is_valid()
        assert form.cleaned_data["q"] == "Matrix"

    def test_genre_field_accepts_valid_pk(self):
        genre = GenreFactory(name="Drama")
        form = MovieFilterForm(data={"genre": str(genre.pk)})
        assert form.is_valid()
        assert form.cleaned_data["genre"] == genre

    def test_date_field_accepts_iso_date_string(self):
        form = MovieFilterForm(data={"date": "2026-05-23"})
        assert form.is_valid()
        assert form.cleaned_data["date"] == date(2026, 5, 23)

    def test_date_field_rejects_malformed_value(self):
        form = MovieFilterForm(data={"date": "not-a-date"})
        assert not form.is_valid()
        assert "date" in form.errors

    def test_genre_field_rejects_nonexistent_pk(self):
        form = MovieFilterForm(data={"genre": "99999"})
        assert not form.is_valid()
        assert "genre" in form.errors
```

- [ ] **Step 2 (user): run — expect 6 FAIL** (`ModuleNotFoundError: apps.cinema.forms`)

```bash
poetry run pytest tests/cinema/test_movie_filter_form.py -v
```

- [ ] **Step 3 (user): create `apps/cinema/forms.py`** (reference impl):

```python
from django import forms

from apps.cinema.models import Genre


class MovieFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={"placeholder": "Tytuł filmu...", "class": "form-control"}
        ),
        label="",
    )
    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all(),
        required=False,
        empty_label="Wszystkie gatunki",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        ),
        label="",
    )
```

- [ ] **Step 4 (user): rerun — expect 6 PASS**

```bash
poetry run pytest tests/cinema/test_movie_filter_form.py -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_filter_form.py apps/cinema/forms.py
git commit -m "feat(FR-02): MovieFilterForm with q/genre/date fields"
```

---

## Task 3: Wire filter form into view queryset

**Files:**
- Modify: `tests/cinema/test_movie_list.py`
- Modify: `apps/cinema/views.py`

**Why now:** Form exists; lock view-level filter behavior before template renders the bar.

- [ ] **Step 1 (Claude): extend `tests/cinema/test_movie_list.py` — append imports + `TestFilters` class**

Add to top-of-file imports (right under existing imports, before `pytestmark`):

```python
from apps.cinema.forms import MovieFilterForm
```

Append at end of file:

```python
class TestFilters:
    def test_q_filter_matches_icontains(self, client):
        now = timezone.now()
        wanted = MovieFactory(title="The Matrix")
        other = MovieFactory(title="Other Movie")
        ScreeningFactory(movie=wanted, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=other, start_time=now + timedelta(days=1))

        response = client.get("/?q=matrix")

        listed = list(response.context["movies"])
        assert wanted in listed
        assert other not in listed

    def test_q_filter_is_case_insensitive(self, client):
        movie = MovieFactory(title="Inception")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/?q=INCEPTION")

        assert movie in list(response.context["movies"])

    def test_q_filter_empty_string_returns_all(self, client):
        now = timezone.now()
        m1 = MovieFactory()
        m2 = MovieFactory()
        ScreeningFactory(movie=m1, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=m2, start_time=now + timedelta(days=1))

        response = client.get("/?q=")

        listed = list(response.context["movies"])
        assert m1 in listed
        assert m2 in listed

    def test_genre_filter_narrows_results(self, client):
        now = timezone.now()
        drama = GenreFactory(name="Drama")
        action = GenreFactory(name="Action")
        movie_drama = MovieFactory()
        movie_action = MovieFactory()
        movie_drama.genres.add(drama)
        movie_action.genres.add(action)
        ScreeningFactory(movie=movie_drama, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=movie_action, start_time=now + timedelta(days=1))

        response = client.get(f"/?genre={drama.pk}")

        listed = list(response.context["movies"])
        assert movie_drama in listed
        assert movie_action not in listed

    def test_genre_filter_invalid_pk_returns_all(self, client):
        now = timezone.now()
        m1 = MovieFactory()
        m2 = MovieFactory()
        ScreeningFactory(movie=m1, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=m2, start_time=now + timedelta(days=1))

        response = client.get("/?genre=99999")

        listed = list(response.context["movies"])
        assert m1 in listed
        assert m2 in listed

    def test_date_filter_matches_screening_on_that_day(self, client):
        now = timezone.now()
        tomorrow = (now + timedelta(days=1)).date()
        movie_match = MovieFactory()
        movie_other = MovieFactory()
        ScreeningFactory(
            movie=movie_match,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )
        ScreeningFactory(
            movie=movie_other,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=2),
        )

        response = client.get(f"/?date={tomorrow.isoformat()}")

        listed = list(response.context["movies"])
        assert movie_match in listed
        assert movie_other not in listed

    def test_date_filter_boundary_inclusive_at_midnight(self, client):
        # Screening exactly at 00:00 of the filter day (local TZ) should match.
        import datetime as dt
        target_date = (timezone.now() + timedelta(days=1)).date()
        midnight_local = timezone.make_aware(
            dt.datetime.combine(target_date, dt.time(0, 0))
        )
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=midnight_local)

        response = client.get(f"/?date={target_date.isoformat()}")

        assert movie in list(response.context["movies"])

    def test_date_filter_boundary_inclusive_at_end_of_day(self, client):
        import datetime as dt
        target_date = (timezone.now() + timedelta(days=1)).date()
        almost_midnight = timezone.make_aware(
            dt.datetime.combine(target_date, dt.time(23, 59, 59))
        )
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=almost_midnight)

        response = client.get(f"/?date={target_date.isoformat()}")

        assert movie in list(response.context["movies"])

    def test_date_filter_excludes_next_day(self, client):
        # Screening at 00:00 of the day AFTER the filter date should NOT match.
        import datetime as dt
        target_date = (timezone.now() + timedelta(days=1)).date()
        next_day_midnight = timezone.make_aware(
            dt.datetime.combine(target_date + timedelta(days=1), dt.time(0, 0))
        )
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=next_day_midnight)

        response = client.get(f"/?date={target_date.isoformat()}")

        assert movie not in list(response.context["movies"])

    def test_combined_filters_intersect(self, client):
        now = timezone.now()
        drama = GenreFactory(name="Drama")
        target_date = (now + timedelta(days=1)).date()

        # The only movie matching all three filters.
        match = MovieFactory(title="Star Drama")
        match.genres.add(drama)
        ScreeningFactory(
            movie=match,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )

        # Wrong title.
        wrong_title = MovieFactory(title="Other")
        wrong_title.genres.add(drama)
        ScreeningFactory(
            movie=wrong_title,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )

        # Wrong genre.
        action = GenreFactory(name="Action")
        wrong_genre = MovieFactory(title="Star Action")
        wrong_genre.genres.add(action)
        ScreeningFactory(
            movie=wrong_genre,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )

        # Wrong date.
        wrong_date = MovieFactory(title="Star Future")
        wrong_date.genres.add(drama)
        ScreeningFactory(
            movie=wrong_date,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=5),
        )

        response = client.get(
            f"/?q=star&genre={drama.pk}&date={target_date.isoformat()}"
        )

        listed = list(response.context["movies"])
        assert match in listed
        assert wrong_title not in listed
        assert wrong_genre not in listed
        assert wrong_date not in listed

    def test_filter_form_in_context(self, client):
        response = client.get("/")
        assert isinstance(response.context["filter_form"], MovieFilterForm)
```

- [ ] **Step 2 (user): run — expect 11 FAIL** (current view ignores `request.GET`; also `filter_form` not in context)

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestFilters -v
```

- [ ] **Step 3 (user): extend `apps/cinema/views.py`** — replace `MovieListView` with:

```python
import datetime
from datetime import time, timedelta

from django.db.models import Min, Q
from django.utils import timezone
from django.views.generic import DetailView, ListView

from apps.cinema.forms import MovieFilterForm
from apps.cinema.models import Movie
from apps.cinema.utils import youtube_embed_url


class MovieListView(ListView):
    model = Movie
    template_name = "cinema/movie_list.html"
    context_object_name = "movies"
    paginate_by = 12

    def get_queryset(self):
        now = timezone.now()
        qs = (
            Movie.objects
            .annotate(
                next_screening_at=Min(
                    "screenings__start_time",
                    filter=Q(screenings__start_time__gte=now),
                )
            )
            .filter(next_screening_at__isnull=False)
            .prefetch_related("genres")
        )

        form = MovieFilterForm(self.request.GET or None)
        if form.is_valid():
            if q := form.cleaned_data.get("q"):
                qs = qs.filter(title__icontains=q)
            if genre := form.cleaned_data.get("genre"):
                qs = qs.filter(genres=genre)
            if d := form.cleaned_data.get("date"):
                day_start = timezone.make_aware(
                    datetime.datetime.combine(d, time.min)
                )
                day_end = day_start + timedelta(days=1)
                qs = qs.filter(
                    screenings__start_time__gte=day_start,
                    screenings__start_time__lt=day_end,
                ).distinct()

        return qs.order_by("next_screening_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = MovieFilterForm(self.request.GET or None)
        return ctx


# MovieDetailView from US-13 stays unchanged below.
```

Important: keep the existing `MovieDetailView` class intact below `MovieListView`. Only `MovieListView` and its imports change.

- [ ] **Step 4 (user): rerun — expect 11 PASS** (plus all US-11/13 movie_list tests unchanged)

```bash
poetry run pytest tests/cinema/test_movie_list.py -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_list.py apps/cinema/views.py
git commit -m "feat(FR-02): wire filter form into MovieListView queryset"
```

---

## Task 4: Template — filter bar + empty-state branching + querystring pagination + N+1 cap bump

**Files:**
- Modify: `tests/cinema/test_movie_list.py`
- Modify: `templates/cinema/movie_list.html`

- [ ] **Step 1 (Claude): append render tests + bump N+1 cap**

Append render tests (new classes for clarity):

```python
class TestFilterFormRendering:
    def test_filter_form_q_field_renders(self, client):
        response = client.get("/")
        content = response.content.decode()
        assert 'name="q"' in content
        assert 'placeholder="Tytuł filmu..."' in content

    def test_filter_form_genre_dropdown_includes_empty_label(self, client):
        GenreFactory(name="Drama")
        response = client.get("/")
        content = response.content.decode()
        assert "Wszystkie gatunki" in content
        assert 'name="genre"' in content

    def test_filter_form_date_input_uses_html5_type(self, client):
        response = client.get("/")
        content = response.content.decode()
        assert 'type="date"' in content
        assert 'name="date"' in content

    def test_filter_form_preserves_submitted_values(self, client):
        response = client.get("/?q=star&date=2026-05-23")
        content = response.content.decode()
        assert 'value="star"' in content
        assert 'value="2026-05-23"' in content


class TestResetLink:
    def test_reset_link_hidden_when_no_filters_active(self, client):
        response = client.get("/")
        content = response.content.decode()
        assert "Wyczyść filtry" not in content
        # Reset (×) button absent.
        assert 'title="Wyczyść filtry"' not in content

    def test_reset_link_visible_when_filters_active(self, client):
        response = client.get("/?q=xyz")
        content = response.content.decode()
        assert 'title="Wyczyść filtry"' in content
        assert 'href="/movies/"' in content


class TestEmptyStateVariants:
    def test_filter_empty_state_when_no_match(self, client):
        # Movie exists but no match for ?q=zzzzzz
        movie = MovieFactory(title="Inception")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/?q=zzzzzz")
        content = response.content.decode()

        assert "Brak filmów pasujących" in content
        assert "Wyczyść filtry" in content
        # The "no future screenings anywhere" copy must NOT appear here.
        assert "Wróć wkrótce" not in content

    def test_no_screenings_empty_state_copy_when_no_filters_no_movies(self, client):
        # No movies anywhere.
        response = client.get("/")
        content = response.content.decode()

        assert "Aktualnie brak filmów" in content
        assert "Wróć wkrótce" in content
        # Filter-empty copy must NOT appear here.
        assert "Brak filmów pasujących" not in content


class TestPaginationFilterPreservation:
    def test_filter_pagination_preserves_query_params(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory(title=f"Common Movie {i}")
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/?q=Common")
        content = response.content.decode()

        # Pagination block must contain both q=Common and page=2 (order-insensitive).
        # The querystring tag emits URL-encoded form (no quoting needed for these chars).
        assert "q=Common" in content
        assert "page=2" in content
```

Now bump the N+1 cap. Find existing `TestQueryBudget::test_full_page_uses_bounded_queries` and update:

```python
class TestQueryBudget:
    def test_full_page_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """12 movies, each with 2 genres → without prefetch this would be 1 + 12 = 13 queries
        for genres alone, blowing past the budget. The annotated queryset's prefetch_related
        keeps it tight.

        US-12 adds 1 query for the Genre filter dropdown (queryset eval in form rendering),
        so the cap bumps from 4 → 5.
        """
        now = timezone.now()
        for i in range(12):
            movie = MovieFactory()
            movie.genres.add(GenreFactory(), GenreFactory())
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        # Budget: 1 paginator.count + 1 movies + 1 prefetched genres + 1 form genre dropdown = 4 baseline.
        # Cap at 5 to absorb any test-harness query without flaking.
        with django_assert_max_num_queries(5):
            client.get("/")
```

- [ ] **Step 2 (user): run — expect ~14 FAIL** (template lacks filter bar, empty-state branching, querystring pagination; budget bumped pre-emptively might still pass)

```bash
poetry run pytest tests/cinema/test_movie_list.py -v -k "TestFilterFormRendering or TestResetLink or TestEmptyStateVariants or TestPaginationFilterPreservation"
```

- [ ] **Step 3 (user): rewrite `templates/cinema/movie_list.html`** (reference impl — insert filter bar + branch empty state + querystring pagination):

```html
{% extends "base.html" %}

{% block title %}Repertuar — KinoMania{% endblock %}

{% block content %}
<h1 class="h2 mb-4">Repertuar</h1>

<form method="get" class="row g-2 mb-4" role="search">
  <div class="col-md-5">{{ filter_form.q }}</div>
  <div class="col-md-3">{{ filter_form.genre }}</div>
  <div class="col-md-2">{{ filter_form.date }}</div>
  <div class="col-md-2 d-flex gap-2">
    <button type="submit" class="btn btn-primary flex-grow-1">Filtruj</button>
    {% if request.GET %}
      <a href="{% url 'cinema:movie_list' %}" class="btn btn-outline-secondary"
         title="Wyczyść filtry">×</a>
    {% endif %}
  </div>
</form>

{% if movies %}
  <div class="row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-xl-4 g-4">
    {% for movie in movies %}
      <div class="col">
        <div class="card h-100">
          {% if movie.poster %}
            <img src="{{ movie.poster.url }}" class="card-img-top"
                 alt="{{ movie.title }}"
                 style="aspect-ratio: 2/3; object-fit: cover;">
          {% else %}
            <div class="card-img-top bg-light d-flex align-items-center justify-content-center"
                 style="aspect-ratio: 2/3; font-size: 3rem;" aria-hidden="true">🎬</div>
          {% endif %}
          <div class="card-body d-flex flex-column">
            <h5 class="card-title">{{ movie.title }}</h5>
            <p class="mb-2">
              {% for genre in movie.genres.all %}
                <span class="badge bg-secondary">{{ genre.name }}</span>
              {% endfor %}
            </p>
            <p class="text-muted small mb-3">
              Najbliższy seans: {{ movie.next_screening_at|date:"d.m.Y H:i" }}
            </p>
            <a href="{{ movie.get_absolute_url }}" class="btn btn-primary btn-sm mt-auto">Szczegóły</a>
          </div>
        </div>
      </div>
    {% endfor %}
  </div>

  {% if is_paginated %}
    <nav aria-label="Paginacja" class="mt-4">
      <ul class="pagination justify-content-center">
        {% if page_obj.has_previous %}
          <li class="page-item">
            <a class="page-link" href="?{% querystring page=page_obj.previous_page_number %}">&laquo;</a>
          </li>
        {% endif %}
        <li class="page-item active">
          <span class="page-link">{{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span>
        </li>
        {% if page_obj.has_next %}
          <li class="page-item">
            <a class="page-link" href="?{% querystring page=page_obj.next_page_number %}">&raquo;</a>
          </li>
        {% endif %}
      </ul>
    </nav>
  {% endif %}
{% else %}
  <div class="alert alert-info">
    {% if request.GET %}
      Brak filmów pasujących do wybranych kryteriów.
      <a href="{% url 'cinema:movie_list' %}">Wyczyść filtry</a> żeby zobaczyć wszystkie.
    {% else %}
      Aktualnie brak filmów z zaplanowanymi seansami. Wróć wkrótce!
    {% endif %}
  </div>
{% endif %}
{% endblock %}
```

Key changes vs US-11 version:
1. New `<form method="get">` block above the grid.
2. Pagination links now use `{% querystring page=... %}` (preserves filters).
3. `{% else %}` branch of `{% if movies %}` now reads `request.GET` to choose copy.

- [ ] **Step 4 (user): rerun — expect ~14 PASS** (plus all US-11/13 movie_list tests still green; the budget cap test should remain green at ≤5 queries)

```bash
poetry run pytest tests/cinema/test_movie_list.py -v
```

If `TestPaginationFilterPreservation::test_filter_pagination_preserves_query_params` fails, the most likely cause is Django version < 5.1 missing `{% querystring %}`. Project is on Django 6 per `pyproject.toml` — verify with `poetry run python -c "import django; print(django.get_version())"`. If somehow on an older Django, swap to manual `?q={{ request.GET.q }}&page=...` concat (less elegant but Django-version-agnostic).

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_list.py templates/cinema/movie_list.html
git commit -m "feat(FR-02): filter bar + empty-state branching + querystring pagination"
```

---

## Task 5: Coverage + smoke + PR

**Files:**
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (user): full suite + coverage**

```bash
poetry run pytest --cov=apps --cov-report=term-missing
```

Expected: all tests pass; `apps/cinema/forms.py` 100%; `apps/cinema/views.py` 100% (or close — the `if d := ...` branch covered by date tests); project ≥80%.

- [ ] **Step 2 (user): manual smoke**

```bash
poetry run python manage.py seed_db --flush
poetry run python manage.py runserver
```

Visit `http://127.0.0.1:8000/`. Confirm:
- Filter bar above the grid (q input + genre dropdown + date input + Filtruj button)
- No "Wyczyść filtry" link (no filters active)
- Try `?q=zzz` (or type into `q` and submit) — empty-state with "Brak filmów pasujących" + "Wyczyść filtry" link
- Try `?genre=<id of seed Drama>` — only Drama movies
- Try `?date=` with today's date or tomorrow — only movies playing that day (seed places screenings randomly, so try a few dates)
- Combine filters in URL bar — intersection applies
- Click pagination next page on a filtered view (`?q=common&page=2`) — filters preserved in URL

- [ ] **Step 3 (Claude): update `.Claude/backlog.md` §7** — US-12 → Done; queue **US-14** (daily screenings list, FR-04) next per m2_planning.

- [ ] **Step 4 (user): commit backlog**

```bash
git add .Claude/backlog.md
git commit -m "docs(M2): mark US-12 done, queue US-14 next"
```

- [ ] **Step 5 (user): push + open PR**

```bash
git push -u origin feat/FR-02-movie-list-filtering
```

PR body:

```
Title: feat(FR-02): movie list filtering + search — US-12

## Summary
- New `MovieFilterForm(forms.Form)` with `q` (text icontains), `genre` (ModelChoice dropdown), `date` (HTML5 date input). All fields optional.
- `MovieListView.get_queryset()` extended: form-driven narrowing on top of US-11's annotated queryset. `?date=` uses DST-safe `make_aware(...)` for day boundaries.
- Filter bar above the grid; "Wyczyść filtry" reset link visible only when filters active.
- Empty-state copy branches by `request.GET`: "Brak filmów pasujących" + reset link vs original "Wróć wkrótce".
- Pagination preserves filter query params via Django 5.1+ `{% querystring %}` tag.
- ~22 new tests (6 form unit + 11 filter integration + 4 form render + 2 reset link + 2 empty-state variants + 1 pagination preservation).
- N+1 budget cap bumped 4 → 5 (Genre dropdown queryset eval).

## Closes
- US-12 (FR-02)

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-05-21-movie-list-filtering-design.md`
- Plan: `docs/superpowers/plans/2026-05-21-movie-list-filtering.md`
- FR spec: `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-02

## Out of scope (deferred)
- Multiselect genre filter (Q2 chose dropdown) — future enhancement
- Full-text search (`to_tsvector`) → US-17 or post-M2 polish
- htmx live filtering (Q1 chose pure-Django) — out of M2
- Daily screenings view (`/screenings/?date=...`) → US-14 (FR-04)

## Test plan
- [ ] CI green (lint, mypy, tests, ≥80% coverage)
- [ ] Manual smoke: each filter alone + combinations + reset link + pagination preservation
- [ ] Empty-state copy differs between "no movies anywhere" and "filter matched nothing"
```

- [ ] **Step 6 (after merge — separate session): update `memory/project_kinomania_bootstrap.md`** — M2 progress: 6/8 done; next is US-14.

---

## Self-review summary

- ✅ FR-02 acceptance criteria: text input title icontains (Task 3), genre dropdown (Task 2 form + Task 3 view), date picker (Task 2 form + Task 3 view), GET params (`?q=...&genre=...&date=...` — pure Form). All matched.
- ✅ Spec §1 brainstorming decisions Q1-Q3 baked in across all tasks.
- ✅ Spec §2 form: Task 2 fully covers field shapes + widgets + `required=False` semantics.
- ✅ Spec §3 view: Task 3 implements all three filter branches + walrus pattern + `.distinct()` on date join + day-window math.
- ✅ Spec §4 template: Task 4 covers filter bar + reset link visibility + empty-state branching + querystring pagination.
- ✅ Spec §5 tests: all 5 sub-areas (form unit, filter integration, render, reset/empty, pagination preservation) distributed across Tasks 2, 3, 4.
- ✅ Spec §6 file changes: every file accounted for.
- ✅ Spec §7 commit plan: matches task structure (5 commits + 2 docs).
- ✅ N+1 cap bump (4 → 5) explained in test comment and PR body.
- ✅ No placeholders; every step has runnable code/commands.
- ✅ One commit per logical unit; reviewable diffs.
