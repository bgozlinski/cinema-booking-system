# Cinema Admin Implementation Plan (US-15 — FR-11 parts)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Subagent-driven execution is NOT compatible with this workflow — see role-division note below. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific role division (CRITICAL):** This repo has an explicit rule (see `memory/feedback_role_division.md`) — **user writes ALL application code** (`.py`, `.html`, settings edits). **Claude writes ALL tests** (`test_*.py`, `conftest.py`, `factories.py`). User runs ALL `git`/`gh` commands. App code in this plan is a **reference implementation** for the user to study/adapt while typing — not for paste. Test code is **complete and ready to paste** by Claude.

**Goal:** Implement 5 cinema-side `ModelAdmin` classes (`Genre`, `Actor`, `Director`, `Hall`, `Movie`) in `apps/cinema/admin.py`, with custom display helpers (`poster_thumbnail`, `photo_thumbnail`, `screenings_count`, `movies_count`, `genres_list`). Closes US-15. Unblocks manual seeding/QA for US-11..US-14 (catalog views).

**Architecture:** Single `apps/cinema/admin.py` registers 5 `ModelAdmin` classes via `@admin.register(...)`. Custom display methods return either an empty dash (`"—"`) or a `format_html(...)` `<img>` snippet for thumbnails; count methods use related-manager `.count()`. No inlines and no `ScreeningAdmin` in US-15 — `ScreeningAdmin` ships in **US-28** (FR-11 booking-side admin) together with `BookingAdmin` and the inline plumbing. The FR-11 spec lists `inlines = [ScreeningInline]` for MovieAdmin/HallAdmin, but `ScreeningInline` is deferred to US-28 to keep US-15 strictly mechanical and avoid premature coupling to booking admin work.

**Tech Stack:** Django 6 admin (`admin.ModelAdmin`, `@admin.register`, `format_html`), pytest-django, factory_boy (existing factories in `tests/cinema/factories.py`).

**Branch:** `feat/FR-11-cinema-admin` (per backlog US-15).

---

## Pre-flight checklist (read these first)

- [ ] `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-11 — admin spec source of truth (lines ~299-340)
- [ ] `.Claude/m2_planning.md` — milestone kickoff (US-15 is "plan directly, mechanical")
- [ ] `.Claude/commit_convention.md` — Conventional Commits with FR-11 scope
- [ ] `apps/accounts/admin.py` — style mirror (`@admin.register`, `list_display` ordering, readonly_fields convention)
- [ ] `apps/cinema/models.py` — what gets registered, related_names (`Movie.screenings`, `Actor.movies`, `Director.movies`, `Genre.movies`); **Hall has NO related_name on `Screening.hall`** → use `screening_set` (default reverse accessor)
- [ ] `tests/cinema/factories.py` — existing factories to reuse

---

## Design notes (US-15 scope, mechanical)

### What gets registered

| ModelAdmin | `list_display` | `search_fields` | `list_filter` | Custom display |
|---|---|---|---|---|
| `GenreAdmin` | `("name", "movies_count")` | `("name",)` | — | `movies_count` |
| `HallAdmin` | `("name", "capacity", "screenings_count")` | `("name",)` | — | `screenings_count` |
| `ActorAdmin` | `("full_name", "photo_thumbnail", "movies_count")` | `("full_name",)` | — | `photo_thumbnail`, `movies_count` |
| `DirectorAdmin` | `("full_name", "photo_thumbnail", "movies_count")` | `("full_name",)` | — | `photo_thumbnail`, `movies_count` |
| `MovieAdmin` | `("title", "release_date", "poster_thumbnail", "screenings_count", "genres_list")` | `("title", "description", "directors__full_name")` | `("genres", "release_date")` | `poster_thumbnail`, `screenings_count`, `genres_list` |

`MovieAdmin` additionally sets:
- `filter_horizontal = ("genres", "actors", "directors")` (matrix M2M widget)
- `date_hierarchy = "release_date"` (drill-down by year/month/day)

### Custom display helper contract

| Method | Returns when empty | Returns when populated |
|---|---|---|
| `poster_thumbnail(obj)` (Movie) | `"—"` | `format_html('<img src="{}" style="height:60px;" />', obj.poster.url)` |
| `photo_thumbnail(obj)` (Actor/Director) | `"—"` | `format_html('<img src="{}" style="height:60px;" />', obj.photo.url)` |
| `movies_count(obj)` (Genre/Actor/Director) | `0` | `obj.movies.count()` |
| `screenings_count(obj)` (Movie) | `0` | `obj.screenings.count()` |
| `screenings_count(obj)` (Hall) | `0` | `obj.screening_set.count()` |
| `genres_list(obj)` (Movie) | `"—"` | `", ".join(g.name for g in obj.genres.all())` |

Each method has a `short_description` set via the `@admin.display(description=...)` decorator (Django 4.0+ idiom).

### Out of scope (deferred to US-28)

- `ScreeningAdmin` (standalone `/admin/cinema/screening/`)
- `BookingAdmin`
- `ScreeningInline` / `BookingInline` on Movie/Hall
- Colour badges for `available_seats_display` / `booked_seats_display`

### Out of scope (already done elsewhere)

- `UserAdmin` — exists in `apps/accounts/admin.py` (M1, US-04+)

---

## File structure (what we'll create/modify)

```
apps/cinema/
└── admin.py                                  ★ NEW — 5 ModelAdmin classes

