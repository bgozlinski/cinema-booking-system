# US-31 — Public read-only API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `movies`, `screenings`, `genres`, `halls`, `actors`, `directors` as a public, paginated, filterable read-only REST API under `/api/v1/`, reusing existing model methods and the booked-count annotation.

**Architecture:** New `apps/cinema/api/{serializers,filters,viewsets,urls}.py`, mounted via a `SimpleRouter` at the API root. The booked-count annotation moves from `views.py` to a shared `apps/cinema/selectors.py` so both web and API use it (no API→views import). Movies use a list/detail serializer split; `available_seats_count` is served from the annotation to avoid N+1.

**Tech Stack:** DRF 3.17 (`ReadOnlyModelViewSet`, `SimpleRouter`), django-filter 25.2, drf-spectacular 0.29; pytest / pytest-django.

---

## Role division

- **User** writes all app files (`apps/cinema/**`, `settings/api_urls.py`) and runs all `git`/`pytest`. Claude proposes exact content.
- **Claude** writes all test code (`tests/**`).

Steps tagged **[User]** / **[Claude]**. Files that grow across tasks are shown **complete** each time (paste-safe).

## Spec

`docs/superpowers/specs/2026-05-24-us31-public-api-design.md`

## File structure

| File | Action | Responsibility | Author |
|------|--------|----------------|--------|
| `apps/cinema/selectors.py` | create | `annotate_booked_count` (moved from views) | User |
| `apps/cinema/views.py` | modify | import the moved helper; drop now-unused imports | User |
| `apps/cinema/api/__init__.py` | create | package marker | User |
| `apps/cinema/api/serializers.py` | create (grows) | resource serializers | User |
| `apps/cinema/api/filters.py` | create (grows) | `MovieFilter`, `ScreeningFilter` | User |
| `apps/cinema/api/viewsets.py` | create (grows) | `PublicReadViewSet` + 6 viewsets | User |
| `apps/cinema/api/urls.py` | create (grows) | `SimpleRouter` registrations | User |
| `settings/api_urls.py` | modify | mount cinema API at `""` | User |
| `tests/cinema/test_api_public.py` | create (grows) | endpoint + filter + N+1 tests | Claude |

## TDD strategy

Vertical slices by resource group; each endpoint's HTTP test is red (`404`) until its route is registered. Task 1 is a pure refactor guarded by the existing web-view suite. Commit on green per task; the first commit folds in the `backlog.md` board update.

---

### Task 1: Extract `annotate_booked_count` to `selectors.py`

**Files:**
- Create: `apps/cinema/selectors.py`
- Modify: `apps/cinema/views.py`

- [ ] **Step 1 [User]: Create `apps/cinema/selectors.py`**

```python
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.booking.models import BookingStatus


def annotate_booked_count(qs):
    """Annotate `_annotated_booked_count` on a Screening queryset.

    Sums seats from CONFIRMED + active-PENDING bookings so callers reading
    `Screening.available_seats_count()` / `is_available()` avoid an N+1 (the
    method short-circuits on the annotation). Shared by the web views and the API.
    Call per-request — it captures `timezone.now()`.
    """
    now = timezone.now()
    return qs.annotate(
        _annotated_booked_count=Coalesce(
            Sum(
                "bookings__seats_count",
                filter=(
                    Q(bookings__status=BookingStatus.CONFIRMED)
                    | Q(
                        bookings__status=BookingStatus.PENDING,
                        bookings__expires_at__gt=now,
                    )
                ),
            ),
            0,
        )
    )
```

- [ ] **Step 2 [User]: Update `apps/cinema/views.py`**

