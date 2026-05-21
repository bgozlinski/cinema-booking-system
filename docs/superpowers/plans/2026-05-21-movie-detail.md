# MovieDetail View Implementation Plan (US-13 — FR-03)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py`, `.html`, settings edits). **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Add `MovieDetailView(DetailView)` at `/movies/<int:pk>/` rendering hero (poster + meta), embedded YouTube trailer (via `youtube-nocookie.com` with minimal sandbox), directors, actors carousel, and upcoming-screenings table. Wire the "Szczegóły" button on the movie list to the new page. Closes US-13. Unblocks US-12 (filtering) — same view will be extended later.

**Architecture:** New `MovieDetailView` sibling of `MovieListView`. New helper `youtube_embed_url(url)` in `apps/cinema/utils.py` parses YouTube URLs (watch/youtu.be/embed shapes, including `m.youtube.com` and extra query args) to a `youtube-nocookie.com` embed URL or `None`. View prefetches genres/actors/directors and computes `trailer_embed_url` + `upcoming_screenings` (future-only, `start_time__gte=now`) in `get_context_data`. Template gates each section by `{% if movie.X.all %}` so orphan movies render cleanly. New `Movie.get_absolute_url()` (deferred from US-10) backs the list page's "Szczegóły" button.

**Tech Stack:** Django 6 `DetailView`, `urllib.parse` + `re` (stdlib) for URL parsing, Bootstrap 5.3.3 Carousel (`data-bs-ride="false"`), pytest-django (`client`, `django_assert_max_num_queries`).

**Branch:** `feat/FR-03-movie-detail` (per backlog US-13).

---

## Pre-flight checklist (read these first)

- [ ] `docs/superpowers/specs/2026-05-21-movie-detail-design.md` — design decisions (Q1, Q2, helper contract, iframe security)
- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-03 — spec source of truth (lines ~216-222)
- [ ] `apps/cinema/models.py` — `Movie` model + `Screening.available_seats_count()` stub (returns `hall.capacity` until US-18)
- [ ] `apps/cinema/views.py` — `MovieListView` pattern to mirror
- [ ] `apps/cinema/urls.py` — current URL config (`/`, `/movies/`)
- [ ] `templates/cinema/movie_list.html` — list template (will need its "Szczegóły" button rewired in Task 7)
- [ ] `tests/cinema/test_movie_list.py` — `assertMaxNumQueries(4)` pattern + emoji placeholder assertions
- [ ] `tests/cinema/factories.py` — `MovieFactory`, `GenreFactory`, `ActorFactory`, `DirectorFactory`, `HallFactory`, `ScreeningFactory` (all from US-10)

---

## File structure

```
apps/cinema/
├── utils.py                                  ★ NEW (Task 2)
├── views.py                                  ✎ + MovieDetailView (Task 3 stub → Task 4 context)
├── urls.py                                   ✎ + path("movies/<int:pk>/", ...) (Task 3)
└── models.py                                 ✎ + Movie.get_absolute_url() (Task 3)

templates/cinema/
├── movie_detail.html                         ★ NEW (Task 3 scaffold → Task 5 hero/trailer → Task 6 cast/screenings)
└── movie_list.html                           ✎ Szczegóły button: drop disabled + add href (Task 7)

tests/cinema/
├── test_youtube_embed_url.py                 ★ NEW (Task 2, ~10 unit tests)
├── test_movie_detail.py                      ★ NEW (Task 3..6 + Task 8, ~18 integration tests)
└── test_movie_list.py                        ✎ swap disabled-button test → href test (Task 7)

.Claude/backlog.md                            ✎ status board (Task 1 + Task 8)
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress (Task 8)
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
git checkout -b feat/FR-03-movie-detail
```

- [ ] **Step 2 (user): commit the spec** (untracked from brainstorming)

```bash
git add docs/superpowers/specs/2026-05-21-movie-detail-design.md
git commit -m "docs(M2): add design spec for US-13 movie detail view"
```

- [ ] **Step 3 (Claude): move US-13 from Ready to In Progress in `.Claude/backlog.md` §7; queue US-12 next**

- [ ] **Step 4 (user): commit plan + backlog**

```bash
git add docs/superpowers/plans/2026-05-21-movie-detail.md .Claude/backlog.md
git commit -m "docs(M2): add implementation plan for US-13 + mark in progress"
```

---

## Task 2: `youtube_embed_url` helper

**Files:**
- Create: `apps/cinema/utils.py`
- Create: `tests/cinema/test_youtube_embed_url.py`