tests/cinema/
└── test_admin.py                             ★ NEW — registration + display method tests

.Claude/backlog.md                            ✎ status board (Task 1 + Task 8)
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress (Task 8)
```

No new migrations. No new dependencies. No settings edits.

---

## Task 1: Branch + backlog DoR

**Files:**
- Modify: `.Claude/backlog.md`

**Why first:** Mirror US-10 pattern. Get spec/plan committed before any code so the PR has a clean docs-first commit.

- [ ] **Step 1 (user): create + switch to feature branch**

```bash
git checkout main
git pull
git checkout -b feat/FR-11-cinema-admin
```

- [ ] **Step 2: update backlog status board — move US-15 from Ready to In Progress**

Find `.Claude/backlog.md` §7 (status board). Move the `US-15 (cinema admin)` row from **Ready (DoR ✅)** to **In Progress** with link to this plan and the spec section pointer (`.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-11).

- [ ] **Step 3 (user): commit the plan + backlog update**

```bash
git add docs/superpowers/plans/2026-05-20-cinema-admin.md .Claude/backlog.md
git commit -m "docs(M2): add implementation plan for US-15 + mark in progress"
```

---

## Task 2: Test scaffold — module import + registration

**Files:**
- Create: `tests/cinema/test_admin.py`

**Why second:** Establish the test module and lock in "admin.py exists + all 5 models registered" before touching any individual ModelAdmin. This is the smoke test that proves admin discovery works.

- [ ] **Step 1 (Claude): write `tests/cinema/test_admin.py` — registration tests only**

```python
"""Tests for cinema admin registration and ModelAdmin classes."""

import pytest
from django.contrib import admin

from apps.cinema.models import Actor, Director, Genre, Hall, Movie


pytestmark = pytest.mark.django_db


class TestAdminRegistration:
    """All cinema models must be registered with the admin site (US-15 / FR-11)."""

    def test_genre_is_registered(self):
        assert admin.site.is_registered(Genre)

    def test_hall_is_registered(self):
        assert admin.site.is_registered(Hall)

    def test_actor_is_registered(self):
        assert admin.site.is_registered(Actor)

    def test_director_is_registered(self):
        assert admin.site.is_registered(Director)

    def test_movie_is_registered(self):
        assert admin.site.is_registered(Movie)
```

- [ ] **Step 2 (user): run test — expect 5 FAIL**

