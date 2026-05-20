# MovieList View Implementation Plan (US-11 — FR-01)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py`, `.html`, settings edits). **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Replace M1 `HomeView` with `MovieListView(ListView)` rendering paginated movie cards sorted by soonest future screening. Mounts at both `/` (legacy alias) and `/movies/` (canonical). Closes US-11. Unblocks US-12 (filtering), US-13 (movie detail).

**Architecture:** Single Django `ListView` subclass with custom `get_queryset()` that annotates each movie with its soonest future screening (`Min(...)` + embedded `filter=Q(...)`), filters out movies without one, prefetches genres for badge rendering, and orders by the annotation. Template `cinema/movie_list.html` extends `base.html` with a Bootstrap card grid (`row-cols-1/sm-2/md-3/xl-4`, 12 per page) + pagination nav + empty-state alert. M1's `HomeView`, `templates/cinema/home.html`, and `tests/cinema/test_home.py` are removed in the same PR.

**Tech Stack:** Django 6 `ListView`, `Min`/`Q` annotations, `prefetch_related`, Bootstrap 5.3.3 (CDN, already in `base.html`), pytest-django (`client` fixture, `assertNumQueries`, `assertContains`).

**Branch:** `feat/FR-01-movie-list` (per backlog US-11).

---

## Pre-flight checklist (read these first)

- [ ] `docs/superpowers/specs/2026-05-21-movie-list-design.md` — design decisions (Q1-Q4, queryset shape, template)
- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-01 — spec source of truth (lines ~201-207)
- [ ] `.Claude/m2_planning.md` — milestone kickoff; US-11 is "first user-facing M2 view, sets the pattern"
- [ ] `apps/cinema/views.py` — current `HomeView` (TemplateView placeholder), being replaced
- [ ] `apps/cinema/urls.py` — current `path("", HomeView.as_view(), name="home")`, being extended
- [ ] `templates/base.html` — Bootstrap 5.3.3 setup, navbar `{% url 'cinema:home' %}` link (must continue to resolve)
- [ ] `templates/cinema/home.html` — M1 placeholder being deleted (Task 2)
- [ ] `tests/cinema/test_home.py` — M1 hero/CTA assertions being deleted (Task 2)
- [ ] `tests/cinema/test_admin.py` — `PNG_1X1` bytes fixture pattern, reused for the poster test
- [ ] `tests/cinema/factories.py` — `MovieFactory`, `GenreFactory`, `ScreeningFactory` already exist (US-10)

---

## File structure

```
apps/cinema/
├── views.py                                  ✎ HomeView → MovieListView (Task 2 + 3)
└── urls.py                                   ✎ + path("movies/", ...) (Task 2)

templates/cinema/
├── movie_list.html                           ★ NEW (Task 2 scaffold → Task 4 full markup → Task 5 pagination/empty)
└── home.html                                 ✖ DELETE (Task 2)

tests/cinema/
├── test_movie_list.py                        ★ NEW (Task 2..6, ~15 tests)
└── test_home.py                              ✖ DELETE (Task 2)

.Claude/backlog.md                            ✎ status board (Task 1 + Task 6)
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress (Task 6)
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
git checkout -b feat/FR-01-movie-list
```

- [ ] **Step 2 (user): commit the spec** (untracked from brainstorming)

```bash
git add docs/superpowers/specs/2026-05-21-movie-list-design.md
git commit -m "docs(M2): add design spec for US-11 movie list view"
```

- [ ] **Step 3 (Claude): move US-11 from Ready to In Progress in `.Claude/backlog.md` §7**

- [ ] **Step 4 (user): commit plan + backlog update**

```bash
git add docs/superpowers/plans/2026-05-21-movie-list.md .Claude/backlog.md
git commit -m "docs(M2): add implementation plan for US-11 + mark in progress"
```

---

## Task 2: Routing scaffold + remove M1 HomeView