**Why first:** Pure function, no DB. Locks in URL parsing edge cases before any view code consumes it. Quick TDD cycle.

- [ ] **Step 1 (Claude): create `tests/cinema/test_youtube_embed_url.py`**

```python
"""Unit tests for youtube_embed_url helper (US-13 / FR-03)."""

import pytest

from apps.cinema.utils import youtube_embed_url


EMBED = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


class TestYouTubeEmbedUrl:
    def test_none_returns_none(self):
        assert youtube_embed_url(None) is None

    def test_empty_string_returns_none(self):
        assert youtube_embed_url("") is None

    def test_non_youtube_url_returns_none(self):
        assert youtube_embed_url("https://example.com/clip.mp4") is None

    def test_watch_url(self):
        assert youtube_embed_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == EMBED

    def test_short_youtu_be_url(self):
        assert youtube_embed_url("https://youtu.be/dQw4w9WgXcQ") == EMBED

    def test_already_embed_url(self):
        assert youtube_embed_url("https://www.youtube.com/embed/dQw4w9WgXcQ") == EMBED

    def test_mobile_youtube_url(self):
        assert youtube_embed_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ") == EMBED

    def test_watch_url_with_extra_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&feature=share"
        assert youtube_embed_url(url) == EMBED

    def test_watch_url_missing_v_param_returns_none(self):
        assert youtube_embed_url("https://www.youtube.com/watch") is None

    def test_invalid_video_id_length_returns_none(self):
        # YouTube IDs are exactly 11 chars; "tooshort" is 8.
        assert youtube_embed_url("https://www.youtube.com/watch?v=tooshort") is None
```