```bash
poetry run pytest tests/cinema/test_admin.py -v
```

Expected: 5 failures with `AssertionError: assert False` (models not yet registered — `apps/cinema/admin.py` doesn't exist or is empty).

- [ ] **Step 3 (user): create `apps/cinema/admin.py` with bare-minimum registration**

```python
# apps/cinema/admin.py — reference implementation for Task 2.
# Each subsequent task expands one ModelAdmin with attributes + custom display methods.
from django.contrib import admin

from apps.cinema.models import Actor, Director, Genre, Hall, Movie


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    pass


@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    pass


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    pass


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    pass


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    pass
```

- [ ] **Step 4 (user): rerun tests — expect 5 PASS**

```bash
poetry run pytest tests/cinema/test_admin.py -v
```

Expected: 5 passed.

- [ ] **Step 5 (user): commit the scaffold**

```bash
git add tests/cinema/test_admin.py apps/cinema/admin.py
git commit -m "feat(FR-11): register cinema models in Django admin (scaffold)"
```

---

## Task 3: GenreAdmin — `movies_count`

**Files:**
- Modify: `tests/cinema/test_admin.py`
- Modify: `apps/cinema/admin.py`

**Scope:** simplest admin first (no images). Locks in the `*_count` display-method pattern that ActorAdmin/DirectorAdmin/HallAdmin reuse.

- [ ] **Step 1 (Claude): extend `tests/cinema/test_admin.py` with `TestGenreAdmin`**

Append below `TestAdminRegistration`:

```python
from tests.cinema.factories import GenreFactory, MovieFactory


class TestGenreAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Genre]
        assert ma.list_display == ("name", "movies_count")

    def test_search_fields(self):
        ma = admin.site._registry[Genre]
        assert ma.search_fields == ("name",)

    def test_movies_count_zero_when_no_movies(self):
        genre = GenreFactory()
        ma = admin.site._registry[Genre]
        assert ma.movies_count(genre) == 0

    def test_movies_count_returns_related_movie_count(self):
        genre = GenreFactory()
        m1 = MovieFactory()
        m2 = MovieFactory()
        m1.genres.add(genre)
        m2.genres.add(genre)
        ma = admin.site._registry[Genre]
        assert ma.movies_count(genre) == 2

    def test_movies_count_has_short_description(self):
        ma = admin.site._registry[Genre]
        assert ma.movies_count.short_description == "movies"
```

- [ ] **Step 2 (user): run new tests — expect 5 FAIL**

```bash
poetry run pytest tests/cinema/test_admin.py::TestGenreAdmin -v
```

Expected: failures on missing `list_display`, missing `search_fields`, `AttributeError: 'GenreAdmin' object has no attribute 'movies_count'`.

- [ ] **Step 3 (user): expand `GenreAdmin` in `apps/cinema/admin.py`**

Reference implementation:

```python
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "movies_count")
    search_fields = ("name",)

    @admin.display(description="movies")
    def movies_count(self, obj):
        return obj.movies.count()
```

- [ ] **Step 4 (user): rerun — expect 5 PASS**

```bash
poetry run pytest tests/cinema/test_admin.py::TestGenreAdmin -v
```

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_admin.py apps/cinema/admin.py
git commit -m "feat(FR-11): expand GenreAdmin with movies_count display"
```

---

## Task 4: HallAdmin — `screenings_count` (default reverse accessor)

**Files:**
- Modify: `tests/cinema/test_admin.py`
- Modify: `apps/cinema/admin.py`

**Why now:** Locks in the `screenings_count` pattern. **Important:** `Screening.hall` has no `related_name`, so the reverse accessor is `screening_set` (Django default). MovieAdmin's `screenings_count` later uses `movie.screenings` because `Screening.movie` has `related_name="screenings"`.

- [ ] **Step 1 (Claude): extend `tests/cinema/test_admin.py` with `TestHallAdmin`**

Append:

```python
from tests.cinema.factories import HallFactory, ScreeningFactory


class TestHallAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Hall]
        assert ma.list_display == ("name", "capacity", "screenings_count")

    def test_search_fields(self):
        ma = admin.site._registry[Hall]
        assert ma.search_fields == ("name",)

    def test_screenings_count_zero_when_no_screenings(self):
        hall = HallFactory()
        ma = admin.site._registry[Hall]
        assert ma.screenings_count(hall) == 0

    def test_screenings_count_returns_related_screening_count(self):
        hall = HallFactory()
        ScreeningFactory.create_batch(3, hall=hall)
        ma = admin.site._registry[Hall]
        assert ma.screenings_count(hall) == 3

    def test_screenings_count_has_short_description(self):
        ma = admin.site._registry[Hall]
        assert ma.screenings_count.short_description == "screenings"
