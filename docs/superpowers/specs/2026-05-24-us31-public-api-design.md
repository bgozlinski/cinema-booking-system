# US-31 — Public read-only API (design)

**Milestone:** M4 — REST API (`v0.4.0`)
**User story:** US-31 — Public read-only API: movies/screenings/genres/halls/actors/directors
**Branch:** `feat/FR-17-public-api`
**FR refs:** FR-17 (public read API), §4 (endpoint map), §8 (per-app `api/` structure)
**Date:** 2026-05-24
**Type:** plan-directly (L) — standard DRF read-only patterns; querysets reuse existing web helpers.
**Predecessor:** US-29 (DRF infra) + US-30 (auth API) ✅ merged.

---

## 1. Goal

Expose the catalog as a public, paginated, filterable read-only REST API under
`/api/v1/`: `movies`, `screenings`, `genres`, `halls`, `actors`, `directors`. This is
the first **router-based** per-app submodule (`apps/cinema/api/`); US-32/34 follow it.

**Definition of done (smoke):**
1. `GET /api/v1/movies/` (anon) → `200`, paginated (12), **full catalog**, ordered
   `-release_date, title`; filters `genre`, `release_date_after`, `release_date_before`,
   `search` (title).
2. `GET /api/v1/movies/<id>/` → nested `genres`, `actors`, `directors`,
   `upcoming_screenings` (future only).
3. `GET /api/v1/screenings/?date=YYYY-MM-DD&movie=&hall=` → `200`, each item carries a
   correct `available_seats_count`.
4. `GET /api/v1/screenings/<id>/` → `200` with `available_seats_count`.
5. `GET /api/v1/{genres,halls,actors,directors}/` → `200` listings.
6. All read endpoints are anonymous-accessible; write methods → `405`.

## 2. Scope boundary

**In scope:** the six read-only resources, list/detail split for movies, django-filter
FilterSets, the booked-count annotation reuse (+ its promotion to `selectors.py`), and tests.

**Out of scope (later US):**
- Admin/staff write API (CRUD, uploads) → US-34.
- Booking endpoints → US-32.
- `bearerAuth` rename + strict-mode CI schema gate → US-35.
- Throttle-trip (`429`) tests → US-36.

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| `/movies/` scope | **Full catalog** — all movies (model default `-release_date, title`), not the web's upcoming-only list. |
| Router | **`SimpleRouter`** per app (no `api-root` view) — avoids a cross-app `api-root` URL-name collision when US-32's booking router also mounts at the API root. |
| Permissions | `IsAuthenticatedOrReadOnly` via a small `PublicReadViewSet` base (read-only viewsets → public GET, writes → 405). |
| Nested actors/directors | Reuse the **full** `ActorSerializer`/`DirectorSerializer` (incl. `biography`) nested in movie-detail — one class each (slim variant deferred unless payloads bloat). |
| Booked-count N+1 | Reuse the existing annotation, **promoted** from `views.py` to `apps/cinema/selectors.py::annotate_booked_count` (shared by web views + API; no API→views import). |

## 4. Components

### `apps/cinema/api/serializers.py`
- `GenreSerializer` — `("id", "name")`.
- `HallSerializer` — `("id", "name", "description", "capacity")`.
- `ActorSerializer` — `("id", "full_name", "photo", "biography")`.
- `DirectorSerializer` — `("id", "full_name", "photo", "biography")`.
- `MovieMiniSerializer` — `("id", "title", "poster")` (embedded in screenings).
- `MovieListSerializer` — `("id", "title", "release_date", "duration_minutes", "poster",
  "genres")`; `genres = GenreSerializer(many=True, read_only=True)`.
- `MovieDetailSerializer` — `MovieListSerializer` fields + `("description", "trailer_url",
  "actors", "directors", "upcoming_screenings")`; `actors = ActorSerializer(many=True)`,
  `directors = DirectorSerializer(many=True)`, `upcoming_screenings = SerializerMethodField`.
  - `get_upcoming_screenings(self, obj)` → `annotate_booked_count(obj.screenings.filter(
    start_time__gte=timezone.now()).select_related("hall").order_by("start_time"))`,
    serialized via `MovieScreeningSerializer(many=True)`. Decorated
    `@extend_schema_field(MovieScreeningSerializer(many=True))` for a clean schema.