Replace the import block (lines 1–14) with — note `Sum`, `Coalesce`, `BookingStatus` are gone (now only used by the moved helper):
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
from apps.cinema.selectors import annotate_booked_count
from apps.cinema.utils import youtube_embed_url
```

Delete the `_annotate_booked_count` function definition (old lines 17–38). Then rename its two call sites: in `MovieDetailView.get_context_data` and `ScreeningListView.get_context_data`, change `_annotate_booked_count(` → `annotate_booked_count(`.

- [ ] **Step 3 [User]: Confirm the web suite still passes (refactor safety net)**

Run: `poetry run pytest tests/cinema -q --no-cov`
Expected: PASS (no behavioural change; existing tests exercise the moved helper).

- [ ] **Step 4 [User]: Commit (folds in the backlog board update)**

```bash
git add apps/cinema/selectors.py apps/cinema/views.py .Claude/backlog.md
git commit -m "refactor(FR-17): extract annotate_booked_count to cinema/selectors (US-31)"
```

---

### Task 2: Simple resources (genres / halls / actors / directors)

**Files:**
- Create: `apps/cinema/api/__init__.py`, `apps/cinema/api/serializers.py`, `apps/cinema/api/viewsets.py`, `apps/cinema/api/urls.py`
- Modify: `settings/api_urls.py`
- Test: `tests/cinema/test_api_public.py`

- [ ] **Step 1 [Claude]: Write the failing tests for the four simple resources**

Create `tests/cinema/test_api_public.py`:
```python
import pytest

from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    HallFactory,
)

pytestmark = pytest.mark.django_db


class TestSimpleResources:
    def test_genres_list_anon(self, api_client):
        GenreFactory(name="Sci-Fi")
        resp = api_client.get("/api/v1/genres/")
        assert resp.status_code == 200
        names = {g["name"] for g in resp.data["results"]}
        assert "Sci-Fi" in names

    def test_halls_list_anon(self, api_client):
        HallFactory(name="IMAX", capacity=300)
        resp = api_client.get("/api/v1/halls/")
        assert resp.status_code == 200
        assert {"id", "name", "description", "capacity"} <= set(resp.data["results"][0])

    def test_actors_list_anon(self, api_client):
        ActorFactory(full_name="Keanu Reeves")
        resp = api_client.get("/api/v1/actors/")
        assert resp.status_code == 200
        assert {"id", "full_name", "photo", "biography"} <= set(resp.data["results"][0])

    def test_directors_list_anon(self, api_client):
        DirectorFactory(full_name="Lana Wachowski")
        resp = api_client.get("/api/v1/directors/")
        assert resp.status_code == 200
        assert any(d["full_name"] == "Lana Wachowski" for d in resp.data["results"])

    def test_write_method_not_allowed(self, api_client):
        resp = api_client.post("/api/v1/genres/", {"name": "X"}, format="json")
        assert resp.status_code == 405
```

- [ ] **Step 2 [User]: Run to confirm they FAIL**

Run: `poetry run pytest tests/cinema/test_api_public.py -q --no-cov`
Expected: FAIL — `404` (no `/api/v1/genres/` etc.).

- [ ] **Step 3 [User]: Create `apps/cinema/api/__init__.py`** (empty file).

- [ ] **Step 4 [User]: Create `apps/cinema/api/serializers.py` (simple resources)**

```python
from rest_framework import serializers

from apps.cinema.models import Actor, Director, Genre, Hall


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = ("id", "name", "description", "capacity")


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ("id", "full_name", "photo", "biography")


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ("id", "full_name", "photo", "biography")
```

- [ ] **Step 5 [User]: Create `apps/cinema/api/viewsets.py` (base + simple viewsets)**

```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.cinema.api.serializers import (
    ActorSerializer,
    DirectorSerializer,
    GenreSerializer,
    HallSerializer,
)
from apps.cinema.models import Actor, Director, Genre, Hall


class PublicReadViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]


