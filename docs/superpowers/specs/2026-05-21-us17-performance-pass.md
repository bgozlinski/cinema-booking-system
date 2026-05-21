# US-17 — Performance pass (M2 last task)

**Data:** 2026-05-21
**Branch (planned):** `perf/FR-01-prefetch` (off `main`)
**Estymata:** S (~2h, faktycznie bliżej M ze względu na admin refactor + 10 testów)
**Powiązane:**
- `.Claude/backlog.md` §2 (M2 table, US-17 entry)
- `.Claude/m2_planning.md` §"Plan directly (no brainstorming needed)" — US-17 "Measure-first, fix-second"
- `apps/cinema/views.py` — public views (US-11/13/14, już zoptymalizowane)
- `apps/cinema/admin.py` — 5 ModelAdminów do refactoringu (US-15)
- `tests/cinema/test_movie_list.py`, `test_movie_detail.py`, `test_screening_list.py` — istniejące `TestQueryBudget` classes

---

## 1. Cel

US-17 to **audit + verification + targeted fix** ostatniego task'a M2 przed cut `v0.2.0`. Cel:

1. **Verification audit** — sprawdzić, że istniejące optymalizacje (`prefetch_related`/`select_related` w US-11/13/14) wytrzymują nowe scenariusze: filtry, paginacja, orphan movie, empty day, big dataset.
2. **Admin N+1 elimination** — wszystkie 5 ModelAdminów (`GenreAdmin`, `HallAdmin`, `ActorAdmin`, `DirectorAdmin`, `MovieAdmin`) mają per-row count helpery (`movies_count`, `screenings_count`, `genres_list`) bez `get_queryset` override → klasyczne N+1 przy `list_per_page=100` (default Django). Refaktor: `annotate` + opcjonalne `prefetch_related` w `get_queryset`.
3. **Tighten where measurable** — istniejące capy public views (5 / 6 / 3) zostały ustawione z bufferem; po szerszym audycie mogą być obniżone do realnego baseline.
4. **Closing M2** — po merge US-17: cut `v0.2.0` tag + (opcjonalne) GitHub release. Dorzucamy też outstanding `v0.1.0` tag na merge commit PR #9 (M1 wykończenie z memory).

### Out of scope

- Stub `Screening.booked_seats_count()` / `available_seats_count()` — to US-18 (M3 real Booking aggregation), bez zmiany sygnatur.
- `django-debug-toolbar` jako trwała dep — explicit odrzucone w brainstormingu (test-driven approach wystarczy).
- Full-text search (Polish `to_tsvector` zamiast `icontains`) — follow-up (US-17b lub M3).
- Caching layer — out of project scope w M2.
- Refactor `Screening.hall` na `related_name="screenings"` — drobna niespójność z `Screening.movie`, ale wymaga migracji i wykracza poza perf. Follow-up (cosmetic refactor PR).

---

## 2. Architektura plików

### Edytowane

```
apps/cinema/admin.py                                  # 5 get_queryset() override + sortable ordering
tests/cinema/test_movie_list.py                       # +3 scenariusze w TestQueryBudget
tests/cinema/test_movie_detail.py                     # +1 scenariusz w TestQueryBudget
tests/cinema/test_screening_list.py                   # +2 scenariusze w TestQueryBudget
.Claude/backlog.md                                    # US-17 → Done, status board update (§7)
```

### Tworzone

```
tests/cinema/test_admin_query_budgets.py              # 5 TestXAdminQueryBudget klas, 1 test each
```

### Stan obecny (zweryfikowane)