**Files:**
- Create: `tests/cinema/test_movie_list.py`
- Modify: `apps/cinema/views.py`
- Modify: `apps/cinema/urls.py`
- Create: `templates/cinema/movie_list.html` (minimal scaffold)
- Delete: `templates/cinema/home.html`
- Delete: `tests/cinema/test_home.py`

**Why this order:** Get routing + scaffolded template green first, with HomeView/test_home.py cleanly removed in the same commit. The naive queryset (`Movie.objects.all()`) is fine for the routing tests — Task 3 narrows it.

- [ ] **Step 1 (Claude): create `tests/cinema/test_movie_list.py` with routing-only tests**

```python
"""Tests for MovieListView (US-11 / FR-01)."""

import pytest
from django.urls import reverse


pytestmark = pytest.mark.django_db


class TestRouting:
    def test_root_url_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_movies_url_returns_200(self, client):
        response = client.get("/movies/")
        assert response.status_code == 200

    def test_cinema_home_reverses_to_root(self):
        assert reverse("cinema:home") == "/"

    def test_cinema_movie_list_reverses_to_movies(self):
        assert reverse("cinema:movie_list") == "/movies/"

    def test_root_uses_movie_list_template(self, client):
        response = client.get("/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_list.html" in template_names

    def test_movies_uses_movie_list_template(self, client):
        response = client.get("/movies/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_list.html" in template_names

    def test_anonymous_user_gets_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_authenticated_user_gets_200(self, client, django_user_model):
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get("/")
        assert response.status_code == 200
```

- [ ] **Step 2 (user): run — expect 8 FAIL** (templates not found / NoReverseMatch for `cinema:movie_list`)

```bash
poetry run pytest tests/cinema/test_movie_list.py -v
```

- [ ] **Step 3 (user): create `templates/cinema/movie_list.html` minimal scaffold**

```html
{% extends "base.html" %}

{% block title %}Repertuar — KinoMania{% endblock %}

{% block content %}
<h1 class="h2 mb-4">Repertuar</h1>
{% endblock %}
```

- [ ] **Step 4 (user): rewrite `apps/cinema/views.py`** (replaces HomeView entirely):

```python
from django.views.generic import ListView

from apps.cinema.models import Movie


class MovieListView(ListView):
    model = Movie
    template_name = "cinema/movie_list.html"
    context_object_name = "movies"
    paginate_by = 12
```

- [ ] **Step 5 (user): rewrite `apps/cinema/urls.py`**:

```python
from django.urls import path

from apps.cinema.views import MovieListView

app_name = "cinema"

urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
]
```

- [ ] **Step 6 (user): delete the M1 placeholder template + its tests**

```bash
git rm templates/cinema/home.html
git rm tests/cinema/test_home.py
```

