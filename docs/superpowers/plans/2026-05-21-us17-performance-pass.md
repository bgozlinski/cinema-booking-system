# US-17 — Performance Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit i wyeliminować N+1 w admin (US-15) + rozszerzyć budget testy public views (US-11/13/14) o nowe scenariusze. Po merge — zamknąć M2 cuttingiem tagu `v0.2.0` i dorzuceniem outstanding `v0.1.0`.

**Architecture:** TDD-style perf — dla każdego targetu: napisz budget test, zmierz, refactor jeśli za drogie, tighten cap. Public views (3) bez refactoru — tylko nowe scenariusze. Admin (5) z `get_queryset` annotate/prefetch_related override. Bez zmian backendu poza `apps/cinema/admin.py`.

**Tech Stack:** Django 6 `Count` annotate + `prefetch_related`, `@admin.display(ordering=...)` dla sortable columns, pytest-django `django_assert_max_num_queries` + `RequestFactory` adapter dla istniejących helper testów, `tests/accounts/factories.UserFactory(is_superuser=True)` dla admin client.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-21-us17-performance-pass.md`.

**Założenie testowe:** 11 nowych testów (6 public extensions + 5 admin budget). Aktualizacja ~11 istniejących testów w `tests/cinema/test_admin.py` ze względu na nowy access pattern helperów (`obj._<name>_count` zamiast `obj.<rel>.count()`).

**Role division (per `.Claude/commit_convention.md` §10 + memory `feedback_role_division`):**
- Claude pisze WSZYSTKIE testy (test_*.py, fixtures) — testy są jego scope.
- Claude pisze również refactor w `apps/cinema/admin.py` (mimo że to "kod aplikacji") — bo to drobne perf changes ściśle związane z testami; user może to zostawić Claude'owi LUB skopiować ręcznie. Default: ja piszę.
- User odpala wszystkie komendy git/gh + pytest sam.

**⚠️ Uwaga PyCharm (z `feedback_pycharm_django_templates`):** US-17 nie ma template'ów, więc hard-wrap nie szkodzi. Ale pyfile może być reformatowany przez ruff format — to OK.

---

## Branch Strategy

Pre-Task-1 — utwórz nowy branch off main:

```bash
git checkout main && git pull
git checkout -b perf/FR-01-prefetch
git branch --show-current   # → perf/FR-01-prefetch
```

Spec + plan (uncommited na main) commitujemy jako pierwszy commit NA branchu (pattern z PR #18, #19):

```bash
git add docs/superpowers/specs/2026-05-21-us17-performance-pass.md \
        docs/superpowers/plans/2026-05-21-us17-performance-pass.md
git commit -m "$(cat <<'EOF'
docs(M2): add US-17 performance pass spec and implementation plan

Brainstorming + planning artifacts for US-17 — last M2 task before v0.2.0 cut.
Scope: audit existing prefetch_related on public views (US-11/13/14, already
optimized) + eliminate N+1 in admin (US-15) via get_queryset annotate. 8 budget
targets: 3 public view test extensions + 5 admin refactors. Closing M2 includes
v0.1.0 tag (outstanding from M1) + v0.2.0 tag + GitHub releases.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `tests/cinema/test_movie_list.py` | Modify (extend `TestQueryBudget`) | +3 scenariusze: genre filter / date filter / pagination |
| `tests/cinema/test_movie_detail.py` | Modify (extend `TestQueryBudget`) | +1 scenariusz: orphan movie |
| `tests/cinema/test_screening_list.py` | Modify (extend `TestQueryBudget`) | +2 scenariusze: empty day / big dataset |
| `tests/cinema/test_admin_query_budgets.py` | Create | 5 klas: TestXAdminQueryBudget × 5 ModelAdminów + lokalny `admin_client` fixture |
| `apps/cinema/admin.py` | Modify (5 admin classes) | Każdy admin dostaje `get_queryset` + zaktualizowany helper |
| `tests/cinema/test_admin.py` | Modify (~11 testów) | Aktualizacja helper-call tests do nowego access pattern przez admin queryset |
| `.Claude/backlog.md` | Modify (§7 status board) | US-17 → Done |

---

## Task 1: Extend `MovieListView` budget tests (+3 scenariusze, no refactor)

**Files:**
- Modify: `tests/cinema/test_movie_list.py` (extend `TestQueryBudget` class)

- [ ] **Step 1: Otwórz `tests/cinema/test_movie_list.py`, w klasie `TestQueryBudget` (linia ~267) dopisz po istniejącym teście `test_full_page_uses_bounded_queries` trzy nowe metody:**

```python
    def test_with_genre_filter_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Filter ?genre=<id> dodaje WHERE na M2M, ale prefetch_related("genres")
        trzyma genre data — query count nie skaluje się z liczbą filmów."""
        from django.utils import timezone
        from datetime import timedelta

        genre = GenreFactory(name="Drama")
        for _ in range(8):
            movie = MovieFactory()
            movie.genres.add(genre)
            ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        # 4 movies bez genre Drama (żeby filter rzeczywiście filtrował)
        for _ in range(4):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        # Budget: 1 paginator + 1 movies (filtered) + 1 prefetched genres + 1 form dropdown = 4.
        # Cap at 5 (zgodnie z base test buffer).
        with django_assert_max_num_queries(5):
            client.get(f"/?genre={genre.pk}")

    def test_with_date_filter_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Filter ?date=YYYY-MM-DD dodaje JOIN na screenings + .distinct() — paginator
        count distinct może wprowadzić extra query."""
        from django.utils import timezone
        from datetime import timedelta

        tomorrow = (timezone.now() + timedelta(days=1)).date()
        for _ in range(6):
            movie = MovieFactory()
            ScreeningFactory(
                movie=movie,
                start_time=timezone.make_aware(
                    __import__("datetime").datetime.combine(tomorrow, __import__("datetime").time(20, 0))
                ),
            )

        # Budget: 1 paginator (with distinct) + 1 movies + 1 prefetched genres + 1 form dropdown
        # + ewentualnie 1 extra dla distinct count = 5-6. Cap at 6.
        with django_assert_max_num_queries(6):
            client.get(f"/?date={tomorrow.isoformat()}")

    def test_pagination_second_page_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Paginacja nie zmienia query count — paginator robi LIMIT/OFFSET, prefetch trzyma."""
        from django.utils import timezone
        from datetime import timedelta

        for i in range(20):
            movie = MovieFactory()
            ScreeningFactory(
                movie=movie,
                start_time=timezone.now() + timedelta(days=i + 1),
            )

        # Budget: ten sam co base — 5.
        with django_assert_max_num_queries(5):
            client.get("/?page=2")
```