- `MovieScreeningSerializer` — `("id", "hall", "start_time", "price",
  "available_seats_count")`; `hall = HallSerializer(read_only=True)`; **no `movie`**
  (avoids movie→screening→movie recursion). `available_seats_count = SerializerMethodField`.
- `ScreeningSerializer` — `("id", "movie", "hall", "start_time", "price",
  "available_seats_count")`; `movie = MovieMiniSerializer(read_only=True)`,
  `hall = HallSerializer(read_only=True)`, `available_seats_count = SerializerMethodField`.

`available_seats_count` is a `SerializerMethodField` with `get_available_seats_count(self,
obj) -> int: return obj.available_seats_count()` (return-type hint → spectacular emits
`integer`). It honors the `_annotated_booked_count` annotation set by the viewset queryset.

### `apps/cinema/api/filters.py`
- `MovieFilter(django_filters.FilterSet)`:
  - `genre = django_filters.NumberFilter(field_name="genres", lookup_expr="exact")`
    (movies having that genre id; M2M exact on a single value → no duplicate rows).
  - `release_date = django_filters.DateFromToRangeFilter(field_name="release_date")`
    → query params `release_date_after` / `release_date_before` (matches FR-17).
  - `class Meta: model = Movie; fields = ["genre", "release_date"]`.
- `ScreeningFilter(django_filters.FilterSet)`:
  - `date = django_filters.DateFilter(method="filter_date")` → `filter_date` builds the
    DST-safe day window (`make_aware(combine(date, time.min))` .. `+1 day`) and filters
    `start_time__gte/__lt` (mirrors the web `ScreeningListView`).
  - `movie = django_filters.NumberFilter(field_name="movie__id")`.
  - `hall = django_filters.NumberFilter(field_name="hall__id")`.
  - `class Meta: model = Screening; fields = ["date", "movie", "hall"]`.

Title search uses DRF `SearchFilter` (`search_fields = ["title"]`) on `MovieViewSet`, not
the FilterSet (`?search=` per FR-17).

### `apps/cinema/api/viewsets.py`
- `class PublicReadViewSet(viewsets.ReadOnlyModelViewSet): permission_classes =
  [IsAuthenticatedOrReadOnly]` — shared base.
- `GenreViewSet` / `HallViewSet` / `ActorViewSet` / `DirectorViewSet` — `queryset =
  <Model>.objects.all()`, single `serializer_class`.
- `MovieViewSet(PublicReadViewSet)`:
  - `queryset = Movie.objects.all()` (basename + default order from the model).
  - `filterset_class = MovieFilter`; `search_fields = ["title"]`.
  - `get_serializer_class()` → `MovieDetailSerializer` if `self.action == "retrieve"`
    else `MovieListSerializer`.
  - `get_queryset()` → base `Movie.objects.all().prefetch_related("genres")`; when
    `self.action == "retrieve"`, also `prefetch_related("actors", "directors")`.
- `ScreeningViewSet(PublicReadViewSet)`:
  - `queryset = Screening.objects.all()` (for router basename only).
  - `serializer_class = ScreeningSerializer`; `filterset_class = ScreeningFilter`.
  - `get_queryset()` → `annotate_booked_count(Screening.objects.select_related("movie",
    "hall"))`. **Must be in `get_queryset` (per-request), not a class attribute** —
    `annotate_booked_count` captures `timezone.now()` internally, so a class-level
    queryset would freeze "now" at import time and use a stale active-PENDING window.

`DjangoFilterBackend` + `SearchFilter` + `OrderingFilter` are the global defaults (US-29),
so they apply without per-view wiring; `filterset_class`/`search_fields` opt in.

### `apps/cinema/selectors.py` (new) + `apps/cinema/views.py` (edit)
Move `_annotate_booked_count` from `views.py` to `apps/cinema/selectors.py` as
`annotate_booked_count` (public name). `views.py` imports it
(`from apps.cinema.selectors import annotate_booked_count`) and its three call sites use
the new name. The API imports the same helper. No behavioural change.