(`git rm` stages the deletion. If the files are still in your working tree, this works; if you'd already deleted them with `rm`, use `git add -A`.)

- [ ] **Step 7 (user): rerun — expect 8 PASS**

```bash
poetry run pytest tests/cinema/test_movie_list.py -v
```

- [ ] **Step 8 (user): full suite — confirm `test_base_template.py` still passes** (navbar Repertuar → `/` assertion is unaffected since `cinema:home` still resolves to `/`)

```bash
poetry run pytest -v
```

Expected: all tests pass (US-08/US-10/US-15/US-16 + Task 2 routing). `test_home.py` is gone, so its previous tests no longer count.

- [ ] **Step 9 (user): commit**

```bash
git add tests/cinema/test_movie_list.py apps/cinema/views.py apps/cinema/urls.py templates/cinema/movie_list.html
git commit -m "feat(FR-01): replace HomeView with MovieListView + URL config"
```

---

## Task 3: Queryset — visibility filter + sort

**Files:**
- Modify: `tests/cinema/test_movie_list.py`
- Modify: `apps/cinema/views.py`

**Why now:** Pin down the data layer before touching the template. The Min/Q annotation is the trickiest piece of US-11; locking it via failing-then-green tests prevents subtle drift later (e.g., when US-12 adds filtering).

- [ ] **Step 1 (Claude): extend `tests/cinema/test_movie_list.py`**

Append imports at top of file (under existing imports):

```python
from datetime import timedelta

from django.utils import timezone

from tests.cinema.factories import GenreFactory, MovieFactory, ScreeningFactory
```

Append class:

```python
class TestQueryset:
    def test_movie_with_future_screening_is_visible(self, client):
        movie = MovieFactory(title="Future Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")

        assert movie in response.context["movies"]

    def test_movie_with_only_past_screening_is_hidden(self, client):
        movie = MovieFactory(title="Past Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))

        response = client.get("/")

        assert movie not in response.context["movies"]

    def test_movie_with_no_screenings_is_hidden(self, client):
        movie = MovieFactory(title="Orphan Movie")

        response = client.get("/")

        assert movie not in response.context["movies"]

    def test_movie_with_past_and_future_screenings_uses_future_as_next(self, client):
        """Regression: Min() must include filter=Q(start_time>=now), otherwise
        next_screening_at picks up the past screening's date."""
        movie = MovieFactory(title="Mixed Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=3))
        future = timezone.now() + timedelta(days=2)
        ScreeningFactory(movie=movie, start_time=future)

        response = client.get("/")

        listed = list(response.context["movies"])
        assert movie in listed
        # The annotation rounds to microseconds; allow 1-second tolerance.
        rendered = next(m for m in listed if m.pk == movie.pk)
        assert abs((rendered.next_screening_at - future).total_seconds()) < 1

    def test_movies_are_sorted_by_next_screening_ascending(self, client):
        now = timezone.now()
        movie_late = MovieFactory(title="Late")
        movie_early = MovieFactory(title="Early")
        movie_mid = MovieFactory(title="Mid")
        ScreeningFactory(movie=movie_late, start_time=now + timedelta(days=3))
        ScreeningFactory(movie=movie_early, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=movie_mid, start_time=now + timedelta(days=2))

        response = client.get("/")

        titles = [m.title for m in response.context["movies"]]
        assert titles == ["Early", "Mid", "Late"]
```

- [ ] **Step 2 (user): run — expect FAIL on visibility/sort tests** (current view uses `Movie.objects.all()`, so past/orphan movies leak in)

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestQueryset -v
```

- [ ] **Step 3 (user): extend `apps/cinema/views.py`** with the annotated queryset:

```python
from django.db.models import Min, Q
from django.utils import timezone
from django.views.generic import ListView

from apps.cinema.models import Movie


class MovieListView(ListView):
    model = Movie
    template_name = "cinema/movie_list.html"
    context_object_name = "movies"
    paginate_by = 12

    def get_queryset(self):
        now = timezone.now()
        return (
            Movie.objects
            .annotate(
                next_screening_at=Min(
                    "screenings__start_time",
                    filter=Q(screenings__start_time__gte=now),
                )
            )
            .filter(next_screening_at__isnull=False)
            .prefetch_related("genres")
            .order_by("next_screening_at")
        )
```

- [ ] **Step 4 (user): rerun — expect 5 PASS**

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestQueryset -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_list.py apps/cinema/views.py
git commit -m "feat(FR-01): queryset annotation + sorting by soonest screening"
```

---

## Task 4: Template — card rendering

**Files:**
- Modify: `tests/cinema/test_movie_list.py`
- Modify: `templates/cinema/movie_list.html`

**Why now:** With visibility/sort locked, fill in card markup. Tests assert HTML fragments via `assertContains` / substring checks (not DOM parsing — overkill for this scale).

- [ ] **Step 1 (Claude): extend `tests/cinema/test_movie_list.py`**

Append at top of file (after existing imports), under the timezone import:

```python
from django.core.files.uploadedfile import SimpleUploadedFile


# Smallest valid PNG (1x1) — reused from tests/cinema/test_admin.py
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc"
    b"\xff\xff?\x03\x00\x06\x00\x02\x00\x01\xa5\xc8\x7f\xb1\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)
```

Append class:

```python
class TestCardRendering:
    def test_card_shows_title(self, client):
        movie = MovieFactory(title="Unique Card Title")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")

        assert "Unique Card Title" in response.content.decode()

    def test_card_shows_all_genre_badges(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        movie.genres.add(GenreFactory(name="Drama"), GenreFactory(name="Sci-Fi"))

        response = client.get("/")
        content = response.content.decode()

        assert "Drama" in content
        assert "Sci-Fi" in content
        assert content.count('class="badge bg-secondary"') >= 2

    def test_card_shows_next_screening_date(self, client):
        movie = MovieFactory()
        future = timezone.now().replace(hour=18, minute=30) + timedelta(days=2)
        ScreeningFactory(movie=movie, start_time=future)

        response = client.get("/")

        assert future.strftime("%d.%m.%Y %H:%M") in response.content.decode()

    def test_card_shows_disabled_details_button(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert "Szczegóły" in content
        # US-13 will drop the `disabled` class + wire href.
        assert "disabled" in content

    def test_card_uses_emoji_placeholder_when_poster_blank(self, client):
        movie = MovieFactory(poster="")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert "🎬" in content
        # No broken <img src="">
        assert 'src=""' not in content

    def test_card_uses_real_poster_when_set(self, client):
        movie = MovieFactory()
        movie.poster = SimpleUploadedFile("p.png", PNG_1X1, content_type="image/png")
        movie.save()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert movie.poster.url in content
        assert "<img" in content
```

- [ ] **Step 2 (user): run — expect 6 FAIL** (template is still the minimal scaffold)

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestCardRendering -v
```

- [ ] **Step 3 (user): expand `templates/cinema/movie_list.html`** with the full card grid:

```html
{% extends "base.html" %}

{% block title %}Repertuar — KinoMania{% endblock %}

{% block content %}
<h1 class="h2 mb-4">Repertuar</h1>

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
          <a href="#" class="btn btn-primary btn-sm mt-auto disabled">Szczegóły</a>
        </div>
      </div>
    </div>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 4 (user): rerun — expect 6 PASS**

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestCardRendering -v
```

- [ ] **Step 5 (user): cleanup test-uploaded poster (optional)** — `media/posters/p*.png` left behind. `rm media/posters/p*.png` if cluttering.

- [ ] **Step 6 (user): commit**

```bash
git add tests/cinema/test_movie_list.py templates/cinema/movie_list.html
git commit -m "feat(FR-01): movie card markup with poster placeholder + badges"
```

---

## Task 5: Pagination + empty state

**Files:**
- Modify: `tests/cinema/test_movie_list.py`
- Modify: `templates/cinema/movie_list.html`

- [ ] **Step 1 (Claude): extend `tests/cinema/test_movie_list.py`**

Append class:

```python
class TestPagination:
    def test_page_one_shows_12_cards_when_13_movies(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/")

        assert len(response.context["movies"]) == 12

    def test_page_two_shows_remaining_card_when_13_movies(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/?page=2")

        assert len(response.context["movies"]) == 1

    def test_page_out_of_range_returns_404(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/?page=3")

        assert response.status_code == 404

    def test_pagination_nav_hidden_when_one_page(self, client):
        # 12 movies → exactly one page → no nav.
        now = timezone.now()
        for i in range(12):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/")
        content = response.content.decode()

        assert 'class="pagination' not in content

    def test_pagination_nav_visible_when_multiple_pages(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/")
        content = response.content.decode()

        assert 'class="pagination' in content


class TestEmptyState:
    def test_empty_state_shown_when_no_future_screenings(self, client):
        # No movies at all.
        response = client.get("/")
        content = response.content.decode()

        assert "Aktualnie brak filmów" in content
        assert "row-cols-" not in content

    def test_empty_state_shown_when_only_past_screenings(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert "Aktualnie brak filmów" in content
```

- [ ] **Step 2 (user): run — expect 7 FAIL**

```bash
poetry run pytest tests/cinema/test_movie_list.py -v -k "Pagination or Empty"
```

- [ ] **Step 3 (user): wrap the existing card grid in `{% if movies %}...{% else %}...{% endif %}` and add pagination nav** in `templates/cinema/movie_list.html`:

```html
{% extends "base.html" %}

{% block title %}Repertuar — KinoMania{% endblock %}

{% block content %}
<h1 class="h2 mb-4">Repertuar</h1>

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
            <a href="#" class="btn btn-primary btn-sm mt-auto disabled">Szczegóły</a>
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
            <a class="page-link" href="?page={{ page_obj.previous_page_number }}">&laquo;</a>
          </li>
        {% endif %}
        <li class="page-item active">
          <span class="page-link">{{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span>
        </li>
        {% if page_obj.has_next %}
          <li class="page-item">
            <a class="page-link" href="?page={{ page_obj.next_page_number }}">&raquo;</a>
          </li>
        {% endif %}
      </ul>
    </nav>
  {% endif %}
{% else %}
  <div class="alert alert-info">
    Aktualnie brak filmów z zaplanowanymi seansami. Wróć wkrótce!
  </div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4 (user): rerun — expect 7 PASS**

```bash
poetry run pytest tests/cinema/test_movie_list.py -v -k "Pagination or Empty"
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_list.py templates/cinema/movie_list.html
git commit -m "feat(FR-01): pagination nav + empty state for movie list"
```

---

## Task 6: N+1 sanity + coverage + smoke + PR

**Files:**
- Modify: `tests/cinema/test_movie_list.py`
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (Claude): append the prefetch regression test**

```python
class TestQueryBudget:
    def test_full_page_uses_bounded_queries(self, client, django_assert_num_queries):
        """12 movies, each with 2 genres → without prefetch this would be 1 + 12 = 13 queries
        for genres alone, blowing past the budget. The annotated queryset's prefetch_related
        keeps it tight."""
        now = timezone.now()
        for i in range(12):
            movie = MovieFactory()
            movie.genres.add(GenreFactory(), GenreFactory())
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        # Budget: 1 paginator.count + 1 movies + 1 prefetched genres = 3.
        # Allow 4 to absorb any test-harness query (session etc.).
        with django_assert_num_queries(4):
            client.get("/")
```

> Note: this uses pytest-django's `django_assert_num_queries` context manager (fixture is auto-injected). If your local pytest-django version exposes it as a class-level fixture only, replace with `from django.test.utils import CaptureQueriesContext` — but pytest-django ≥ 3.0 ships the fixture form.

- [ ] **Step 2 (user): run — likely PASS** (the queryset already has `prefetch_related("genres")` from Task 3). If it FAILS with a count like 5 or 6, inspect the printed queries — most likely something added a `select_related` redundancy or the prefetch was accidentally dropped.

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestQueryBudget -v
```

- [ ] **Step 3 (user): full suite + coverage**

```bash
poetry run pytest --cov=apps --cov-report=term-missing
```

Expected: ~all tests pass; `apps/cinema/views.py` 100%, `templates/` not tracked by coverage but exercised by all the rendering tests.

- [ ] **Step 4 (user): manual smoke**

```bash
poetry run python manage.py seed_db --flush     # generates 20 movies + 100 screenings
poetry run python manage.py runserver
```

Visit `http://127.0.0.1:8000/`:
- Confirm cards render, posters show 🎬 emoji (US-16 seeds with blank posters), genre badges visible, "Najbliższy seans" dates in `d.m.Y H:m` format
- Click "Repertuar" in navbar — same page
- Visit `http://127.0.0.1:8000/movies/` — same page
- Visit `http://127.0.0.1:8000/?page=2` — confirm pagination nav at bottom

- [ ] **Step 5 (Claude): update `.Claude/backlog.md` §7** — US-11 → Done; queue **US-13** (MovieDetail) next per `.Claude/m2_planning.md` ordering (US-13 before US-12 per planning doc: detail page first because it sets the iframe/CSP design decisions, then filtering extends MovieList).

- [ ] **Step 6 (user): commit backlog update**

```bash
git add .Claude/backlog.md
git commit -m "docs(M2): mark US-11 done, queue US-13 next"
```

- [ ] **Step 7 (user): push + open PR**

```bash
git push -u origin feat/FR-01-movie-list
```

PR body:

```
Title: feat(FR-01): movie list view + URL config — US-11

## Summary
- Replace M1 `HomeView` (TemplateView placeholder) with `MovieListView(ListView)`
- Mounted at both `/` (legacy alias `cinema:home`) and `/movies/` (canonical `cinema:movie_list`)
- Queryset: annotates each movie with soonest future screening (`Min(..., filter=Q(...))`), filters out movies with no future screening, prefetches genres, orders by the annotation
- Template `cinema/movie_list.html`: responsive card grid (1/2/3/4 cols by breakpoint), 12/page pagination, empty state
- Cards show: poster (with 🎬 emoji fallback), title, genre badges, next screening date, disabled "Szczegóły" button (wired in US-13)
- Removed: `HomeView`, `templates/cinema/home.html`, `tests/cinema/test_home.py`
- ~22 new tests; assertNumQueries(4) guards against N+1

## Closes
- US-11 (FR-01)

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-05-21-movie-list-design.md`
- Plan: `docs/superpowers/plans/2026-05-21-movie-list.md`
- FR spec: `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-01

## Out of scope (deferred)
- Filtering / search (`?q=`, `?genre=`, `?date=`) → US-12 (FR-02)
- Movie detail page (`/movies/<pk>/`) → US-13 (FR-03), drops "Szczegóły" disabled + wires href
- Daily screenings list (`/screenings/?date=...`) → US-14 (FR-04)
- Performance pass (additional prefetches, query budget tightening) → US-17

## Test plan
- [ ] CI green (lint, mypy, tests, ≥80% coverage)
- [ ] Manual smoke: `seed_db --flush` then visit `/`, `/movies/`, `/?page=2`
- [ ] Cards render with 🎬 emoji placeholder for blank posters
- [ ] Navbar "Repertuar" link still works (alias-style)
```

- [ ] **Step 8 (after merge, separate session): update `memory/project_kinomania_bootstrap.md`** — M2 progress: 4/8 done; next is US-13.

---

## Self-review summary

- ✅ FR-01 acceptance criteria: future screenings only (Task 3), card with poster/title/genres/date/details (Task 4), paginate 12 (Task 5), public access (Task 2 anon/auth tests).
- ✅ Spec §2 architecture (CBV, dual URL): Task 2.
- ✅ Spec §3 queryset (annotation + filter + prefetch + order): Task 3.
- ✅ Spec §4 template (full structure, decisions): Tasks 4 + 5.
- ✅ Spec §5 test coverage (all 7 categories): distributed Tasks 2-6.
- ✅ Spec §6 file changes: every file accounted for.
- ✅ Spec §7 commit plan: roughly matches task structure (5 feature commits + docs).
- ✅ HomeView/home.html/test_home.py cleanup explicitly in Task 2 (no dangling M1 artifacts).
- ✅ N+1 regression test (Task 6) protects the prefetch decision from drift.
- ✅ No placeholders; every step has runnable code/commands.
- ✅ One commit per logical unit (routing / queryset / cards / pagination / cleanup-docs) — small reviewable diffs.