- [ ] **Step 2 (user): run — expect 10 FAIL** (`apps.cinema.utils` doesn't exist)

```bash
poetry run pytest tests/cinema/test_youtube_embed_url.py -v
```

- [ ] **Step 3 (user): create `apps/cinema/utils.py`** (reference impl):

```python
import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def youtube_embed_url(url: str | None) -> str | None:
    """Return a privacy-respecting youtube-nocookie embed URL, or None if
    the input is missing/not a recognized YouTube URL.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.hostname not in _YOUTUBE_HOSTS:
        return None

    video_id = None
    if parsed.hostname == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = (parse_qs(parsed.query).get("v") or [None])[0]
    elif parsed.path.startswith("/embed/"):
        parts = parsed.path.split("/")
        video_id = parts[2] if len(parts) > 2 else None

    if not video_id or not _VIDEO_ID_RE.match(video_id):
        return None
    return f"https://www.youtube-nocookie.com/embed/{video_id}"
```

- [ ] **Step 4 (user): rerun — expect 10 PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_youtube_embed_url.py apps/cinema/utils.py
git commit -m "feat(FR-03): youtube_embed_url helper with full URL-form coverage"
```

---

## Task 3: URL config + `Movie.get_absolute_url` + view stub

**Files:**
- Create: `tests/cinema/test_movie_detail.py`
- Modify: `apps/cinema/urls.py`
- Modify: `apps/cinema/views.py`
- Modify: `apps/cinema/models.py`
- Create: `templates/cinema/movie_detail.html` (minimal scaffold)

**Why now:** Get routing + 404 + `get_absolute_url` green with a naive view (no context overrides). Task 4 adds context. Task 5+6 expand the template.

- [ ] **Step 1 (Claude): create `tests/cinema/test_movie_detail.py`**

```python
"""Tests for MovieDetailView (US-13 / FR-03)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.cinema.factories import MovieFactory, ScreeningFactory


pytestmark = pytest.mark.django_db


class TestRouting:
    def test_detail_url_returns_200(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200

    def test_missing_pk_returns_404(self, client):
        response = client.get("/movies/99999/")
        assert response.status_code == 404

    def test_movie_detail_reverses_correctly(self):
        movie = MovieFactory()
        assert reverse("cinema:movie_detail", kwargs={"pk": movie.pk}) == f"/movies/{movie.pk}/"

    def test_detail_uses_movie_detail_template(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_detail.html" in template_names

    def test_anonymous_user_gets_200(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200

    def test_authenticated_user_gets_200(self, client, django_user_model):
        movie = MovieFactory()
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200


class TestMovieGetAbsoluteUrl:
    def test_returns_detail_path(self):
        movie = MovieFactory()
        assert movie.get_absolute_url() == f"/movies/{movie.pk}/"
```

- [ ] **Step 2 (user): run — expect 7 FAIL** (no `cinema:movie_detail` URL, no template, no `get_absolute_url`)

```bash
poetry run pytest tests/cinema/test_movie_detail.py -v
```

- [ ] **Step 3 (user): add `MovieDetailView` stub to `apps/cinema/views.py`** (append below `MovieListView`):

```python
from django.views.generic import DetailView, ListView


class MovieDetailView(DetailView):
    model = Movie
    template_name = "cinema/movie_detail.html"
    context_object_name = "movie"
```

- [ ] **Step 4 (user): add URL pattern to `apps/cinema/urls.py`**:

```python
from apps.cinema.views import MovieDetailView, MovieListView

urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
    path("movies/<int:pk>/", MovieDetailView.as_view(), name="movie_detail"),
]
```

- [ ] **Step 5 (user): add `get_absolute_url` to `Movie` in `apps/cinema/models.py`** (inside the `Movie` class):

```python
from django.urls import reverse  # add to imports if not already present

class Movie(models.Model):
    # ... existing fields and Meta ...

    def get_absolute_url(self):
        return reverse("cinema:movie_detail", kwargs={"pk": self.pk})
```

- [ ] **Step 6 (user): create `templates/cinema/movie_detail.html`** (minimal scaffold; expanded in Tasks 5+6):

```html
{% extends "base.html" %}

{% block title %}{{ movie.title }} — KinoMania{% endblock %}

{% block content %}
<article>
  <h1>{{ movie.title }}</h1>
</article>
{% endblock %}
```

- [ ] **Step 7 (user): rerun — expect 7 PASS**

```bash
poetry run pytest tests/cinema/test_movie_detail.py -v
```

- [ ] **Step 8 (user): commit**

```bash
git add tests/cinema/test_movie_detail.py apps/cinema/urls.py apps/cinema/views.py apps/cinema/models.py templates/cinema/movie_detail.html
git commit -m "feat(FR-03): Movie.get_absolute_url + URL config for detail view"
```

---

## Task 4: View `get_context_data` + queryset prefetches

**Files:**
- Modify: `tests/cinema/test_movie_detail.py`
- Modify: `apps/cinema/views.py`

**Why now:** Lock in the context shape (`trailer_embed_url`, `upcoming_screenings`) before the template starts consuming them. Tests inspect `response.context` directly.

- [ ] **Step 1 (Claude): append `TestContext` to `tests/cinema/test_movie_detail.py`**

```python
class TestContext:
    def test_trailer_embed_url_for_youtube(self, client):
        movie = MovieFactory(trailer_url="https://youtu.be/dQw4w9WgXcQ")
        response = client.get(f"/movies/{movie.pk}/")
        assert (
            response.context["trailer_embed_url"]
            == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
        )

    def test_trailer_embed_url_is_none_for_non_youtube(self, client):
        movie = MovieFactory(trailer_url="https://example.com/clip.mp4")
        response = client.get(f"/movies/{movie.pk}/")
        assert response.context["trailer_embed_url"] is None

    def test_trailer_embed_url_is_none_for_blank_trailer(self, client):
        movie = MovieFactory(trailer_url="")
        response = client.get(f"/movies/{movie.pk}/")
        assert response.context["trailer_embed_url"] is None

    def test_upcoming_screenings_includes_future(self, client):
        movie = MovieFactory()
        future = ScreeningFactory(
            movie=movie, start_time=timezone.now() + timedelta(days=1)
        )
        response = client.get(f"/movies/{movie.pk}/")
        assert future in list(response.context["upcoming_screenings"])

    def test_upcoming_screenings_excludes_past(self, client):
        movie = MovieFactory()
        past = ScreeningFactory(
            movie=movie, start_time=timezone.now() - timedelta(days=1)
        )
        response = client.get(f"/movies/{movie.pk}/")
        assert past not in list(response.context["upcoming_screenings"])

    def test_upcoming_screenings_sorted_ascending(self, client):
        movie = MovieFactory()
        now = timezone.now()
        s_late = ScreeningFactory(movie=movie, start_time=now + timedelta(days=3))
        s_early = ScreeningFactory(movie=movie, start_time=now + timedelta(days=1))
        s_mid = ScreeningFactory(movie=movie, start_time=now + timedelta(days=2))

        response = client.get(f"/movies/{movie.pk}/")

        listed = list(response.context["upcoming_screenings"])
        assert listed == [s_early, s_mid, s_late]

    def test_upcoming_screenings_empty_for_orphan(self, client):
        movie = MovieFactory()  # no screenings
        response = client.get(f"/movies/{movie.pk}/")
        assert list(response.context["upcoming_screenings"]) == []
```

- [ ] **Step 2 (user): run — expect 7 FAIL** (`KeyError` on `trailer_embed_url` / `upcoming_screenings`)

```bash
poetry run pytest tests/cinema/test_movie_detail.py::TestContext -v
```

- [ ] **Step 3 (user): expand `MovieDetailView` in `apps/cinema/views.py`** (reference impl):

```python
from django.db.models import Min, Q
from django.utils import timezone
from django.views.generic import DetailView, ListView

from apps.cinema.models import Movie
from apps.cinema.utils import youtube_embed_url


class MovieDetailView(DetailView):
    model = Movie
    template_name = "cinema/movie_detail.html"
    context_object_name = "movie"

    def get_queryset(self):
        return Movie.objects.prefetch_related("genres", "actors", "directors")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trailer_embed_url"] = youtube_embed_url(self.object.trailer_url)
        ctx["upcoming_screenings"] = (
            self.object.screenings
            .filter(start_time__gte=timezone.now())
            .select_related("hall")
            .order_by("start_time")
        )
        return ctx
```

- [ ] **Step 4 (user): rerun — expect 7 PASS**

```bash
poetry run pytest tests/cinema/test_movie_detail.py::TestContext -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_detail.py apps/cinema/views.py
git commit -m "feat(FR-03): MovieDetailView context (trailer + upcoming screenings)"
```

---

## Task 5: Template — hero + trailer

**Files:**
- Modify: `tests/cinema/test_movie_detail.py`
- Modify: `templates/cinema/movie_detail.html`

- [ ] **Step 1 (Claude): append imports + `TestHeroAndTrailer` to `tests/cinema/test_movie_detail.py`**

Add imports at top (under existing imports):

```python
from django.core.files.uploadedfile import SimpleUploadedFile

from tests.cinema.factories import GenreFactory
```

Append:

```python
# Smallest valid PNG (1x1) — reused from tests/cinema/test_movie_list.py
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc"
    b"\xff\xff?\x03\x00\x06\x00\x02\x00\x01\xa5\xc8\x7f\xb1\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)


class TestHeroAndTrailer:
    def test_hero_shows_title(self, client):
        movie = MovieFactory(title="Unique Hero Title")
        response = client.get(f"/movies/{movie.pk}/")
        assert "Unique Hero Title" in response.content.decode()

    def test_hero_shows_release_date_and_duration(self, client):
        movie = MovieFactory(duration_minutes=137)
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "137" in content
        assert "min" in content
        assert movie.release_date.strftime("%d.%m.%Y") in content

    def test_hero_shows_description(self, client):
        movie = MovieFactory(description="A peculiar plot about cinema.")
        response = client.get(f"/movies/{movie.pk}/")
        assert "A peculiar plot about cinema." in response.content.decode()

    def test_hero_shows_genre_badges(self, client):
        movie = MovieFactory()
        movie.genres.add(GenreFactory(name="Sci-Fi"), GenreFactory(name="Drama"))
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Sci-Fi" in content
        assert "Drama" in content
        assert content.count('class="badge bg-secondary"') >= 2

    def test_hero_uses_emoji_placeholder_when_poster_blank(self, client):
        movie = MovieFactory(poster="")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "🎬" in content
        assert 'src=""' not in content

    def test_hero_uses_real_poster_when_set(self, client):
        movie = MovieFactory()
        movie.poster = SimpleUploadedFile("p.png", PNG_1X1, content_type="image/png")
        movie.save()
        response = client.get(f"/movies/{movie.pk}/")
        assert movie.poster.url in response.content.decode()

    def test_trailer_iframe_for_youtube_url(self, client):
        movie = MovieFactory(trailer_url="https://youtu.be/dQw4w9WgXcQ")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "<iframe" in content
        assert "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" in content
        assert 'sandbox="allow-scripts allow-same-origin allow-presentation"' in content

    def test_trailer_fallback_link_for_non_youtube(self, client):
        movie = MovieFactory(trailer_url="https://example.com/clip.mp4")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "<iframe" not in content
        assert 'href="https://example.com/clip.mp4"' in content
        assert 'rel="noopener noreferrer"' in content

    def test_trailer_section_hidden_when_url_blank(self, client):
        movie = MovieFactory(trailer_url="")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        # No iframe, no "Zwiastun" heading.
        assert "<iframe" not in content
        assert "Zwiastun" not in content
```

- [ ] **Step 2 (user): run — expect 9 FAIL** (template is still scaffold)

```bash
poetry run pytest tests/cinema/test_movie_detail.py::TestHeroAndTrailer -v
```

- [ ] **Step 3 (user): expand `templates/cinema/movie_detail.html`** with hero + trailer sections:

```html
{% extends "base.html" %}

{% block title %}{{ movie.title }} — KinoMania{% endblock %}

{% block content %}
<article>
  {# Hero — poster + meta #}
  <div class="row g-4 mb-5">
    <div class="col-md-4">
      {% if movie.poster %}
        <img src="{{ movie.poster.url }}" alt="{{ movie.title }}"
             class="img-fluid rounded shadow-sm"
             style="aspect-ratio: 2/3; object-fit: cover; width: 100%;">
      {% else %}
        <div class="bg-light rounded d-flex align-items-center justify-content-center"
             style="aspect-ratio: 2/3; font-size: 5rem;" aria-hidden="true">🎬</div>
      {% endif %}
    </div>
    <div class="col-md-8">
      <h1 class="mb-3">{{ movie.title }}</h1>
      <p class="mb-3">
        {% for genre in movie.genres.all %}
          <span class="badge bg-secondary">{{ genre.name }}</span>
        {% endfor %}
      </p>
      <dl class="row small text-muted mb-3">
        <dt class="col-sm-4">Premiera</dt>
        <dd class="col-sm-8">{{ movie.release_date|date:"d.m.Y" }}</dd>
        <dt class="col-sm-4">Czas trwania</dt>
        <dd class="col-sm-8">{{ movie.duration_minutes }} min</dd>
      </dl>
      <p>{{ movie.description|linebreaksbr }}</p>
    </div>
  </div>

  {# Trailer — only if we have a URL #}
  {% if trailer_embed_url %}
    <section class="mb-5">
      <h2 class="h4 mb-3">Zwiastun</h2>
      <iframe src="{{ trailer_embed_url }}"
              title="Zwiastun: {{ movie.title }}"
              width="100%" style="aspect-ratio: 16/9;"
              frameborder="0"
              allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              referrerpolicy="strict-origin-when-cross-origin"
              sandbox="allow-scripts allow-same-origin allow-presentation"
              allowfullscreen></iframe>
    </section>
  {% elif movie.trailer_url %}
    <section class="mb-5">
      <h2 class="h4 mb-3">Zwiastun</h2>
      <a href="{{ movie.trailer_url }}" class="btn btn-outline-secondary"
         target="_blank" rel="noopener noreferrer">Zobacz zwiastun (link zewnętrzny)</a>
    </section>
  {% endif %}
</article>
{% endblock %}
```

- [ ] **Step 4 (user): rerun — expect 9 PASS**

```bash
poetry run pytest tests/cinema/test_movie_detail.py::TestHeroAndTrailer -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_detail.py templates/cinema/movie_detail.html
git commit -m "feat(FR-03): hero + trailer section in movie_detail.html"
```

---

## Task 6: Template — directors + actors carousel + screenings table

**Files:**
- Modify: `tests/cinema/test_movie_detail.py`
- Modify: `templates/cinema/movie_detail.html`

- [ ] **Step 1 (Claude): append imports + 3 test classes**

Add imports (under existing):

```python
from decimal import Decimal

from tests.cinema.factories import ActorFactory, DirectorFactory, HallFactory
```

Append:

```python
class TestDirectors:
    def test_directors_section_shows_names(self, client):
        movie = MovieFactory()
        d1 = DirectorFactory(full_name="Director One")
        d2 = DirectorFactory(full_name="Director Two")
        movie.directors.add(d1, d2)
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Director One" in content
        assert "Director Two" in content

    def test_directors_section_hidden_when_empty(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert "Reżyseria" not in response.content.decode()

    def test_director_photo_placeholder_when_blank(self, client):
        movie = MovieFactory()
        movie.directors.add(DirectorFactory(full_name="No-Photo Director", photo=""))
        response = client.get(f"/movies/{movie.pk}/")
        assert "👤" in response.content.decode()


class TestActorsCarousel:
    def test_actors_carousel_renders_data_attribute(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(), ActorFactory())
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert 'data-bs-ride="false"' in content

    def test_actors_carousel_has_one_item_per_actor(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(), ActorFactory(), ActorFactory())
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert content.count('class="carousel-item') == 3

    def test_actors_carousel_has_exactly_one_active_item(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(), ActorFactory(), ActorFactory())
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        # Bootstrap requires exactly one `.active` slide on load.
        assert content.count("carousel-item active") == 1

    def test_actors_section_hidden_when_empty(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert "Obsada" not in response.content.decode()

    def test_actor_photo_placeholder_when_blank(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(full_name="No-Photo Actor", photo=""))
        response = client.get(f"/movies/{movie.pk}/")
        assert "👤" in response.content.decode()


class TestUpcomingScreenings:
    def test_screening_row_shows_hall_price_seats(self, client):
        hall = HallFactory(name="Sala A", capacity=100)
        movie = MovieFactory()
        ScreeningFactory(
            movie=movie, hall=hall,
            start_time=timezone.now() + timedelta(days=1),
            price=Decimal("42.50"),
        )
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Sala A" in content
        assert "42.50" in content
        assert "zł" in content
        # available_seats_count stub returns hall.capacity (100) until US-18.
        assert "100" in content

    def test_screening_row_shows_disabled_reserve_button(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Zarezerwuj" in content
        # US-20 will drop the disabled class.
        assert "disabled" in content

    def test_screening_empty_state_when_no_future(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Brak zaplanowanych seansów" in content
        assert "<table" not in content

    def test_orphan_movie_renders_with_only_hero_and_empty_alert(self, client):
        movie = MovieFactory(trailer_url="")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert response.status_code == 200
        assert movie.title in content
        assert "Brak zaplanowanych seansów" in content
        # No optional sections.
        assert "Reżyseria" not in content
        assert "Obsada" not in content
        assert "Zwiastun" not in content
```

- [ ] **Step 2 (user): run — expect 12 FAIL**

```bash
poetry run pytest tests/cinema/test_movie_detail.py -v -k "TestDirectors or TestActorsCarousel or TestUpcomingScreenings"
```

- [ ] **Step 3 (user): expand `templates/cinema/movie_detail.html`** — append three sections after the trailer block, before the closing `</article>`:

```html
  {# Directors #}
  {% if movie.directors.all %}
    <section class="mb-5">
      <h2 class="h4 mb-3">Reżyseria</h2>
      <div class="row row-cols-2 row-cols-md-4 g-3">
        {% for director in movie.directors.all %}
          <div class="col">
            <div class="text-center">
              {% if director.photo %}
                <img src="{{ director.photo.url }}" alt="{{ director.full_name }}"
                     class="rounded-circle mb-2"
                     style="width:80px; height:80px; object-fit:cover;">
              {% else %}
                <div class="rounded-circle bg-light d-flex align-items-center justify-content-center mb-2 mx-auto"
                     style="width:80px; height:80px; font-size:2rem;" aria-hidden="true">👤</div>
              {% endif %}
              <div class="small">{{ director.full_name }}</div>
            </div>
          </div>
        {% endfor %}
      </div>
    </section>
  {% endif %}

  {# Actors — Bootstrap Carousel, one actor per slide #}
  {% if movie.actors.all %}
    <section class="mb-5">
      <h2 class="h4 mb-3">Obsada</h2>
      <div id="actorsCarousel" class="carousel slide" data-bs-ride="false">
        <div class="carousel-inner">
          {% for actor in movie.actors.all %}
            <div class="carousel-item {% if forloop.first %}active{% endif %}">
              <div class="text-center py-3">
                {% if actor.photo %}
                  <img src="{{ actor.photo.url }}" alt="{{ actor.full_name }}"
                       class="rounded-circle mb-2"
                       style="width:140px; height:140px; object-fit:cover;">
                {% else %}
                  <div class="rounded-circle bg-light d-flex align-items-center justify-content-center mb-2 mx-auto"
                       style="width:140px; height:140px; font-size:3rem;" aria-hidden="true">👤</div>
                {% endif %}
                <div>{{ actor.full_name }}</div>
              </div>
            </div>
          {% endfor %}
        </div>
        <button class="carousel-control-prev" type="button"
                data-bs-target="#actorsCarousel" data-bs-slide="prev">
          <span class="carousel-control-prev-icon" aria-hidden="true"></span>
          <span class="visually-hidden">Poprzedni</span>
        </button>
        <button class="carousel-control-next" type="button"
                data-bs-target="#actorsCarousel" data-bs-slide="next">
          <span class="carousel-control-next-icon" aria-hidden="true"></span>
          <span class="visually-hidden">Następny</span>
        </button>
      </div>
    </section>
  {% endif %}

  {# Upcoming screenings #}
  <section class="mb-5">
    <h2 class="h4 mb-3">Najbliższe seanse</h2>
    {% if upcoming_screenings %}
      <div class="table-responsive">
        <table class="table align-middle">
          <thead>
            <tr>
              <th>Data i godzina</th>
              <th>Sala</th>
              <th>Cena</th>
              <th>Dostępne miejsca</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {% for s in upcoming_screenings %}
              <tr>
                <td>{{ s.start_time|date:"d.m.Y H:i" }}</td>
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
    {% else %}
      <div class="alert alert-info">
        Brak zaplanowanych seansów dla tego filmu.
      </div>
    {% endif %}
  </section>
```

- [ ] **Step 4 (user): rerun — expect 12 PASS** (plus all 23 previous still green)

```bash
poetry run pytest tests/cinema/test_movie_detail.py -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_detail.py templates/cinema/movie_detail.html
git commit -m "feat(FR-03): cast (directors + actors carousel) + screenings table"
```

---

## Task 7: Wire "Szczegóły" button on movie list

**Files:**
- Modify: `tests/cinema/test_movie_list.py`
- Modify: `templates/cinema/movie_list.html`

**Why now:** All detail-page plumbing is in place. Drop the "disabled" stub on the list card and link to the real detail page.

- [ ] **Step 1 (Claude): replace the existing `test_card_shows_disabled_details_button`** in `tests/cinema/test_movie_list.py` with an active-link variant. Find the existing method (in `TestCardRendering`) and swap it for:

```python
    def test_card_links_details_button_to_movie_detail(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert "Szczegóły" in content
        assert f'href="/movies/{movie.pk}/"' in content
        # The disabled stub from US-11 is gone now.
        assert "btn-primary btn-sm mt-auto disabled" not in content
```

- [ ] **Step 2 (user): run — expect 1 FAIL** (current template still has `disabled` + `href="#"`)

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestCardRendering::test_card_links_details_button_to_movie_detail -v
```

- [ ] **Step 3 (user): update `templates/cinema/movie_list.html`** — find the "Szczegóły" anchor and change it from:

```html
<a href="#" class="btn btn-primary btn-sm mt-auto disabled">Szczegóły</a>
```

to:

```html
<a href="{{ movie.get_absolute_url }}" class="btn btn-primary btn-sm mt-auto">Szczegóły</a>
```

- [ ] **Step 4 (user): rerun + full movie_list suite sanity:**

```bash
poetry run pytest tests/cinema/test_movie_list.py -v
```

Expected: all green (the test you just rewrote passes; rest of TestCardRendering/TestPagination/TestEmptyState/TestQueryBudget unchanged).

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_movie_list.py templates/cinema/movie_list.html
git commit -m "feat(FR-03): wire Szczegóły button on movie list to detail page"
```

---

## Task 8: N+1 budget + coverage + smoke + PR

**Files:**
- Modify: `tests/cinema/test_movie_detail.py`
- Modify: `.Claude/backlog.md`

- [ ] **Step 1 (Claude): append `TestQueryBudget` to `tests/cinema/test_movie_detail.py`**

```python
class TestQueryBudget:
    def test_full_page_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Populated detail page: movie + 3 M2M prefetches + screenings + hall select_related.
        Budget cap 6 absorbs harness overhead; regression triggers when prefetch_related drops
        a relation or someone adds an unprefetched iterator in the template."""
        movie = MovieFactory()
        movie.genres.add(GenreFactory(), GenreFactory())
        movie.actors.add(ActorFactory(), ActorFactory(), ActorFactory())
        movie.directors.add(DirectorFactory(), DirectorFactory())
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=2))

        with django_assert_max_num_queries(6):
            client.get(f"/movies/{movie.pk}/")