class GenreViewSet(PublicReadViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer


class HallViewSet(PublicReadViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer


class ActorViewSet(PublicReadViewSet):
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer


class DirectorViewSet(PublicReadViewSet):
    queryset = Director.objects.all()
    serializer_class = DirectorSerializer
```

- [ ] **Step 6 [User]: Create `apps/cinema/api/urls.py` (four routes)**

```python
from rest_framework.routers import SimpleRouter

from apps.cinema.api.viewsets import (
    ActorViewSet,
    DirectorViewSet,
    GenreViewSet,
    HallViewSet,
)

router = SimpleRouter()
router.register("genres", GenreViewSet)
router.register("halls", HallViewSet)
router.register("actors", ActorViewSet)
router.register("directors", DirectorViewSet)

urlpatterns = router.urls
```

- [ ] **Step 7 [User]: Mount the cinema API in `settings/api_urls.py`**

Replace the file with (adds the `path("", include("apps.cinema.api.urls"))` line):
```python
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("auth/", include("apps.accounts.api.urls")),
    path("", include("apps.cinema.api.urls")),
]
```

- [ ] **Step 8 [User]: Run to confirm PASS**

Run: `poetry run pytest tests/cinema/test_api_public.py -q --no-cov`
Expected: PASS (5 passed).

- [ ] **Step 9 [User]: Commit**

```bash
git add apps/cinema/api/ settings/api_urls.py tests/cinema/test_api_public.py
git commit -m "feat(FR-17): public read API for genres/halls/actors/directors (US-31)"
```

---

### Task 3: Movies (list + detail + filters)

**Files:**
- Modify: `apps/cinema/api/serializers.py`, `apps/cinema/api/viewsets.py`, `apps/cinema/api/urls.py`
- Create: `apps/cinema/api/filters.py`
- Test: `tests/cinema/test_api_public.py`

- [ ] **Step 1 [Claude]: Append the movie tests**

Add to `tests/cinema/test_api_public.py` (new top-level imports + class):
```python
from django.utils import timezone
from datetime import timedelta

from tests.cinema.factories import MovieFactory, ScreeningFactory


class TestMovies:
    def test_list_anon_paginated_full_catalog(self, api_client):
        # 13 movies, none with screenings -> still all listed (full catalog)
        for _ in range(13):
            MovieFactory()
        resp = api_client.get("/api/v1/movies/")
        assert resp.status_code == 200
        assert resp.data["count"] == 13
        assert len(resp.data["results"]) == 12  # PAGE_SIZE

    def test_list_item_shape(self, api_client):
        scifi = GenreFactory(name="Sci-Fi")
        MovieFactory(title="The Matrix", genres=[scifi])
        resp = api_client.get("/api/v1/movies/?search=Matrix")
        assert resp.status_code == 200
        item = resp.data["results"][0]
        assert {"id", "title", "release_date", "duration_minutes", "poster", "genres"} == set(item)
        assert item["genres"][0]["name"] == "Sci-Fi"

    def test_filter_by_genre(self, api_client):
        scifi = GenreFactory(name="Sci-Fi")
        drama = GenreFactory(name="Drama")
        MovieFactory(title="Matrix", genres=[scifi])
        MovieFactory(title="Rain Man", genres=[drama])
        resp = api_client.get(f"/api/v1/movies/?genre={scifi.id}")
        titles = {m["title"] for m in resp.data["results"]}
        assert titles == {"Matrix"}

    def test_filter_by_release_date_range(self, api_client):
        MovieFactory(title="Old", release_date="2000-01-01")
        MovieFactory(title="New", release_date="2025-01-01")
        resp = api_client.get("/api/v1/movies/?release_date_after=2010-01-01")
        titles = {m["title"] for m in resp.data["results"]}
        assert titles == {"New"}

    def test_detail_nested_shape(self, api_client):
        actor = ActorFactory(full_name="Keanu Reeves")
        director = DirectorFactory(full_name="Lana Wachowski")
        scifi = GenreFactory(name="Sci-Fi")
        movie = MovieFactory(title="Matrix", genres=[scifi], actors=[actor], directors=[director])
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=3))
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=3))  # past
        resp = api_client.get(f"/api/v1/movies/{movie.id}/")
        assert resp.status_code == 200
        assert resp.data["title"] == "Matrix"
        assert resp.data["genres"][0]["name"] == "Sci-Fi"
        assert resp.data["actors"][0]["full_name"] == "Keanu Reeves"
        assert resp.data["directors"][0]["full_name"] == "Lana Wachowski"
        assert len(resp.data["upcoming_screenings"]) == 1  # past excluded
        assert "available_seats_count" in resp.data["upcoming_screenings"][0]
```

- [ ] **Step 2 [User]: Run movie tests to confirm they FAIL**

Run: `poetry run pytest tests/cinema/test_api_public.py::TestMovies -q --no-cov`
Expected: FAIL — `404` (movies route not registered).

- [ ] **Step 3 [User]: Create `apps/cinema/api/filters.py`**

```python
import django_filters