| Element | Stan |
|---------|------|
| `apps/cinema/views.py` — `MovieListView` | ✅ `prefetch_related("genres")` aplikowane, cap 5 w teście |
| `apps/cinema/views.py` — `MovieDetailView` | ✅ `prefetch_related("genres","actors","directors")` + `select_related("hall")` na screenings, cap 6 |
| `apps/cinema/views.py` — `ScreeningListView` | ✅ `select_related("movie","hall")` + `prefetch_related("movie__genres")`, cap 3 |
| `apps/cinema/admin.py` — 5 ModelAdmin | ⚠️ Wszystkie 5 ma per-row `.count()` / `.values_list().order_by()` w helperach → klasyczne N+1 |
| `tests/cinema/factories.py` | ✅ Zawiera `GenreFactory`, `HallFactory`, `ActorFactory`, `DirectorFactory`, `MovieFactory`, `ScreeningFactory` |
| `tests/conftest.py` | ❌ Brak — projekt nie używa centralnych shared fixtures (decyzja w fazie planu) |

---

## 3. Verified model fields (kluczowe dla annotate paths)

Z `apps/cinema/models.py`:

| Reverse access | Annotate path | Source |
|----------------|---------------|--------|
| `Genre.movies` | `Count("movies")` | `Movie.genres = M2M(Genre, related_name="movies")` |
| `Actor.movies` | `Count("movies")` | `Movie.actors = M2M(Actor, related_name="movies")` |
| `Director.movies` | `Count("movies")` | `Movie.directors = M2M(Director, related_name="movies")` |
| `Movie.screenings` | `Count("screenings")` | `Screening.movie = FK(Movie, related_name="screenings")` |
| `Hall.screening_set` (default reverse) | `Count("screening")` | `Screening.hall = FK(Hall)` — **brak related_name** |

---

## 4. Refactor patterns w `apps/cinema/admin.py`

### 4.1. Pattern A — simple count annotate (4 z 5 adminów)

Stosowany dla `GenreAdmin`, `HallAdmin`, `ActorAdmin`, `DirectorAdmin`. Każdy ma 1 count helper. Pełny przykład dla `GenreAdmin`:

```python
from django.db.models import Count

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

Variations:
- `HallAdmin`: `annotate(_screenings_count=Count("screening"))` (lowercase model name, brak related_name)
- `ActorAdmin`, `DirectorAdmin`: identyczne jak `GenreAdmin` — `Count("movies")`. `photo_thumbnail` helper pozostaje bez zmian (FieldFile na instance attr, brak query).

### 4.2. Pattern B — count annotate + M2M prefetch (`MovieAdmin`)

`MovieAdmin` ma 2 N+1 helpery (`screenings_count` + `genres_list`) i wymaga obu: annotate dla count + prefetch dla genres list.

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
        names = sorted(g.name for g in obj.genres.all())  # uses prefetch cache
        return ", ".join(names) if names else "—"
```

**Kluczowe decyzje:**

1. **`distinct=True` na `Count`** — `list_filter=("genres",)` w `MovieAdmin` triggeruje M2M JOIN dla filter sidebar dropdown, co bez `distinct` duplikuje wiersze w `Count`. Defensywne.
2. **`genres_list` używa `obj.genres.all()`** — nie `values_list("name", flat=True).order_by("name")` jak obecnie. `values_list` z `order_by` triggeruje **fresh query** mimo `prefetch_related`. Sorted lambda na prefetched list jest free (Python-side).
3. **`ordering="_screenings_count"` w `@admin.display`** — sortable column gratis (UX win).

### 4.3. Skutki uboczne refactoringu

| Skutek | Status |
|--------|--------|
| `genres_list` zmienia źródło danych (`values_list().order_by()` → `sorted` na prefetched) | ✅ wynik identyczny (oba sortowane alfabetycznie) — istniejące testy `TestMovieAdmin` w `test_admin.py` muszą przejść bez zmian |
| Sortable column dla counts | ✅ free UX win, brak regression |
| `obj._movies_count` / `obj._screenings_count` jako private attr name | ✅ Django idiom (`_` prefix sygnalizuje annotate field) |
| Brak zmian w `search_fields` / `list_filter` / `filter_horizontal` | ✅ niezwiązane z perf |

---

## 5. Per-target plan testów

### 5.1. Public view tests — extension (3 pliki, +6 testów)

#### 5.1.1. `tests/cinema/test_movie_list.py::TestQueryBudget`

Istniejący: `test_full_page_uses_bounded_queries` (12 movies × 2 genres, cap **5**).