```

- [ ] **Step 2 (user): run — likely PASS**

```bash
poetry run pytest tests/cinema/test_movie_detail.py::TestQueryBudget -v
```

If FAIL with count > 6, inspect printed queries — common culprits: missing `prefetch_related` on `actors`/`directors`/`genres`, or template iterating `s.hall.<other_field>` without `select_related`. Bump cap to 7 only if confident the extra query is harness-injected (e.g., session/auth).

- [ ] **Step 3 (user): full suite + coverage**

```bash
poetry run pytest --cov=apps --cov-report=term-missing
```

Expected: all tests pass; `apps/cinema/utils.py` 100%; `apps/cinema/views.py` 100%; `apps/cinema/models.py` ≥99% (only the `__str__` paths uncovered if any).

- [ ] **Step 4 (user): manual smoke**

```bash
poetry run python manage.py seed_db --flush
poetry run python manage.py runserver
```

Visit `http://127.0.0.1:8000/`. Pick any movie. Click "Szczegóły" → land on `/movies/<pk>/`. Confirm:
- Hero renders with 🎬 placeholder (seeded posters are blank)
- Genre badges visible
- No "Zwiastun" section (seed sets `trailer_url=""`)
- Directors + actors sections render with 👤 placeholders
- Actors carousel arrows step through slides
- Screenings table populated (each seeded movie has random screenings)
- Try a movie with no future screenings (rare with seed but `seed_db --flush --screenings=0` reproduces) → "Brak zaplanowanych seansów" alert
- 404: visit `/movies/99999/`