from apps.cinema.models import Movie


class MovieFilter(django_filters.FilterSet):
    genre = django_filters.NumberFilter(field_name="genres", lookup_expr="exact")
    release_date = django_filters.DateFromToRangeFilter(field_name="release_date")

    class Meta:
        model = Movie
        fields = ["genre", "release_date"]
```

- [ ] **Step 4 [User]: Replace `apps/cinema/api/serializers.py` (adds movie serializers)**

```python
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening
from apps.cinema.selectors import annotate_booked_count


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = ("id", "name", "description", "capacity")


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ("id", "full_name", "photo", "biography")


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ("id", "full_name", "photo", "biography")


class MovieMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = ("id", "title", "poster")


class MovieScreeningSerializer(serializers.ModelSerializer):
    hall = HallSerializer(read_only=True)
    available_seats_count = serializers.SerializerMethodField()

    class Meta:
        model = Screening
        fields = ("id", "hall", "start_time", "price", "available_seats_count")

    def get_available_seats_count(self, obj) -> int:
        return obj.available_seats_count()


class MovieListSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)

    class Meta:
        model = Movie
        fields = ("id", "title", "release_date", "duration_minutes", "poster", "genres")


class MovieDetailSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    actors = ActorSerializer(many=True, read_only=True)
    directors = DirectorSerializer(many=True, read_only=True)
    upcoming_screenings = serializers.SerializerMethodField()

    class Meta:
        model = Movie
        fields = (
            "id",
            "title",
            "description",
            "release_date",
            "duration_minutes",
            "poster",
            "trailer_url",
            "genres",
            "actors",
            "directors",
            "upcoming_screenings",
        )

    @extend_schema_field(MovieScreeningSerializer(many=True))
    def get_upcoming_screenings(self, obj):
        qs = annotate_booked_count(
            obj.screenings.filter(start_time__gte=timezone.now())
            .select_related("hall")
            .order_by("start_time")
        )
        return MovieScreeningSerializer(qs, many=True).data
```

- [ ] **Step 5 [User]: Replace `apps/cinema/api/viewsets.py` (adds MovieViewSet)**

```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.cinema.api.filters import MovieFilter
from apps.cinema.api.serializers import (
    ActorSerializer,
    DirectorSerializer,
    GenreSerializer,
    HallSerializer,
    MovieDetailSerializer,
    MovieListSerializer,
)
from apps.cinema.models import Actor, Director, Genre, Hall, Movie


class PublicReadViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]