```

- [ ] **Step 2 (user): run — expect FAIL**

```bash
poetry run pytest tests/cinema/test_admin.py::TestHallAdmin -v
```

- [ ] **Step 3 (user): expand `HallAdmin`**

Reference implementation:

```python
@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "screenings_count")
    search_fields = ("name",)

    @admin.display(description="screenings")
    def screenings_count(self, obj):
        return obj.screening_set.count()
```

- [ ] **Step 4 (user): rerun — expect PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_admin.py apps/cinema/admin.py
git commit -m "feat(FR-11): expand HallAdmin with screenings_count display"
```

---

## Task 5: ActorAdmin — `photo_thumbnail` + `movies_count`

**Files:**
- Modify: `tests/cinema/test_admin.py`
- Modify: `apps/cinema/admin.py`

**Why now:** Introduces the thumbnail pattern reused by DirectorAdmin + MovieAdmin.

- [ ] **Step 1 (Claude): extend `tests/cinema/test_admin.py` with `TestActorAdmin`**

Append:

```python
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.safestring import SafeString

from tests.cinema.factories import ActorFactory


# Smallest valid PNG (1x1 transparent) — paste-ready bytes for ImageField tests.
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc"
    b"\xff\xff?\x03\x00\x06\x00\x02\x00\x01\xa5\xc8\x7f\xb1\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)


class TestActorAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Actor]
        assert ma.list_display == ("full_name", "photo_thumbnail", "movies_count")

    def test_search_fields(self):
        ma = admin.site._registry[Actor]
        assert ma.search_fields == ("full_name",)

    def test_photo_thumbnail_returns_dash_when_no_photo(self):
        actor = ActorFactory(photo="")
        ma = admin.site._registry[Actor]
        assert ma.photo_thumbnail(actor) == "—"

    def test_photo_thumbnail_returns_img_tag_when_photo_set(self):
        actor = ActorFactory()
        actor.photo = SimpleUploadedFile("a.png", PNG_1X1, content_type="image/png")
        actor.save()
        ma = admin.site._registry[Actor]
        result = ma.photo_thumbnail(actor)
        assert isinstance(result, SafeString)
        assert "<img" in result
        assert actor.photo.url in result

    def test_movies_count_zero_when_no_movies(self):
        actor = ActorFactory()
        ma = admin.site._registry[Actor]
        assert ma.movies_count(actor) == 0

    def test_movies_count_returns_related_movie_count(self):
        actor = ActorFactory()
        m1 = MovieFactory()
        m2 = MovieFactory()
        m1.actors.add(actor)
        m2.actors.add(actor)
        ma = admin.site._registry[Actor]
        assert ma.movies_count(actor) == 2

    def test_thumbnail_and_count_have_short_descriptions(self):
        ma = admin.site._registry[Actor]
        assert ma.photo_thumbnail.short_description == "photo"
        assert ma.movies_count.short_description == "movies"
```

- [ ] **Step 2 (user): run — expect FAIL**

```bash
poetry run pytest tests/cinema/test_admin.py::TestActorAdmin -v
```

- [ ] **Step 3 (user): expand `ActorAdmin`**