⚠️ **Uwaga import:** `MovieFactory`, `GenreFactory`, `ScreeningFactory` powinny już być importowane na górze pliku. Jeśli nie — dodaj do istniejących importów.

- [ ] **Step 2: Run tylko nowe testy żeby zweryfikować że przechodzą:**

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestQueryBudget -v
```

Oczekiwane: wszystkie 4 (1 base + 3 new) zielone. Jeśli któryś fail z "X queries used, limit Y" → zanotuj actual X, dostosuj cap (np. fail at 7 → bump cap to 8 IF nadal sensownie), lub investigate dlaczego więcej.

- [ ] **Step 3: Run pełen pytest (regression):**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 4: Commit:**

```bash
git add tests/cinema/test_movie_list.py
git commit -m "$(cat <<'EOF'
test(M2): extend MovieListView budget tests (filter + pagination scenarios)

Adds 3 scenarios to TestQueryBudget: ?genre=<id> filter (M2M JOIN, prefetch
absorbs), ?date=YYYY-MM-DD filter (JOIN + distinct, paginator count may be +1),
and ?page=2 (pagination doesn't change query count). Caps match existing base
test (5 for genre/page, 6 for date due to distinct count overhead).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Extend `MovieDetailView` budget test (+1 scenariusz, no refactor)

**Files:**
- Modify: `tests/cinema/test_movie_detail.py` (extend `TestQueryBudget` class)

- [ ] **Step 1: Otwórz `tests/cinema/test_movie_detail.py`, w klasie `TestQueryBudget` (linia ~296) dopisz po istniejącym teście:**

```python
    def test_orphan_movie_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Movie bez screenings/actors/directors/trailer — prefetch'y dla M2M tabel
        wciąż odpalają się jako fixed cost (zwracają 0 rows), więc cap nie spada
        gwałtownie. Verification: brak N+1 dla emptys."""
        movie = MovieFactory(trailer_url="")
        # Bez add(*genres), bez ScreeningFactory(movie=movie), bez actors/directors.

        # Budget: 1 movie + 3 prefetch (genres/actors/directors, każdy zwraca 0) + 1 screenings
        # filter+select_related (zwraca 0) = 5. Cap 6 (zgodnie z base buffer).
        with django_assert_max_num_queries(6):
            response = client.get(f"/movies/{movie.pk}/")
            assert response.status_code == 200
```

- [ ] **Step 2: Run nowy test:**

```bash
poetry run pytest tests/cinema/test_movie_detail.py::TestQueryBudget -v
```

Oczekiwane: zielone (2 testy: base + orphan).

- [ ] **Step 3: Run pełen pytest:**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 4: Commit:**

```bash
git add tests/cinema/test_movie_detail.py
git commit -m "$(cat <<'EOF'
test(M2): add orphan-movie scenario to MovieDetailView budget test

Verifies that a movie with no screenings/actors/directors/trailer still respects
the query budget — prefetch_related runs as fixed cost regardless of M2M
population. Cap 6 (matches base test buffer).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Extend `ScreeningListView` budget tests (+2 scenariusze, no refactor)

**Files:**
- Modify: `tests/cinema/test_screening_list.py` (extend `TestQueryBudget` class)

- [ ] **Step 1: Otwórz `tests/cinema/test_screening_list.py`, w klasie `TestQueryBudget` (linia ~264) dopisz po istniejącym teście:**

```python
    def test_empty_day_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Empty day = 0 screenings. Brak prefetch needed (empty queryset),
        tylko Screening fetch + (optional) messages/session baseline."""
        from django.utils import timezone
        from datetime import timedelta

        # Tworzę screening DZIŚ, ale pytam o TOMORROW (empty result for tomorrow).
        ScreeningFactory(start_time=timezone.now())
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()

        # Budget: 1 screenings (zwraca 0) + 1 messages (Django messages framework) = 2.
        with django_assert_max_num_queries(2):
            response = client.get(f"/screenings/?date={tomorrow}")
            assert response.status_code == 200

    def test_big_dataset_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """20 movies × 5 screenings = 100 rows. Prefetch nie skaluje się z N —
        budget pozostaje stały."""
        from django.utils import timezone
        from datetime import timedelta

        tomorrow = timezone.localdate() + timedelta(days=1)
        for i in range(20):
            movie = MovieFactory()
            for hour in (10, 13, 16, 19, 22):
                ScreeningFactory(
                    movie=movie,
                    start_time=timezone.make_aware(
                        __import__("datetime").datetime.combine(
                            tomorrow, __import__("datetime").time(hour, 0)
                        )
                    ),
                )

        # Budget: 1 screenings (z select_related + prefetch) + 1 messages = 2-3.
        # Cap 3 (zgodnie z base buffer).
        with django_assert_max_num_queries(3):
            response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
            assert response.status_code == 200
```

⚠️ Jeśli `_make_local_dt` helper istnieje w pliku (memory wspomina jego użycie w big-dataset test) — użyj go zamiast inline `make_aware(datetime.combine(...))`. Sprawdź na początku pliku.

- [ ] **Step 2: Run nowe testy:**

```bash
poetry run pytest tests/cinema/test_screening_list.py::TestQueryBudget -v
```

Oczekiwane: 3 zielone.

- [ ] **Step 3: Run pełen pytest:**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 4: Commit:**

```bash
git add tests/cinema/test_screening_list.py
git commit -m "$(cat <<'EOF'
test(M2): extend ScreeningListView budget tests (empty day + big dataset)

Adds 2 scenarios: empty day (0 screenings for the requested date, cap 2 —
no prefetch needed) and big dataset (20 movies × 5 screenings = 100 rows,
cap 3 — prefetch_related doesn't scale with row count).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: GenreAdmin perf — bootstrap test file + first admin refactor

**Files:**
- Create: `tests/cinema/test_admin_query_budgets.py`
- Modify: `apps/cinema/admin.py` (GenreAdmin)
- Modify: `tests/cinema/test_admin.py` (TestGenreAdmin — 2 testy z helper call)

- [ ] **Step 1: Utwórz `tests/cinema/test_admin_query_budgets.py` z fixturem + pierwszą klasą:**

```python
"""Per-admin changelist query budget tests (US-17 / FR-perf).

Each ModelAdmin in apps/cinema/admin.py is hit through its changelist URL with
a populated DB and budgeted via django_assert_max_num_queries. Caps are
data-driven: started loose during US-17 implementation, tightened after measuring
the actual query count post-refactor.

The N+1 risk lives in custom display helpers (movies_count, screenings_count,
genres_list). Without get_queryset override these helpers spawn a query per row.
After refactor (annotate(Count(...)) + prefetch_related where needed) the count
is loaded once at the queryset level.
"""

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory
from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    HallFactory,
    MovieFactory,
    ScreeningFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    """Logged-in superuser. Local to this module — central conftest deferred
    until a second test file needs admin_client (US-28 booking admin most likely)."""
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    return client


class TestGenreAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 genres × ~3 movies each. Without get_queryset override, movies_count
        helper triggers 1 query per row (12 N+1). After refactor: 1 annotate query
        absorbed into the changelist's main fetch."""
        for _ in range(12):
            genre = GenreFactory()
            for _ in range(3):
                movie = MovieFactory()
                movie.genres.add(genre)

        url = reverse("admin:cinema_genre_changelist")

        # Cap: 12 (post-refactor educated guess = admin baseline ~10 + 1 annotate + 1 buffer).
        # Tighten after measurement in step 4.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200
```

- [ ] **Step 2: Run test żeby zobaczyć aktualny query count (przed refactorem):**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestGenreAdminQueryBudget -v
```

Oczekiwane: **FAIL** z "X queries used, but limit is 12". Zanotuj X — to jest baseline przed refactorem (estimate ~22: 12 N+1 + ~10 admin baseline). Jeśli **PASS** at 12 — wow, admin baseline jest mniejszy niż myślałem; przejdź do Step 3.

- [ ] **Step 3: Refactor `apps/cinema/admin.py::GenreAdmin`. Otwórz plik, na górze dodaj import:**

```python
from django.db.models import Count
```

Następnie zastąp klasę `GenreAdmin` (linia 8-15):

```python
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "movies_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_movies_count=Count("movies"))

    @admin.display(description="movies", ordering="_movies_count")
    def movies_count(self, obj):
        return obj._movies_count
```

- [ ] **Step 4: Re-run budget test z verbose żeby zobaczyć new count:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestGenreAdminQueryBudget -v
```

Oczekiwane: **PASS**. Jeśli output mówi "queries used: Y" — zanotuj Y. Cel: cap = Y + 1 (buffer). Jeśli Y == 10 i cap 12 — można tighten do 11.

Tighten cap (opcjonalne): wróć do `tests/cinema/test_admin_query_budgets.py` i zmień `django_assert_max_num_queries(12)` na `django_assert_max_num_queries(Y + 1)`. Update docstring komentarz `# Cap: <Y+1> (post-refactor measured: <Y> queries)`.

- [ ] **Step 5: Sprawdź czy istniejące testy `test_admin.py` przeszły. Run TestGenreAdmin:**

```bash
poetry run pytest tests/cinema/test_admin.py::TestGenreAdmin -v
```

Oczekiwane: **2 FAIL** (`test_movies_count_zero_when_no_movies`, `test_movies_count_returns_related_movie_count`) z AttributeError: 'Genre' object has no attribute '_movies_count'. Helper czyta `obj._movies_count` które na surowym model instance NIE istnieje.

- [ ] **Step 6: Zaktualizuj `tests/cinema/test_admin.py::TestGenreAdmin` żeby helper calls szły przez admin queryset.**

Na górze pliku dodaj import jeśli nie istnieje:

```python
from django.test import RequestFactory
```

Zastąp 2 broken testy w klasie `TestGenreAdmin` (linie ~58-70):

```python
    def test_movies_count_zero_when_no_movies(self):
        genre = GenreFactory()
        ma = admin.site._registry[Genre]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=genre.pk)
        assert ma.movies_count(annotated) == 0

    def test_movies_count_returns_related_movie_count(self):
        genre = GenreFactory()
        m1 = MovieFactory()
        m2 = MovieFactory()
        m1.genres.add(genre)
        m2.genres.add(genre)
        ma = admin.site._registry[Genre]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=genre.pk)
        assert ma.movies_count(annotated) == 2
```

`test_movies_count_has_short_description` (linia ~72) zostaje bez zmian — sprawdza `short_description` attribute on helper, niezwiązane z access pattern.

- [ ] **Step 7: Run pełen test_admin.py + test_admin_query_budgets.py:**

```bash
poetry run pytest tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py -v
```

Oczekiwane: wszystkie zielone (`TestGenreAdmin` 5 testów + `TestGenreAdminQueryBudget` 1 test).

- [ ] **Step 8: Run pełen pytest (full regression):**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 9: Commit:**

```bash
git add apps/cinema/admin.py tests/cinema/test_admin_query_budgets.py tests/cinema/test_admin.py
git commit -m "$(cat <<'EOF'
perf(M2): kill N+1 in GenreAdmin via annotate + sortable count column

Adds GenreAdmin.get_queryset override with annotate(_movies_count=Count("movies"))
and switches movies_count helper to read the annotated field — eliminates 1 query
per row in the /admin/cinema/genre/ changelist. Bonus: ordering="_movies_count"
on @admin.display makes the column sortable. Tests: new TestGenreAdminQueryBudget
in tests/cinema/test_admin_query_budgets.py; existing TestGenreAdmin helper tests
updated to pull annotated instances through ma.get_queryset(request).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: HallAdmin perf

**Files:**
- Modify: `apps/cinema/admin.py` (HallAdmin)
- Modify: `tests/cinema/test_admin_query_budgets.py` (add class)
- Modify: `tests/cinema/test_admin.py` (TestHallAdmin — 2 testy z helper call)

- [ ] **Step 1: W `tests/cinema/test_admin_query_budgets.py` dopisz po `TestGenreAdminQueryBudget`:**

```python
class TestHallAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 halls × ~2 screenings each. Without get_queryset override,
        screenings_count helper triggers 1 query per row (12 N+1)."""
        for _ in range(12):
            hall = HallFactory()
            ScreeningFactory.create_batch(2, hall=hall)

        url = reverse("admin:cinema_hall_changelist")
        # Cap 12: admin baseline + 1 annotate + 1 buffer. Tighten in step 4.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200
```

- [ ] **Step 2: Run test żeby zobaczyć baseline:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestHallAdminQueryBudget -v
```

Oczekiwane: **FAIL** (12 N+1 + admin baseline > 12). Zanotuj actual count X.

- [ ] **Step 3: Refactor `apps/cinema/admin.py::HallAdmin`. Zastąp klasę (linia 17-24, używając już zaimportowanego `Count`):**

```python
@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "screenings_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_screenings_count=Count("screening"))

    @admin.display(description="screenings", ordering="_screenings_count")
    def screenings_count(self, obj):
        return obj._screenings_count
```

⚠️ **Uwaga path:** `Count("screening")` — lowercase model name (`Screening.hall` ma default reverse `screening_set` na instance, ale annotate path używa lowercase model name `screening`, bez `_set`).

- [ ] **Step 4: Re-run budget test, tighten cap:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestHallAdminQueryBudget -v
```

Oczekiwane: **PASS**. Zanotuj Y i ewentualnie tighten cap do Y+1 (update docstring `# Cap: <Y+1> (post-refactor measured: <Y>)`).

- [ ] **Step 5: Sprawdź broken testy:**

```bash
poetry run pytest tests/cinema/test_admin.py::TestHallAdmin -v
```

Oczekiwane: **2 FAIL** (`test_screenings_count_zero_when_no_screenings`, `test_screenings_count_returns_related_screening_count`).

- [ ] **Step 6: Zaktualizuj `tests/cinema/test_admin.py::TestHallAdmin`. Zastąp 2 broken testy (linie ~86-95):**

```python
    def test_screenings_count_zero_when_no_screenings(self):
        hall = HallFactory()
        ma = admin.site._registry[Hall]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=hall.pk)
        assert ma.screenings_count(annotated) == 0

    def test_screenings_count_returns_related_screening_count(self):
        hall = HallFactory()
        ScreeningFactory.create_batch(3, hall=hall)
        ma = admin.site._registry[Hall]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=hall.pk)
        assert ma.screenings_count(annotated) == 3
```

- [ ] **Step 7: Run pełen test_admin.py + test_admin_query_budgets.py:**

```bash
poetry run pytest tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py -v
```

Oczekiwane: zielone.

- [ ] **Step 8: Run pełen pytest (regression):**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 9: Commit:**

```bash
git add apps/cinema/admin.py tests/cinema/test_admin_query_budgets.py tests/cinema/test_admin.py
git commit -m "$(cat <<'EOF'
perf(M2): kill N+1 in HallAdmin via annotate + sortable count column

HallAdmin.get_queryset annotates _screenings_count via Count("screening")
(lowercase model name, no related_name on Screening.hall FK). Helper reads the
annotated field; column is sortable via @admin.display(ordering=...). Tests:
TestHallAdminQueryBudget in admin_query_budgets file, existing TestHallAdmin
helper tests updated to use annotated queryset.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: ActorAdmin perf

**Files:**
- Modify: `apps/cinema/admin.py` (ActorAdmin)
- Modify: `tests/cinema/test_admin_query_budgets.py` (add class)
- Modify: `tests/cinema/test_admin.py` (TestActorAdmin — 2 testy z helper call)

- [ ] **Step 1: W `tests/cinema/test_admin_query_budgets.py` dopisz po `TestHallAdminQueryBudget`:**

```python
class TestActorAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 actors × ~2 movies each. movies_count helper is N+1 per row."""
        for _ in range(12):
            actor = ActorFactory()
            for _ in range(2):
                movie = MovieFactory()
                movie.actors.add(actor)

        url = reverse("admin:cinema_actor_changelist")
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200
```

- [ ] **Step 2: Run test żeby zobaczyć baseline:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestActorAdminQueryBudget -v
```

Oczekiwane: **FAIL**. Zanotuj X.

- [ ] **Step 3: Refactor `apps/cinema/admin.py::ActorAdmin`. Zastąp klasę (linia ~27-40):**

```python
@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "photo_thumbnail", "movies_count")
    search_fields = ("full_name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_movies_count=Count("movies"))

    @admin.display(description="photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.photo.url)

    @admin.display(description="movies", ordering="_movies_count")
    def movies_count(self, obj):
        return obj._movies_count
```

- [ ] **Step 4: Re-run budget test, tighten cap:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestActorAdminQueryBudget -v
```

Oczekiwane: **PASS** at <12. Tighten cap jeśli measurement pokazuje headroom.

- [ ] **Step 5: Sprawdź broken testy:**

```bash
poetry run pytest tests/cinema/test_admin.py::TestActorAdmin -v
```

Oczekiwane: **2 FAIL** (`test_movies_count_zero_when_no_movies`, `test_movies_count_returns_related_movie_count`).

- [ ] **Step 6: Zaktualizuj `tests/cinema/test_admin.py::TestActorAdmin`. Zastąp 2 broken testy (linie ~126-138):**

```python
    def test_movies_count_zero_when_no_movies(self):
        actor = ActorFactory()
        ma = admin.site._registry[Actor]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=actor.pk)
        assert ma.movies_count(annotated) == 0

    def test_movies_count_returns_related_movie_count(self):
        actor = ActorFactory()
        m1 = MovieFactory()
        m2 = MovieFactory()
        m1.actors.add(actor)
        m2.actors.add(actor)
        ma = admin.site._registry[Actor]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=actor.pk)
        assert ma.movies_count(annotated) == 2