- [ ] **Step 5 (Claude): update `.Claude/backlog.md` §7** — US-13 → Done; queue **US-12** (filtering + search) next per `.Claude/m2_planning.md` ordering (US-13 → US-12).

- [ ] **Step 6 (user): commit backlog update**

```bash
git add .Claude/backlog.md
git commit -m "docs(M2): mark US-13 done, queue US-12 next"
```

- [ ] **Step 7 (user): commit the budget test (if not already with Task 6):**

```bash
git add tests/cinema/test_movie_detail.py
git commit -m "test(FR-03): N+1 query budget regression for detail page"
```

(Or squash into the backlog commit — your call.)

- [ ] **Step 8 (user): push + open PR**

```bash
git push -u origin feat/FR-03-movie-detail
```

PR body:

```
Title: feat(FR-03): movie detail view + embedded trailer — US-13

## Summary
- New `MovieDetailView(DetailView)` at `/movies/<int:pk>/` (`cinema:movie_detail`)
- New `youtube_embed_url` helper in `apps/cinema/utils.py` — supports watch/youtu.be/embed shapes, `m.youtube.com`, query args. Returns `youtube-nocookie.com` embed URL or `None`.
- Iframe security: `sandbox="allow-scripts allow-same-origin allow-presentation"`, `referrerpolicy="strict-origin-when-cross-origin"`, no popups/forms/top-navigation.
- Template sections: hero (poster+meta+description), conditional trailer (iframe for YouTube, fallback link otherwise), conditional directors grid, conditional actors carousel (Bootstrap, `data-bs-ride="false"`), screenings table with empty state.
- `Movie.get_absolute_url()` (deferred from US-10) — backs the rewired "Szczegóły" button on the movie list.
- 👤 emoji placeholder for blank actor/director photos (mirrors 🎬 pattern from US-11).
- ~32 new tests (10 helper unit + 22 view/template integration) + N+1 budget guard.

## Closes
- US-13 (FR-03)

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-05-21-movie-detail-design.md`
- Plan: `docs/superpowers/plans/2026-05-21-movie-detail.md`
- FR spec: `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-03

## Out of scope (deferred)
- Booking flow (clicking "Zarezerwuj") → US-20 (M3, FR-07) drops `disabled` + adds href, mirroring the Szczegóły handoff here
- Real `Screening.available_seats_count` (Booking aggregation) → US-18 (M3, FR-3.8); stub still returns `hall.capacity`
- Filtering / search on the list view → US-12 (FR-02)
- Daily screenings list → US-14 (FR-04)
- Performance pass on prefetches → US-17 (NFR)

## Test plan
- [ ] CI green (lint, mypy, tests, ≥80% coverage)
- [ ] Manual smoke: `seed_db --flush`, click "Szczegóły" on any movie card, confirm all sections render
- [ ] Direct URL `/movies/<pk>/` works for orphan movies (no screenings, no cast)
- [ ] 404 on missing pk
```