Reference implementation (add `from django.utils.html import format_html` at top of file):

```python
from django.utils.html import format_html

# ... existing imports + admins ...

@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "photo_thumbnail", "movies_count")
    search_fields = ("full_name",)

    @admin.display(description="photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.photo.url)

    @admin.display(description="movies")
    def movies_count(self, obj):
        return obj.movies.count()
```

- [ ] **Step 4 (user): rerun — expect PASS**

- [ ] **Step 5 (user): cleanup test-uploaded media file (optional but nice — pytest-django doesn't auto-clean ImageField uploads)**

`MEDIA_ROOT` points at `<repo>/media/`. After the test run there'll be a stray `actors/a*.png` in `media/actors/`. Quickly delete it (or add the cleanup to `conftest.py` in a later pass — out of scope here).

- [ ] **Step 6 (user): commit**

```bash
git add tests/cinema/test_admin.py apps/cinema/admin.py
git commit -m "feat(FR-11): expand ActorAdmin with photo_thumbnail + movies_count"
```

---

## Task 6: DirectorAdmin — mirror of ActorAdmin

**Files:**
- Modify: `tests/cinema/test_admin.py`
- Modify: `apps/cinema/admin.py`

**Why now:** Mechanical duplication. Same shape as ActorAdmin; separate ModelAdmin class so future divergence (e.g., extra fields specific to Directors) doesn't require splitting later.

- [ ] **Step 1 (Claude): extend `tests/cinema/test_admin.py` with `TestDirectorAdmin`**

Append:

```python
from tests.cinema.factories import DirectorFactory


class TestDirectorAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Director]
        assert ma.list_display == ("full_name", "photo_thumbnail", "movies_count")

    def test_search_fields(self):
        ma = admin.site._registry[Director]
        assert ma.search_fields == ("full_name",)

    def test_photo_thumbnail_returns_dash_when_no_photo(self):
        director = DirectorFactory(photo="")
        ma = admin.site._registry[Director]
        assert ma.photo_thumbnail(director) == "—"

    def test_photo_thumbnail_returns_img_tag_when_photo_set(self):
        director = DirectorFactory()
        director.photo = SimpleUploadedFile("d.png", PNG_1X1, content_type="image/png")
        director.save()
        ma = admin.site._registry[Director]
        result = ma.photo_thumbnail(director)
        assert isinstance(result, SafeString)
        assert "<img" in result
        assert director.photo.url in result

    def test_movies_count_returns_related_movie_count(self):
        director = DirectorFactory()
        m = MovieFactory()
        m.directors.add(director)
        ma = admin.site._registry[Director]
        assert ma.movies_count(director) == 1
```

- [ ] **Step 2 (user): run — expect FAIL**

- [ ] **Step 3 (user): expand `DirectorAdmin` (mirror Actor)**

```python
@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "photo_thumbnail", "movies_count")
    search_fields = ("full_name",)

    @admin.display(description="photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.photo.url)

    @admin.display(description="movies")
    def movies_count(self, obj):
        return obj.movies.count()
```

- [ ] **Step 4 (user): rerun — expect PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_admin.py apps/cinema/admin.py
git commit -m "feat(FR-11): expand DirectorAdmin with photo_thumbnail + movies_count"
```

---

## Task 7: MovieAdmin — full FR-11 scope

**Files:**
- Modify: `tests/cinema/test_admin.py`
- Modify: `apps/cinema/admin.py`

**Why last:** This is the biggest one — `filter_horizontal`, `date_hierarchy`, three custom display methods, search across M2M reverse (`directors__full_name`). Doing it last means every helper pattern is already proven.

- [ ] **Step 1 (Claude): extend `tests/cinema/test_admin.py` with `TestMovieAdmin`**

Append:

```python
from tests.cinema.factories import GenreFactory  # already imported above; reuse


class TestMovieAdmin:
    def test_list_display_columns(self):
        ma = admin.site._registry[Movie]
        assert ma.list_display == (
            "title",
            "release_date",
            "poster_thumbnail",
            "screenings_count",
            "genres_list",
        )

    def test_search_fields(self):
        ma = admin.site._registry[Movie]
        assert ma.search_fields == ("title", "description", "directors__full_name")

    def test_list_filter(self):
        ma = admin.site._registry[Movie]
        assert ma.list_filter == ("genres", "release_date")

    def test_filter_horizontal(self):
        ma = admin.site._registry[Movie]
        assert ma.filter_horizontal == ("genres", "actors", "directors")

    def test_date_hierarchy(self):
        ma = admin.site._registry[Movie]
        assert ma.date_hierarchy == "release_date"

    def test_poster_thumbnail_returns_dash_when_no_poster(self):
        movie = MovieFactory(poster="")
        ma = admin.site._registry[Movie]
        assert ma.poster_thumbnail(movie) == "—"

    def test_poster_thumbnail_returns_img_tag_when_poster_set(self):
        movie = MovieFactory()
        movie.poster = SimpleUploadedFile("p.png", PNG_1X1, content_type="image/png")
        movie.save()
        ma = admin.site._registry[Movie]
        result = ma.poster_thumbnail(movie)
        assert isinstance(result, SafeString)
        assert "<img" in result
        assert movie.poster.url in result

    def test_screenings_count_zero_when_no_screenings(self):
        movie = MovieFactory()
        ma = admin.site._registry[Movie]
        assert ma.screenings_count(movie) == 0

    def test_screenings_count_returns_related_screening_count(self):
        movie = MovieFactory()
        ScreeningFactory.create_batch(2, movie=movie)
        ma = admin.site._registry[Movie]
        assert ma.screenings_count(movie) == 2

    def test_genres_list_returns_dash_when_no_genres(self):
        movie = MovieFactory()
        ma = admin.site._registry[Movie]
        assert ma.genres_list(movie) == "—"

    def test_genres_list_returns_comma_joined_names(self):
        movie = MovieFactory()
        g_action = GenreFactory(name="Action")
        g_drama = GenreFactory(name="Drama")
        movie.genres.add(g_action, g_drama)
        ma = admin.site._registry[Movie]
        result = ma.genres_list(movie)
        # Genre default ordering is ("name",) so Action precedes Drama.
        assert result == "Action, Drama"

    def test_custom_displays_have_short_descriptions(self):
        ma = admin.site._registry[Movie]
        assert ma.poster_thumbnail.short_description == "poster"
        assert ma.screenings_count.short_description == "screenings"
        assert ma.genres_list.short_description == "genres"
```

- [ ] **Step 2 (user): run — expect FAIL**

```bash
poetry run pytest tests/cinema/test_admin.py::TestMovieAdmin -v
```

- [ ] **Step 3 (user): expand `MovieAdmin`**

Reference implementation:

```python
@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "release_date",
        "poster_thumbnail",
        "screenings_count",
        "genres_list",
    )
    search_fields = ("title", "description", "directors__full_name")
    list_filter = ("genres", "release_date")
    filter_horizontal = ("genres", "actors", "directors")
    date_hierarchy = "release_date"

    @admin.display(description="poster")
    def poster_thumbnail(self, obj):
        if not obj.poster:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.poster.url)

    @admin.display(description="screenings")
    def screenings_count(self, obj):
        return obj.screenings.count()

    @admin.display(description="genres")
    def genres_list(self, obj):
        names = list(obj.genres.values_list("name", flat=True).order_by("name"))
        if not names:
            return "—"
        return ", ".join(names)