```

- [ ] **Step 7: Run pełen test_admin.py + test_admin_query_budgets.py:**

```bash
poetry run pytest tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py -v
```

Oczekiwane: zielone.

- [ ] **Step 8: Run pełen pytest (regression):**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 9: Commit:**

```bash
git add apps/cinema/admin.py tests/cinema/test_admin_query_budgets.py tests/cinema/test_admin.py
git commit -m "$(cat <<'EOF'
perf(M2): kill N+1 in ActorAdmin via annotate + sortable count column

ActorAdmin.get_queryset annotates _movies_count via Count("movies") (M2M reverse
via Movie.actors related_name="movies"). photo_thumbnail unchanged (FieldFile
reads instance attr, no DB query). Tests: TestActorAdminQueryBudget + existing
TestActorAdmin helper tests updated.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: DirectorAdmin perf

**Files:**
- Modify: `apps/cinema/admin.py` (DirectorAdmin)
- Modify: `tests/cinema/test_admin_query_budgets.py` (add class)
- Modify: `tests/cinema/test_admin.py` (TestDirectorAdmin — 1-2 testy z helper call)

- [ ] **Step 1: W `tests/cinema/test_admin_query_budgets.py` dopisz po `TestActorAdminQueryBudget`:**

```python
class TestDirectorAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 directors × ~2 movies each. movies_count helper is N+1 per row."""
        for _ in range(12):
            director = DirectorFactory()
            for _ in range(2):
                movie = MovieFactory()
                movie.directors.add(director)

        url = reverse("admin:cinema_director_changelist")
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200
```