| Nowy test | Setup | Cap (target) | Reasoning |
|-----------|-------|--------------|-----------|
| `test_with_genre_filter_uses_bounded_queries` | 12 movies (5 z danym genrem), `?genre=<id>` | 5 | Genre filter dodaje WHERE na M2M; prefetch_related trzyma genre data |
| `test_with_date_filter_uses_bounded_queries` | 12 movies (6 playing tomorrow), `?date=<tomorrow>` | 6 | Date filter dodaje JOIN + `.distinct()`; paginator count distinct może = +1 |
| `test_pagination_second_page_uses_bounded_queries` | 30 movies, `?page=2` | 5 | Pagination nie zmienia query count |

#### 5.1.2. `tests/cinema/test_movie_detail.py::TestQueryBudget`

Istniejący: `test_full_page_uses_bounded_queries` (populated movie, cap **6**).

| Nowy test | Setup | Cap (target) |
|-----------|-------|--------------|
| `test_orphan_movie_uses_bounded_queries` | Movie bez screenings/actors/directors/trailer | 6 (prefetch'y odpalają się jako fixed cost mimo empty results) |

#### 5.1.3. `tests/cinema/test_screening_list.py::TestQueryBudget`

Istniejący: `test_full_day_uses_bounded_queries` (5 movies × 3 screenings, cap **3**).

| Nowy test | Setup | Cap (target) |
|-----------|-------|--------------|
| `test_empty_day_uses_bounded_queries` | 0 screenings na dany dzień | 2 (brak prefetch, tylko Screening + messages baseline) |
| `test_big_dataset_uses_bounded_queries` | 20 movies × 5 screenings | 3 (prefetch nie skaluje się z N) |

### 5.2. Admin budget tests — new file (1 plik, +5 testów)

`tests/cinema/test_admin_query_budgets.py` — nowy moduł.

Każda klasa: 1 test (`test_changelist_uses_bounded_queries`) hitujący `reverse("admin:cinema_<model>_changelist")` przez admin_client, sprawdzający budget po refactorze.

| Klasa testowa | Setup | Cap przed (estimate) | Cap po refactorze (target) |
|---------------|-------|----------------------|----------------------------|
| `TestGenreAdminQueryBudget` | 12 genres × ~3 movies each | ~22 (12 N+1 + ~10 admin baseline) | ~12 |
| `TestHallAdminQueryBudget` | 12 halls × ~2 screenings each | ~22 | ~12 |
| `TestActorAdminQueryBudget` | 12 actors × ~2 movies each | ~22 | ~12 |
| `TestDirectorAdminQueryBudget` | 12 directors × ~2 movies each | ~22 | ~12 |
| `TestMovieAdminQueryBudget` | 12 movies × ~3 genres × ~2 screenings | ~34 (12+12 N+1 + ~10 admin baseline) | ~15 |

Cap "target" to **educated guess**; faktyczne cap (cap = actual + 1 buffer) ustalimy data-driven w fazie implementacji.

### 5.3. admin_client fixture

Brak `tests/conftest.py` w projekcie. Decyzja w fazie planu:
- **Opcja A:** lokalny `@pytest.fixture admin_client` w `test_admin_query_budgets.py` (najmniejsza praca; OK jeśli używany w jednym pliku)
- **Opcja B:** centralny `tests/conftest.py` z `admin_client` jako shared infra (lepsze dla przyszłych admin testów np. US-28 booking admin)

Plan dokona wyboru — domyślnie A, chyba że audyt pokaże planowane re-use.

Pattern (przykład):

```python
import pytest
from django.urls import reverse
from tests.accounts.factories import UserFactory
from tests.cinema.factories import GenreFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    return client


class TestGenreAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        for _ in range(12):
            GenreFactory()
        url = reverse("admin:cinema_genre_changelist")
        with django_assert_max_num_queries(<CAP>):
            response = admin_client.get(url)
        assert response.status_code == 200
```

---

## 6. TDD-style perf workflow (per target)

Dla każdego z 8 targetów (3 public extensions + 5 admin):

1. **Pisanie testu** — `assertNumQueries(cap)` z target cap (educated guess)
2. **Run** — `pytest -x tests/cinema/test_X.py::TestY::test_Z -v`
3. **Fail (over budget)**:
   - Admin: refactor `admin.py` (annotate / prefetch), re-run
   - Public view: investigate (template lazy access? form widget query?), fix, re-run
4. **Pass z headroom** — tighten cap (cap = actual + 1 buffer)
5. **Pass** — commit test + (jeśli applicable) refactor osobno

---

## 7. Testowanie (regression + new)

### Regresja

Wszystkie istniejące testy muszą przejść bez zmian:
- `tests/cinema/test_admin.py` (34 testy) — sprawdza `admin.site._registry`, `list_display`, `search_fields`, helpers behaviour. **Po refactorze**: `movies_count` / `screenings_count` zwracają teraz `obj._<name>_count` zamiast `obj.<rel>.count()`. **Istniejące testy** `test_movies_count_zero_when_no_movies`, `test_screenings_count_with_X_screenings` etc. wywołują helpery na model instances **bez** przejścia przez admin queryset — przed annotate `obj._movies_count` nie istnieje, więc helper crashes.

  **Mitigation:** każdy test po refactorze musi:
  - albo wywołać helper przez admin queryset (`ma.get_queryset(request).first()`)
  - albo zaktualizować assertion na nowy access pattern

  **Lista testów `test_admin.py` do potencjalnej aktualizacji** (data-driven w plan):
  - `TestGenreAdmin::test_movies_count_zero_when_no_movies`
  - `TestGenreAdmin::test_movies_count_with_X_movies`
  - `TestHallAdmin::test_screenings_count_*`
  - `TestActorAdmin::test_movies_count_*`
  - `TestDirectorAdmin::test_movies_count_*`
  - `TestMovieAdmin::test_screenings_count_*`
  - `TestMovieAdmin::test_genres_list_*` — `genres_list` zmienia implementację (sorted Python vs `values_list().order_by()`), wynik identyczny ale source-of-truth się zmienia

  Plan dorzuci adapter (np. `from django.test import RequestFactory`, mock request, `ma.get_queryset(request)`) jako helper.

- `tests/cinema/test_movie_list.py`, `test_movie_detail.py`, `test_screening_list.py` — istniejące `TestQueryBudget` capy nie zmieniają się (chyba że tighten po measurement)
- Pozostałe regression testy (template renders, redirects, etc.) — bez wpływu

### Nowe testy

- 6 nowych metod w istniejących `TestQueryBudget` (public views)
- 5 nowych klas w `tests/cinema/test_admin_query_budgets.py` (admin)

### Manual smoke (opcjonalne, po implementacji)

1. `poetry run python manage.py seed_db --flush` — fresh DB
2. `poetry run python manage.py runserver`
3. Login na `/admin/` jako superuser (`createsuperuser`)
4. Otwórz `/admin/cinema/movie/` — sprawdź:
   - Page renderuje się szybciej (~100ms vs ~500ms przed)
   - `screenings` column ma sortable arrows (klik → ↑/↓)
5. Otwórz `/admin/cinema/genre/`, `/admin/cinema/hall/`, `/admin/cinema/actor/`, `/admin/cinema/director/` — sortable counts działają

---

## 8. Definition of Done

- [ ] **AC met:** wszystkie 11 budget testów green (6 public extensions + 5 admin new)
- [ ] **N+1 elimination:** `admin.py` zrefaktorowany — wszystkie 5 ModelAdmin używa `get_queryset` z `annotate` / `prefetch_related`
- [ ] **Cap documentation:** każdy nowy test ma docstring tłumaczący skąd cap
- [ ] **Tighten check:** istniejące capy 5/6/3 sprawdzone na headroom; tighten jeśli measurement pozwala (z update test komentarzy)
- [ ] **Sortable columns bonus:** każdy annotate ma `ordering="_<field>"` w `@admin.display`
- [ ] **Regression testy `test_admin.py` przechodzą** — istniejące helpery testy zaktualizowane do nowego access pattern (przez admin queryset)
- [ ] **Tests green:** `pytest --cov` zielone, coverage ≥80%
- [ ] **Quality gates:** `ruff check`, `ruff format --check`, `mypy` — bez błędów
- [ ] **Manualne smoke:** admin changelists renderują się + sortable counts
- [ ] **Bez nowych migracji** (US-17 to pure-Python perf)
- [ ] **Bez nowych dependencies**
- [ ] **`backlog.md` updated:** US-17 → Done w status board (§7)

---

## 9. Closing M2 — `v0.2.0` cut (post-US-17 merge)

Po merge US-17 PR do main:

1. **Outstanding M1 tag** (z `project_kinomania_bootstrap.md`):
   ```bash
   # Tag na merge commit PR #9 (M1 close — sprawdzić hash przez `git log --grep="Merge pull request #9"`)
   git tag -a v0.1.0 <merge-commit-sha> -m "M1 — Foundation (US-01..US-09)"
   git push origin v0.1.0
   ```
   Opcjonalnie: `gh release create v0.1.0 --title "v0.1.0 — Foundation"`.

2. **M2 close — `v0.2.0` tag:**
   ```bash
   git checkout main && git pull
   git tag -a v0.2.0 -m "M2 — Catalog web (US-10..US-17)"
   git push origin v0.2.0
   ```
   Opcjonalnie: `gh release create v0.2.0 --title "v0.2.0 — Catalog web" --notes-from-tag` (lub ręcznie z `git log v0.1.0..v0.2.0 --oneline`).

3. **Status update:** `.Claude/backlog.md` §7 — US-17 → Done; przygotuj sekcję na M3 (US-18..US-28).

4. **(Optional) Memory update:** `project_kinomania_bootstrap.md` — odzwierciedl `v0.2.0` release + M3 transition; usuń outstanding M1 tag note.

5. **M3 transition:** create `.Claude/m3_planning.md` (analog do `m2_planning.md`) jako session-start brief dla M3 (`Booking web + Stripe`, 11 US).

---

## 10. Risks

1. **`Count(distinct=True)` overhead** — niewielki perf cost vs safety; używamy defensywnie w `MovieAdmin` ze względu na `list_filter=("genres",)` JOIN.
2. **Admin baseline queries** — Django admin robi ~8-10 queries baseline (permissions check, log_entries, session, paginator count, filter sidebar populate). Caps będą **N+constant**, nie absolute small numbers — to oczekiwane.
3. **Test harness queries** — pytest-django może dodawać 0-2 queries per request (savepoint, fixtures). Buffer +1 w każdym cap (matching obecny pattern w istniejących `TestQueryBudget`).
4. **Existing `test_admin.py` tests breakage** — helpery `movies_count` / `screenings_count` po refactorze czytają `obj._<name>_count` zamiast `obj.<rel>.count()`; istniejące testy które wywołują helper na model instance crashes. **Mitigation:** plan dorzuca adapter (mock request → `ma.get_queryset(request)`) lub aktualizuje testy.
5. **Migration absence** — US-17 nie wymaga zmian models (zero migracji). Risk: ktoś (lub przyszły US) doda field — niezwiązane z US-17.
6. **`Screening.hall` related_name inconsistency** — explicit out-of-scope (cosmetic refactor follow-up).

---

## 11. Decyzje data-driven (do rozstrzygnięcia w plan)

1. **admin_client fixture location** — central conftest vs lokalny per-file (default lokalny, chyba że plan wykryje re-use)
2. **Exact caps** — target caps w §5.1 i §5.2 to educated guesses; faktyczne caps = `<actual after refactor> + 1 buffer` dostają measurement w plan/impl
3. **Tighten obecnych capów public views** — tylko jeśli measurement pokaże headroom; nie a priori
4. **`test_admin.py` adapter pattern** — `RequestFactory` mock vs `Client` HTTP (dependent na ile testów wymaga aktualizacji)