### `apps/cinema/api/urls.py` + `settings/api_urls.py`
```python
# apps/cinema/api/urls.py
from rest_framework.routers import SimpleRouter

from apps.cinema.api.viewsets import (
    ActorViewSet, DirectorViewSet, GenreViewSet, HallViewSet, MovieViewSet, ScreeningViewSet,
)

router = SimpleRouter()
router.register("movies", MovieViewSet)
router.register("screenings", ScreeningViewSet)
router.register("genres", GenreViewSet)
router.register("halls", HallViewSet)
router.register("actors", ActorViewSet)
router.register("directors", DirectorViewSet)

urlpatterns = router.urls
```
`settings/api_urls.py`: replace the US-31 placeholder comment with
`path("", include("apps.cinema.api.urls"))` → `/api/v1/movies/`, `/api/v1/screenings/`, etc.

## 5. OpenAPI

`MovieViewSet`'s action-based `get_serializer_class` is detected by drf-spectacular (it
introspects per action). `SerializerMethodField`s carry type hints / `@extend_schema_field`
so no warning is introduced. Strict-mode CI gate stays US-35.

## 6. Testing (Claude writes — `tests/cinema/test_api_public.py`)

Uses `api_client` (US-29) + cinema factories.
- **movies** — anon list `200`; pagination page_size 12 (create 13+, assert `count` +
  `len(results)==12`); **full catalog** (a movie with no screenings still appears, unlike
  the web list); `genre` filter; `release_date_after`/`before`; `search=` on title;
  detail nested `genres`/`actors`/`directors`; `upcoming_screenings` excludes past.
- **screenings** — anon list `200`; `date`/`movie`/`hall` filters; `available_seats_count`
  reflects CONFIRMED + active-PENDING bookings (reuse booking factories); detail.
- **genres/halls/actors/directors** — list `200` + field shape.
- **permissions/methods** — anon GET allowed everywhere; `POST /api/v1/movies/` → `405`.
- **N+1 budgets** — `django_assert_max_num_queries` on movies-list and screenings-list
  with a populated DB (the annotation + prefetch keep counts flat).

## 7. Coverage / migration

New `apps/cinema/api/` + `selectors.py` are real code → covered by §6 tests; threshold
≥ 80% maintained. **No migration** (no model changes; `selectors.py` is a code move).

## 8. Risks

1. **M2M `genre` filter duplicates.** Single-value exact on `genres` yields each movie
   once (movie-genre pairs are unique) — no `.distinct()` needed. If a multi-value genre
   filter is added later, revisit.
2. **`available_seats_count` N+1 + stale-`now`.** Mitigated by `annotate_booked_count` on
   the screening queryset and the `_annotated_booked_count` short-circuit; the movie-detail
   `upcoming_screenings` method annotates its sub-queryset too. **`annotate_booked_count`
   must run per-request** (`get_queryset` / method body) — never as a class-attribute
   queryset, or `timezone.now()` freezes at import time. Covered by N+1 budget tests.
3. **Recursion in nested serializers.** `MovieScreeningSerializer` omits `movie`;
   `ScreeningSerializer` uses `MovieMiniSerializer` (no `screenings`). No cycle.
4. **`selectors.py` move.** Update all three `views.py` call sites + the import; the web
   view tests must stay green (run full suite in the quality gate).
5. **drf-spectacular + method fields.** Type hints / `@extend_schema_field` prevent
   schema warnings now (US-35 enforces strict).

## 9. Build order (for the plan)

1. `selectors.py` extraction + `views.py` import swap (web suite stays green).
2. Serializers (+ serializer-focused tests where useful).
3. Filters.
4. ViewSets + `urls.py` + mount; endpoint + filter + N+1 tests.
5. Quality gate: pytest (cov ≥ 80%), ruff, mypy.

The first branch commit folds in the `backlog.md` board update (US-30 → Done, US-31 → In
Progress) made at US-31 start.