- [ ] **Step 2: Run test żeby zobaczyć baseline:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestDirectorAdminQueryBudget -v
```

Oczekiwane: **FAIL**.

- [ ] **Step 3: Refactor `apps/cinema/admin.py::DirectorAdmin`. Zastąp klasę (linia ~43-56):**

```python
@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "photo_thumbnail", "movies_count")
    search_fields = ("full_name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_movies_count=Count("movies"))

    @admin.display(description="photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.photo.url)

    @admin.display(description="movies", ordering="_movies_count")
    def movies_count(self, obj):
        return obj._movies_count
```

- [ ] **Step 4: Re-run budget test, tighten cap:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestDirectorAdminQueryBudget -v
```

Oczekiwane: **PASS**.

- [ ] **Step 5: Sprawdź broken testy:**

```bash
poetry run pytest tests/cinema/test_admin.py::TestDirectorAdmin -v
```

Oczekiwane: **1-2 FAIL** (sprawdź dokładnie które — z grepu plan'a wiemy że jest `test_movies_count_returns_related_movie_count` na linii ~170). Może być mniej testów niż dla Actor.

- [ ] **Step 6: Zaktualizuj `tests/cinema/test_admin.py::TestDirectorAdmin`. Zastąp broken testy. Pattern (jeśli istnieje test_movies_count_zero):**

```python
    def test_movies_count_zero_when_no_movies(self):
        director = DirectorFactory()
        ma = admin.site._registry[Director]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=director.pk)
        assert ma.movies_count(annotated) == 0

    def test_movies_count_returns_related_movie_count(self):
        director = DirectorFactory()
        m1 = MovieFactory()
        m1.directors.add(director)
        ma = admin.site._registry[Director]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=director.pk)
        assert ma.movies_count(annotated) == 1
```

⚠️ Sprawdź faktyczne testy w pliku — Director sekcja może mieć inne assertion values (test_movies_count_returns_related_movie_count w grepie używał count == 1, nie 2 jak inni). Adapt do faktycznego stanu.

- [ ] **Step 7: Run pełen test_admin.py + test_admin_query_budgets.py:**

```bash
poetry run pytest tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py -v
```

Oczekiwane: zielone.

- [ ] **Step 8: Run pełen pytest (regression):**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 9: Commit:**

```bash
git add apps/cinema/admin.py tests/cinema/test_admin_query_budgets.py tests/cinema/test_admin.py
git commit -m "$(cat <<'EOF'
perf(M2): kill N+1 in DirectorAdmin via annotate + sortable count column

DirectorAdmin.get_queryset annotates _movies_count via Count("movies"). Mirrors
ActorAdmin refactor (same M2M reverse path through Movie.directors related_name).
Tests: TestDirectorAdminQueryBudget + existing TestDirectorAdmin helper tests
updated.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: MovieAdmin perf (2 N+1 helpery — most complex)

**Files:**
- Modify: `apps/cinema/admin.py` (MovieAdmin)
- Modify: `tests/cinema/test_admin_query_budgets.py` (add class)
- Modify: `tests/cinema/test_admin.py` (TestMovieAdmin — 4 testy: 2× screenings_count + 2× genres_list)

- [ ] **Step 1: W `tests/cinema/test_admin_query_budgets.py` dopisz po `TestDirectorAdminQueryBudget`:**

```python
class TestMovieAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 movies × ~3 genres × ~2 screenings. Without refactor: 2 N+1 helpers
        (screenings_count + genres_list) = 24 extra queries on top of admin baseline.
        After refactor: 1 annotate + 1 prefetch + admin baseline ~10."""
        for _ in range(12):
            movie = MovieFactory()
            for _ in range(3):
                movie.genres.add(GenreFactory())
            ScreeningFactory.create_batch(2, movie=movie)

        url = reverse("admin:cinema_movie_changelist")
        # Cap 15: admin baseline (~10) + 1 annotate + 1 prefetch + 1 list_filter dropdown + 2 buffer.
        # Tighten in step 4.
        with django_assert_max_num_queries(15):
            response = admin_client.get(url)
            assert response.status_code == 200
```

- [ ] **Step 2: Run test żeby zobaczyć baseline:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestMovieAdminQueryBudget -v
```

Oczekiwane: **FAIL** at ~34 queries (12+12 N+1 + admin baseline).

- [ ] **Step 3: Refactor `apps/cinema/admin.py::MovieAdmin`. Zastąp klasę (linia ~59-83):**

```python
@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "release_date", "poster_thumbnail", "screenings_count", "genres_list")
    search_fields = ("title", "description", "directors__full_name")
    list_filter = ("genres", "release_date")
    filter_horizontal = ("genres", "actors", "directors")
    date_hierarchy = "release_date"

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .annotate(_screenings_count=Count("screenings", distinct=True))
            .prefetch_related("genres")
        )

    @admin.display(description="poster")
    def poster_thumbnail(self, obj):
        if not obj.poster:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.poster.url)

    @admin.display(description="screenings", ordering="_screenings_count")
    def screenings_count(self, obj):
        return obj._screenings_count

    @admin.display(description="genres")
    def genres_list(self, obj):
        names = sorted(g.name for g in obj.genres.all())
        return ", ".join(names) if names else "—"
```

**Kluczowe zmiany:**
- `Count("screenings", distinct=True)` — `distinct=True` defensywne bo `list_filter=("genres",)` wprowadza M2M JOIN do queryset; bez distinct Count duplikowałby
- `prefetch_related("genres")` — dla `genres_list` helpera; obecne `values_list(...).order_by(...)` ZAWSZE robi fresh query bypassując prefetch cache, dlatego helper jest przepisany
- `sorted(g.name for g in obj.genres.all())` używa prefetch cache (free Python sort)
- `genres_list` bez `ordering=` (nie sortable, bo to comma-joined string, sort by tym nie ma sensu)
- `screenings_count` z `ordering="_screenings_count"` (sortable bonus)

- [ ] **Step 4: Re-run budget test, tighten cap:**

```bash
poetry run pytest tests/cinema/test_admin_query_budgets.py::TestMovieAdminQueryBudget -v
```

Oczekiwane: **PASS** at ~12-14. Zanotuj Y, tighten cap do Y+1 (update docstring).

- [ ] **Step 5: Sprawdź broken testy:**

```bash
poetry run pytest tests/cinema/test_admin.py::TestMovieAdmin -v
```

Oczekiwane: **4 FAIL**:
- `test_screenings_count_zero_when_no_screenings`
- `test_screenings_count_returns_related_screening_count`
- `test_genres_list_returns_dash_when_no_genres`
- `test_genres_list_returns_comma_joined_names`

- [ ] **Step 6: Zaktualizuj `tests/cinema/test_admin.py::TestMovieAdmin`. Zastąp 4 broken testy (linie ~220-250):**

```python
    def test_screenings_count_zero_when_no_screenings(self):
        movie = MovieFactory()
        ma = admin.site._registry[Movie]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=movie.pk)
        assert ma.screenings_count(annotated) == 0

    def test_screenings_count_returns_related_screening_count(self):
        movie = MovieFactory()
        ScreeningFactory.create_batch(2, movie=movie)
        ma = admin.site._registry[Movie]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=movie.pk)
        assert ma.screenings_count(annotated) == 2

    def test_genres_list_returns_dash_when_no_genres(self):
        movie = MovieFactory()
        ma = admin.site._registry[Movie]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=movie.pk)
        assert ma.genres_list(annotated) == "—"

    def test_genres_list_returns_comma_joined_names(self):
        movie = MovieFactory()
        g1 = GenreFactory(name="Drama")
        g2 = GenreFactory(name="Action")
        movie.genres.add(g1, g2)
        ma = admin.site._registry[Movie]
        request = RequestFactory().get("/admin/")
        annotated = ma.get_queryset(request).get(pk=movie.pk)
        # New impl sorts alphabetically (sorted(g.name for g in obj.genres.all()))
        assert ma.genres_list(annotated) == "Action, Drama"
```

⚠️ Sprawdź czy istniejący `test_genres_list_returns_comma_joined_names` ma już sorted assertion (`"Action, Drama"`) czy unsorted. Stary kod używał `values_list("name", flat=True).order_by("name")` — czyli też sortowano alfabetycznie. Nowy impl `sorted(...)` daje identyczny wynik. Jeśli test wcześniej assertował `"Action, Drama"` — assertion pozostaje bez zmian (tylko access pattern się zmienia).

- [ ] **Step 7: Run pełen test_admin.py + test_admin_query_budgets.py:**

```bash
poetry run pytest tests/cinema/test_admin.py tests/cinema/test_admin_query_budgets.py -v
```

Oczekiwane: zielone.

- [ ] **Step 8: Run pełen pytest (regression):**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 9: Commit:**

```bash
git add apps/cinema/admin.py tests/cinema/test_admin_query_budgets.py tests/cinema/test_admin.py
git commit -m "$(cat <<'EOF'
perf(M2): kill 2 N+1s in MovieAdmin via annotate + prefetch + sortable column

MovieAdmin.get_queryset adds annotate(_screenings_count=Count("screenings",
distinct=True)) and prefetch_related("genres"). distinct=True is defensive —
list_filter=("genres",) introduces an M2M JOIN to the queryset which would
duplicate Count rows without it. genres_list helper rewritten to use prefetch
cache (sorted(g.name for g in obj.genres.all())) instead of values_list().
order_by() which always bypasses prefetch. screenings_count column sortable.
Tests: TestMovieAdminQueryBudget + 4 existing TestMovieAdmin helper tests
updated to use annotated queryset.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Tighten public view caps (optional, data-driven)

Po ukończeniu Tasks 1-8 zmierz czy obecne capy w public TestQueryBudget classes mają headroom — jeśli tak, tighten do real+1.

**Files:**
- Modify (potentially): `tests/cinema/test_movie_list.py`, `test_movie_detail.py`, `test_screening_list.py`

- [ ] **Step 1: Sprawdź faktyczny query count w istniejących base testach z verbose:**

```bash
poetry run pytest tests/cinema/test_movie_list.py::TestQueryBudget::test_full_page_uses_bounded_queries -v --tb=short
poetry run pytest tests/cinema/test_movie_detail.py::TestQueryBudget::test_full_page_uses_bounded_queries -v --tb=short
poetry run pytest tests/cinema/test_screening_list.py::TestQueryBudget::test_full_day_uses_bounded_queries -v --tb=short
```

Jeśli wyniki PASS z dużym headroom (np. cap 5, actual 3) — możesz tighten. Można też uruchomić każdy test z **celowo zaniżonym** cap, np. `with django_assert_max_num_queries(1)`, żeby wymusić fail i zobaczyć w error message exact query count.

- [ ] **Step 2: Jeśli measurement pokazuje headroom — tighten capów. Update docstring:**

Przykład: jeśli `test_full_page_uses_bounded_queries` w `test_movie_list.py` pasuje przy actual=4 mimo cap=5, zmień:

```python
        # Budget: 1 paginator.count + 1 movies + 1 prefetched genres + 1 form genre dropdown = 4.
        # Cap at 4 (tightened from 5 after US-17 measurement — no headroom needed).
        with django_assert_max_num_queries(4):
            client.get("/")
```

- [ ] **Step 3: Run pełen pytest:**

```bash
poetry run pytest -x --tb=short
```

Oczekiwane: zielone.

- [ ] **Step 4: Commit (jeśli zmiany były):**

```bash
git add tests/cinema/test_movie_list.py tests/cinema/test_movie_detail.py tests/cinema/test_screening_list.py
git commit -m "$(cat <<'EOF'
test(M2): tighten public view query budgets after US-17 measurement

Existing budget caps (5/6/3) had buffer headroom; tightened to actual+1 based on
US-17 audit. Caps now reflect real-world query count per view; future N+1 fails
trigger immediately.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Jeśli measurement nie wykazał headroom → ten task skip (pominąć commit). Zapisz w PR description że "tighten check zostawił capy bez zmian".

---

## Task 10: Update `.Claude/backlog.md` — US-17 → Done

**Files:**
- Modify: `.Claude/backlog.md` (§7 status board)

- [ ] **Step 1: Otwórz `.Claude/backlog.md`, znajdź §7 (status board, linie ~363-368). Zaktualizuj:**

Stary:
```markdown
| **Ready (DoR ✅)** | **US-17** (performance pass / `prefetch_related` audit, NFR) — **last M2 task**, zamyka milestone `v0.2.0` |
| **Backlog** | US-18..US-43 (M3..M5) |
| **Done** | **US-01..US-16** ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅ |
```

Nowy:
```markdown
| **Ready (DoR ✅)** | **US-18** (M3 kickoff — Booking model + reservation flow) |
| **Backlog** | US-19..US-43 (M3..M5) |
| **Done** | **US-01..US-17** ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅ — M2 (`v0.2.0`) COMPLETE |
```

(Liczba ✅ matches: US-01..US-17 = 17 checkmarków.)

- [ ] **Step 2: Commit:**

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M2): mark US-17 done and close M2 in backlog status board

US-17 (performance pass) merged — last M2 task. Status board updated: US-17 → Done,
US-18 (M3 kickoff) moves to Ready. M2 (v0.2.0) complete; cut tag + release post-merge.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Final verification + PR

- [ ] **Step 1: Pełen pytest + coverage:**

```bash
poetry run pytest --cov
```

Oczekiwane: wszystkie zielone, coverage ≥80%. Wklej summary jeśli coś chrupnie.

- [ ] **Step 2: Lint + format + mypy:**

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
```

Oczekiwane: zero błędów.

- [ ] **Step 3: Manualne smoke test admin (opcjonalne ale zalecane):**

```bash
poetry run python manage.py seed_db --flush
poetry run python manage.py runserver
```

Login na `/admin/` jako superuser (jeśli brak — `python manage.py createsuperuser`). Otwórz:
1. `/admin/cinema/movie/` — sprawdź czy column **`screenings`** ma sortable arrows (↑/↓) — klik header → sortuje
2. `/admin/cinema/genre/` — sortable **`movies`** column
3. `/admin/cinema/hall/` — sortable **`screenings`**
4. `/admin/cinema/actor/` — sortable **`movies`**
5. `/admin/cinema/director/` — sortable **`movies`**

Zatrzymaj.

- [ ] **Step 4: Sprawdź historię commitów:**

```bash
git log --oneline main..HEAD
```

Oczekiwane: **8-10 commitów**:
1. `docs(M2): add US-17 performance pass spec and implementation plan`
2. `test(M2): extend MovieListView budget tests (filter + pagination scenarios)`
3. `test(M2): add orphan-movie scenario to MovieDetailView budget test`
4. `test(M2): extend ScreeningListView budget tests (empty day + big dataset)`
5. `perf(M2): kill N+1 in GenreAdmin via annotate + sortable count column`
6. `perf(M2): kill N+1 in HallAdmin via annotate + sortable count column`
7. `perf(M2): kill N+1 in ActorAdmin via annotate + sortable count column`
8. `perf(M2): kill N+1 in DirectorAdmin via annotate + sortable count column`
9. `perf(M2): kill 2 N+1s in MovieAdmin via annotate + prefetch + sortable column`
10. (optional) `test(M2): tighten public view query budgets after US-17 measurement`
11. `docs(M2): mark US-17 done and close M2 in backlog status board`

- [ ] **Step 5: Push + PR:**

```bash
git push -u origin perf/FR-01-prefetch
gh pr create --title "perf(M2): US-17 performance pass — admin N+1 elimination + budget audit" --body "$(cat <<'EOF'
## Summary
- **US-17 — last M2 task before v0.2.0 cut.** Performance audit + N+1 elimination across cinema admin.
- **Admin refactor** (`apps/cinema/admin.py`): 5 ModelAdminów dostają `get_queryset` override z `annotate(Count(...))` zamiast per-row `.count()` w display helperach. Bonus: każdy count column jest teraz sortable via `@admin.display(ordering=...)`. `MovieAdmin` dodatkowo `prefetch_related("genres")` + zmieniony `genres_list` helper (sorted Python na prefetched M2M zamiast `values_list().order_by()` które bypasowało prefetch).
- **Public views**: zero zmian backendu (`views.py` was already correctly optimized in US-11/13/14). Tylko rozszerzenie budget testów o 6 nowych scenariuszy (genre/date filters, pagination, orphan movie, empty day, big dataset).
- **Test coverage**: 5 nowych admin budget testów w nowym pliku `tests/cinema/test_admin_query_budgets.py` + 6 nowych scenariuszy w istniejących `TestQueryBudget` klasach. ~11 istniejących testów w `test_admin.py` zaktualizowanych do nowego access pattern przez admin queryset.

## Linked
- Spec: `docs/superpowers/specs/2026-05-21-us17-performance-pass.md`
- Plan: `docs/superpowers/plans/2026-05-21-us17-performance-pass.md`
- Closes US-17

## Definition of Done checklist
- [x] AC: wszystkie budget testy green (11 nowych + istniejące unchanged)
- [x] N+1 elimination: 5 ModelAdminów zrefaktorowanych
- [x] Bonus: sortable count columns w 5 ModelAdminach
- [x] Existing test_admin.py helper tests zaktualizowane (RequestFactory + queryset adapter)
- [x] `pytest --cov` zielone, coverage ≥80%
- [x] `ruff check`, `ruff format --check`, `mypy` — czyste
- [x] Manual smoke: sortable columns działają w admin UI
- [x] Brak nowych migracji
- [x] Brak nowych dependencies

## Test plan
- [x] `pytest tests/cinema/test_movie_list.py::TestQueryBudget -v` — 4 zielone (1 base + 3 new)
- [x] `pytest tests/cinema/test_movie_detail.py::TestQueryBudget -v` — 2 zielone (1 base + orphan)
- [x] `pytest tests/cinema/test_screening_list.py::TestQueryBudget -v` — 3 zielone
- [x] `pytest tests/cinema/test_admin_query_budgets.py -v` — 5 zielonych (per ModelAdmin)
- [x] `pytest tests/cinema/test_admin.py -v` — wszystkie zielone (TestXAdmin helper tests updated)
- [x] Manualne sprawdzenie admin UI: 5 sortable count columns

## Closing M2 (post-merge)
- [ ] Outstanding `v0.1.0` tag na merge commit PR #9 (M1 close — wciąż nie wykonane z memory)
- [ ] `v0.2.0` tag na merge commit tego PR-a
- [ ] (Optional) GitHub releases dla obu tagów
- [ ] Memory update: `project_kinomania_bootstrap.md` → reflect M2 close + M3 transition
- [ ] Create `.Claude/m3_planning.md` (analog do `m2_planning.md`) jako session-start brief dla M3

## Out of scope (follow-up)
- `Screening.hall` related_name inconsistency (cosmetic, requires migration — osobny refactor PR)
- Full-text search Polish `to_tsvector` (US-17b lub M3 add)
- `django-debug-toolbar` integration (explicit odrzucone w brainstormingu)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Wklej URL PR-a po utworzeniu.

---

## Task 12 (post-merge): Closing M2

Wykonaj **dopiero po merge PR-a US-17 do main**.

- [ ] **Step 1: Sync local main:**

```bash
git checkout main && git pull
git log --oneline -5
```

- [ ] **Step 2: Cleanup local branch:**

```bash
git branch -d perf/FR-01-prefetch
git remote prune origin
```

- [ ] **Step 3: Outstanding `v0.1.0` tag (M1 close, z memory backlog).**

Znajdź merge commit PR #9 (M1 close):

```bash
git log --grep="Merge pull request #9" --oneline
```

Zanotuj SHA. Następnie:

```bash
git tag -a v0.1.0 <SHA> -m "M1 — Foundation (US-01..US-09)"
git push origin v0.1.0
```

Opcjonalnie GitHub release:

```bash
gh release create v0.1.0 --title "v0.1.0 — Foundation" --notes "M1 (Foundation) — US-01..US-09 complete. Setup, accounts (email auth + activation), seed_db, base templates, M1 baseline."
```

- [ ] **Step 4: `v0.2.0` tag (M2 close):**

```bash
git tag -a v0.2.0 -m "M2 — Catalog web (US-10..US-17)"
git push origin v0.2.0
```

Opcjonalnie GitHub release:

```bash
gh release create v0.2.0 --title "v0.2.0 — Catalog web" --notes "$(cat <<'EOF'
M2 (Catalog web) — US-10..US-17 complete.

## Highlights
- Cinema models: Genre/Actor/Director/Hall/Movie/Screening (US-10)
- Admin: MovieAdmin + 4 other ModelAdminów (US-15)
- seed_db extension: 9 genres, halls, actors, directors, 20 movies, 100 screenings (US-16)
- MovieListView with filtering/pagination (US-11, US-12)
- MovieDetailView with embedded YouTube trailer (US-13)
- ScreeningListView with date picker (US-14)
- **Visual redesign (bonus):** cinema-city style (PR #18) + auth-pages redesign (PR #19)
- **Performance pass (US-17):** admin N+1 elimination + comprehensive budget tests

## Stats
- 17 user stories completed
- ~150+ tests
- Coverage ≥80%
EOF
)"
```

- [ ] **Step 5: Memory update — `project_kinomania_bootstrap.md`.** Otwórz `C:\Users\barte\.claude\projects\C--Users-barte-PycharmProjects-cinema-booking-system\memory\project_kinomania_bootstrap.md` i zaktualizuj:

Stary header (linia 11):
```
**Current state (2026-05-21):** **M1 (`v0.1.0`) COMPLETE ✅; M2 (Catalog web, `v0.2.0`) in progress — 7/8 US done.** Cały M1 (US-01..US-09) + US-10, US-15, US-16, US-11, US-13, US-12, US-14 zmergowane. Tylko **US-17 (performance pass, NFR)** zostaje przed cut `v0.2.0`.
```

Nowy header:
```
**Current state (post-2026-05-21):** **M1 (`v0.1.0`) + M2 (`v0.2.0`) COMPLETE ✅✅.** Cały M1 (US-01..US-09) + cały M2 (US-10..US-17) zmergowane. Tags `v0.1.0` + `v0.2.0` opublikowane. Następny milestone: **M3 — Booking web + Stripe (`v0.3.0`)**, 11 US (US-18..US-28).
```

Usuń "M1 wykończenie outstanding" sekcję (linia 13) — `v0.1.0` tag już jest.

Dodaj krótką notatkę o US-17:
```
**US-17 (perf pass, merged ...)** wyeliminowało N+1 w admin (US-15) przez `get_queryset` override z `annotate(Count(...))` we wszystkich 5 ModelAdmin (`GenreAdmin`/`HallAdmin`/`ActorAdmin`/`DirectorAdmin` po 1 N+1 helper każdy + `MovieAdmin` z 2 N+1 helperami + `prefetch_related("genres")`). Bonus: sortable count columns via `@admin.display(ordering="_<field>")`. 11 nowych budget testów (5 admin + 6 public extensions). `tests/cinema/test_admin_query_budgets.py` jako nowy moduł z lokalnym `admin_client` fixture. `tests/cinema/test_admin.py` zaktualizowane: ~11 istniejących helper testów teraz pull przez `ma.get_queryset(RequestFactory().get("/admin/"))`. **Dev pitfall #7 (admin display helper N+1):** `@admin.display` helpery które robią `obj.<rel>.count()` lub `obj.<m2m>.values_list().order_by()` na model instance ZAWSZE są N+1 — Django ModelAdmin domyślnie nie aplikuje prefetch/annotate na changelist queryset. Każdy ModelAdmin z count/list helperem musi mieć `get_queryset` override.
```

- [ ] **Step 6: Create `.Claude/m3_planning.md`** (analog do `m2_planning.md`) jako session-start brief dla M3. Skopiuj structure z `m2_planning.md`, zaktualizuj:
- Milestone: M3 — Booking web + Stripe (`v0.3.0`)
- US: US-18..US-28 (11 user stories)
- Predecessor: M2 ✅ complete
- Suggested ordering (przykład):
  1. US-18 — Booking model (FK to Screening, seats_count, status, etc.)
  2. US-19 — Reservation form/view (anon-friendly?)
  3. US-20 — "Zarezerwuj" wire-up on MovieDetail + ScreeningList
  4. US-21..28 — Stripe integration, payment flow, webhook handling

**Important:** ten task wymaga brainstormingu M3 — NIE pisz `m3_planning.md` z czubka kapelusza. Best: start nowej sesji z "let's plan M3" i przejdź przez normal brainstorm flow.

- [ ] **Step 7: Verify final state:**

```bash
git tag -l "v0.*"           # → v0.1.0, v0.2.0
git branch -a                # → main + remotes/origin/main
gh release list             # → v0.1.0, v0.2.0 jeśli zrobione
git log --oneline -5
```

---

## Spec coverage check (self-review)

| Sekcja spec | Pokrycie w planie |
|-------------|--------------------|
| §1 Cel / non-goals | Header + Tasks 1-3 (public views) + Tasks 4-8 (admin) + Task 12 (closing M2) |
| §2 Architektura plików | File Structure table + per-task Files headers |
| §3 Verified model fields | Tasks 4-8 use weryfikowane annotate paths (`Count("movies")`, `Count("screening")`, `Count("screenings", distinct=True)`) |
| §4 Refactor patterns | Task 4 (Pattern A — GenreAdmin), Tasks 5-7 (Pattern A copies), Task 8 (Pattern B — MovieAdmin with prefetch) |
| §5 Per-target plan testów | Tasks 1-3 (public) + Tasks 4-8 (admin) + admin_client fixture w Task 4 Step 1 |
| §6 TDD-style perf workflow | Każdy admin task ma steps 1 (test) → 2 (run/baseline) → 3 (refactor) → 4 (re-run/tighten) |
| §7 Testowanie | Każdy task ma run + commit; Task 11 ma full sweep + smoke |
| §8 Definition of Done | Task 11 Step 1-3 (pytest+cov, lint, smoke); plus PR body DoD checklist w Task 11 Step 5 |
| §9 Closing M2 | Task 12 (post-merge) |
| §10 Risks | Pokryte przez per-task care: `distinct=True` w Task 8, baseline measurement w Tasks 4-8 Step 2 |
| §11 Decisions data-driven | admin_client lokalny w Task 4; caps mierzone w Steps 2/4 każdego admin task; tighten public w Task 9 |

Brak gaps. Plan domknięty.