class GenreViewSet(PublicReadViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer


class HallViewSet(PublicReadViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer


class ActorViewSet(PublicReadViewSet):
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer


class DirectorViewSet(PublicReadViewSet):
    queryset = Director.objects.all()
    serializer_class = DirectorSerializer


class MovieViewSet(PublicReadViewSet):
    queryset = Movie.objects.all()
    filterset_class = MovieFilter
    search_fields = ["title"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MovieDetailSerializer
        return MovieListSerializer

    def get_queryset(self):
        qs = Movie.objects.prefetch_related("genres")
        if self.action == "retrieve":
            qs = qs.prefetch_related("actors", "directors")
        return qs
```

- [ ] **Step 6 [User]: Replace `apps/cinema/api/urls.py` (register movies)**

```python
from rest_framework.routers import SimpleRouter

from apps.cinema.api.viewsets import (
    ActorViewSet,
    DirectorViewSet,
    GenreViewSet,
    HallViewSet,
    MovieViewSet,
)

router = SimpleRouter()
router.register("movies", MovieViewSet)
router.register("genres", GenreViewSet)
router.register("halls", HallViewSet)
router.register("actors", ActorViewSet)
router.register("directors", DirectorViewSet)

urlpatterns = router.urls
```

- [ ] **Step 7 [User]: Run movie tests to confirm PASS**

Run: `poetry run pytest tests/cinema/test_api_public.py -q --no-cov`
Expected: PASS (simple + movie tests).

- [ ] **Step 8 [User]: Commit**

```bash
git add apps/cinema/api/ tests/cinema/test_api_public.py
git commit -m "feat(FR-17): movies list/detail API + filters (US-31)"
```

---

### Task 4: Screenings (list + detail + filters + N+1)

**Files:**
- Modify: `apps/cinema/api/serializers.py`, `apps/cinema/api/filters.py`, `apps/cinema/api/viewsets.py`, `apps/cinema/api/urls.py`
- Test: `tests/cinema/test_api_public.py`

- [ ] **Step 1 [Claude]: Append the screening tests**

Add to `tests/cinema/test_api_public.py`:
```python
import datetime as dt

from tests.booking.factories import ConfirmedBookingFactory


class TestScreenings:
    def test_list_anon_with_available_seats(self, api_client):
        hall = HallFactory(name="A", capacity=10)
        screening = ScreeningFactory(hall=hall, start_time=timezone.now() + timedelta(days=2))
        ConfirmedBookingFactory(screening=screening, seats_count=3)
        resp = api_client.get("/api/v1/screenings/")
        assert resp.status_code == 200
        row = next(s for s in resp.data["results"] if s["id"] == screening.id)
        assert row["available_seats_count"] == 7
        assert row["movie"]["id"] == screening.movie_id
        assert {"id", "name", "capacity", "description"} <= set(row["hall"])

    def test_filter_by_date(self, api_client):
        # Pin to noon local on the target day -> deterministic across TZ/DST
        # (avoids the now()+1day-UTC vs localdate()+1 boundary flakiness).
        target = timezone.localdate() + timedelta(days=1)
        on_time = timezone.make_aware(dt.datetime.combine(target, dt.time(12, 0)))
        on = ScreeningFactory(start_time=on_time)
        ScreeningFactory(start_time=on_time + timedelta(days=9))
        resp = api_client.get(f"/api/v1/screenings/?date={target.isoformat()}")
        ids = {s["id"] for s in resp.data["results"]}
        assert on.id in ids
        assert len(ids) == 1

    def test_filter_by_movie_and_hall(self, api_client):
        hall = HallFactory(name="H1")
        s1 = ScreeningFactory(hall=hall)
        ScreeningFactory()  # different movie + hall
        resp = api_client.get(f"/api/v1/screenings/?movie={s1.movie_id}&hall={hall.id}")
        ids = {s["id"] for s in resp.data["results"]}
        assert ids == {s1.id}

    def test_detail(self, api_client):
        screening = ScreeningFactory()
        resp = api_client.get(f"/api/v1/screenings/{screening.id}/")
        assert resp.status_code == 200
        assert "available_seats_count" in resp.data

    def test_list_query_budget(self, api_client, django_assert_max_num_queries):
        for _ in range(8):
            ScreeningFactory(start_time=timezone.now() + timedelta(days=2))
        with django_assert_max_num_queries(6):
            api_client.get("/api/v1/screenings/")
```

- [ ] **Step 2 [User]: Run screening tests to confirm they FAIL**

Run: `poetry run pytest tests/cinema/test_api_public.py::TestScreenings -q --no-cov`
Expected: FAIL — `404` (screenings route not registered).

- [ ] **Step 3 [User]: Replace `apps/cinema/api/filters.py` (adds ScreeningFilter)**

```python
import datetime
from datetime import time, timedelta

import django_filters
from django.utils import timezone

from apps.cinema.models import Movie, Screening


class MovieFilter(django_filters.FilterSet):
    genre = django_filters.NumberFilter(field_name="genres", lookup_expr="exact")
    release_date = django_filters.DateFromToRangeFilter(field_name="release_date")

    class Meta:
        model = Movie
        fields = ["genre", "release_date"]


class ScreeningFilter(django_filters.FilterSet):
    date = django_filters.DateFilter(method="filter_date")
    movie = django_filters.NumberFilter(field_name="movie__id")
    hall = django_filters.NumberFilter(field_name="hall__id")

    class Meta:
        model = Screening
        fields = ["date", "movie", "hall"]

    def filter_date(self, queryset, name, value):
        day_start = timezone.make_aware(datetime.datetime.combine(value, time.min))
        day_end = day_start + timedelta(days=1)
        return queryset.filter(start_time__gte=day_start, start_time__lt=day_end)
```

- [ ] **Step 4 [User]: Append `ScreeningSerializer` to `apps/cinema/api/serializers.py`**

Add at the end (after `MovieDetailSerializer`):
```python


class ScreeningSerializer(serializers.ModelSerializer):
    movie = MovieMiniSerializer(read_only=True)
    hall = HallSerializer(read_only=True)
    available_seats_count = serializers.SerializerMethodField()

    class Meta:
        model = Screening
        fields = ("id", "movie", "hall", "start_time", "price", "available_seats_count")

    def get_available_seats_count(self, obj) -> int:
        return obj.available_seats_count()
```

- [ ] **Step 5 [User]: Replace `apps/cinema/api/viewsets.py` (adds ScreeningViewSet)**

```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.cinema.api.filters import MovieFilter, ScreeningFilter
from apps.cinema.api.serializers import (
    ActorSerializer,
    DirectorSerializer,
    GenreSerializer,
    HallSerializer,
    MovieDetailSerializer,
    MovieListSerializer,
    ScreeningSerializer,
)
from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening
from apps.cinema.selectors import annotate_booked_count


class PublicReadViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]


class GenreViewSet(PublicReadViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer


class HallViewSet(PublicReadViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer


class ActorViewSet(PublicReadViewSet):
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer


class DirectorViewSet(PublicReadViewSet):
    queryset = Director.objects.all()
    serializer_class = DirectorSerializer


class MovieViewSet(PublicReadViewSet):
    queryset = Movie.objects.all()
    filterset_class = MovieFilter
    search_fields = ["title"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MovieDetailSerializer
        return MovieListSerializer

    def get_queryset(self):
        qs = Movie.objects.prefetch_related("genres")
        if self.action == "retrieve":
            qs = qs.prefetch_related("actors", "directors")
        return qs


class ScreeningViewSet(PublicReadViewSet):
    queryset = Screening.objects.all()
    serializer_class = ScreeningSerializer
    filterset_class = ScreeningFilter

    def get_queryset(self):
        return annotate_booked_count(Screening.objects.select_related("movie", "hall"))
```

- [ ] **Step 6 [User]: Replace `apps/cinema/api/urls.py` (register screenings)**

```python
from rest_framework.routers import SimpleRouter

from apps.cinema.api.viewsets import (
    ActorViewSet,
    DirectorViewSet,
    GenreViewSet,
    HallViewSet,
    MovieViewSet,
    ScreeningViewSet,
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

- [ ] **Step 7 [User]: Run the full API test file to confirm PASS**

Run: `poetry run pytest tests/cinema/test_api_public.py -q --no-cov`
Expected: PASS (all simple + movie + screening tests).

- [ ] **Step 8 [User]: Commit**

```bash
git add apps/cinema/api/ tests/cinema/test_api_public.py
git commit -m "feat(FR-17): screenings API + filters + available_seats_count (US-31)"
```

---

### Task 5: Quality gate

- [ ] **Step 1 [User]: Full suite with coverage**

Run: `poetry run pytest`
Expected: PASS, coverage ≥ 80%.

- [ ] **Step 2 [User]: Lint + format**

Run: `poetry run ruff check . && poetry run ruff format --check .`
Expected: clean (if format flags any api file, run `poetry run ruff format .` then re-check).

- [ ] **Step 3 [User]: Type-check**

Run: `poetry run mypy .`
Expected: clean. Watch: `get_serializer_class`/`get_queryset` overrides; `SerializerMethodField` getters return `int`.

- [ ] **Step 4 [User]: Manual smoke (optional)**

Run `poetry run python manage.py runserver`, then `GET http://localhost:8000/api/v1/movies/` and `/api/v1/docs/` (movies/screenings/… now appear in Swagger).

---

## Out of scope

Admin/staff write API (US-34) · booking endpoints (US-32) · `bearerAuth` rename + strict CI schema gate (US-35) · throttle-trip 429 tests (US-36).

## Test plan summary

- `tests/cinema/test_api_public.py`: simple resources (4 lists + 405); movies (pagination/full-catalog, item shape, genre + release_date filters, search, nested detail with upcoming-only screenings); screenings (available_seats_count vs bookings, date/movie/hall filters, detail, N+1 budget).
- Task 1 refactor guarded by the existing `tests/cinema` web-view suite.
- Coverage ≥ 80%; no migration.