- [ ] **Step 9 (after merge — separate session): update `memory/project_kinomania_bootstrap.md`** — M2 progress: 5/8 done; next is US-12.

---

## Self-review summary

- ✅ FR-03 acceptance criteria: hero with poster/title/desc/release_date/duration/genres (Task 5), directors with photos (Task 6), actors carousel with photos (Task 6), YouTube iframe trailer (Task 5), upcoming screenings list with hall/price/seats/button (Task 6), empty-state for no screenings (Task 6).
- ✅ Spec §2 architecture (view + URL + `get_absolute_url`): Tasks 3 + 4.
- ✅ Spec §3 helper (`youtube_embed_url`): Task 2 with all 10 URL-form cases.
- ✅ Spec §4 template (full sectioned layout): Tasks 5 + 6.
- ✅ Spec §5 tests (all categories): distributed Tasks 2-8.
- ✅ Spec §6 file changes: every file accounted for.
- ✅ Spec §7 commit plan: matches task structure (7 feature/test commits + 2 docs).
- ✅ "Szczegóły" wiring (Task 7) and the test swap explicitly handle the US-11 handoff.
- ✅ N+1 regression test (Task 8) caps query budget at 6.
- ✅ Orphan movie + 404 + anon/auth access all covered.
- ✅ No placeholders; every step has runnable code/commands.
- ✅ Reference implementations are concrete, paste-ready for the user.