```

- [ ] **Step 4 (user): rerun — expect PASS**

- [ ] **Step 5 (user): commit**

```bash
git add tests/cinema/test_admin.py apps/cinema/admin.py
git commit -m "feat(FR-11): expand MovieAdmin with full FR-11 scope"
```

---

## Task 8: Coverage check + smoke + PR

**Files:**
- Modify: `.Claude/backlog.md`
- Modify: `memory/project_kinomania_bootstrap.md` (after merge — not in this PR)

- [ ] **Step 1 (user): full suite + coverage**

```bash
poetry run pytest --cov=apps --cov-report=term-missing
```

Expected: all tests pass; `apps/cinema/admin.py` shows ≥95% coverage (only missing branches: empty-image dashes are already tested for all three thumbnail methods, so this should hit 100%).

- [ ] **Step 2 (user): Django admin manual smoke (optional but recommended)**

```bash
poetry run python manage.py runserver
```

Browse to `http://localhost:5439/admin/cinema/` (or whichever port — `runserver` default is `8000`, the `5439` is Postgres). Log in as superuser. Confirm each of the 5 admins renders without 500:
- `/admin/cinema/genre/`
- `/admin/cinema/hall/`
- `/admin/cinema/actor/`
- `/admin/cinema/director/`
- `/admin/cinema/movie/` (verify M2M widgets are horizontal-filter, date hierarchy bar visible)

If you haven't got a superuser locally:

```bash
poetry run python manage.py createsuperuser
```

- [ ] **Step 3: update `.Claude/backlog.md` §7 status board**

Move `US-15` from **In Progress** to **Done** (✅). Update the M2 progress count (`2/8 US zmergowanych`). Identify next: **US-16** (`seed_db` extension).

- [ ] **Step 4 (user): commit backlog update**

```bash
git add .Claude/backlog.md
git commit -m "docs(M2): mark US-15 done, queue US-16 next"
```

- [ ] **Step 5 (user): push + open PR**

```bash
git push -u origin feat/FR-11-cinema-admin
```

Open PR using the structure mirrored from PR #11:

```
Title: feat(FR-11): cinema admin (5 ModelAdmins) — US-15

## Summary
- Register Genre/Actor/Director/Hall/Movie in Django admin (`apps/cinema/admin.py`)
- Custom display helpers: poster_thumbnail, photo_thumbnail, screenings_count, movies_count, genres_list
- MovieAdmin: filter_horizontal M2M widgets + date_hierarchy on release_date + search across directors__full_name
- 28 tests, 100% coverage on `apps/cinema/admin.py`

## Closes
- US-15 (FR-11 parts)

## Spec & Plan
- Plan: `docs/superpowers/plans/2026-05-20-cinema-admin.md`
- FR spec: `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-11

## Out of scope (deferred)
- ScreeningAdmin + BookingAdmin + inlines → US-28 (FR-11 booking-side admin, M3)

## Test plan
- [ ] CI green (lint, mypy, tests, ≥80% coverage)
- [ ] Manual smoke: each of the 5 admin pages renders for a superuser
- [ ] M2M widgets on MovieAdmin show as horizontal filter (not vertical select)
- [ ] Date hierarchy bar visible on MovieAdmin list page
```

- [ ] **Step 6 (after merge — separate session task): update memory**

After merge, update `memory/project_kinomania_bootstrap.md`:
- M2 progress: `2/8 US done`
- US-15 outcome line
- Note that US-16 is next

---

## Self-review summary

- ✅ All 5 FR-11 ModelAdmins covered (Genre, Hall, Actor, Director, Movie) — US-15 scope.
- ✅ All custom display helpers in FR-11 implemented (`poster_thumbnail`, `photo_thumbnail`, `screenings_count` ×2, `movies_count`, `genres_list`).
- ✅ Out-of-scope (Screening/Booking admin + inlines) explicitly deferred to US-28 — no silent gaps.
- ✅ Hall reverse accessor pitfall flagged in design notes (`screening_set` vs `screenings`).
- ✅ Tests cover registration + display methods + short descriptions + empty/populated branches.
- ✅ No placeholders, every step has runnable code/commands.
- ✅ One commit per ModelAdmin — small, reviewable diffs.
