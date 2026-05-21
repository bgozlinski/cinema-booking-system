# Design — KinoMania: MovieList filtering + search (US-12 / FR-02)

**Data:** 2026-05-21
**Status:** Approved (brainstorming session — bartek + Claude Opus 4.7)
**Powiązany US:** US-12 (`feat/FR-02-movie-list-filtering`)
**Powiązany FR:** FR-02 (Filtrowanie i wyszukiwanie)
**Cel:** Specyfikacja rozbudowy `MovieListView` z US-11 o trzy filtry przekazywane przez GET — `q` (title `icontains`), `genre` (single dropdown), `date` (date picker, single calendar day). Filtry kombinują się intersekcyjnie. Brak wyników po filtrze pokazuje osobny copy + reset link. Paginacja zachowuje query params. Dokument NIE zawiera planu — ten powstanie przez `superpowers:writing-plans`.

---

## Spis treści
1. [Decyzje brainstorming](#1-decyzje-brainstorming)
2. [Form](#2-form)
3. [View](#3-view)
4. [Template + UX](#4-template--ux)
5. [Strategia testów](#5-strategia-testów)
6. [Zmiany w plikach](#6-zmiany-w-plikach)
7. [Plan commitów](#7-plan-commitów)
8. [Out of scope (follow-up)](#8-out-of-scope-follow-up)

---

## 1. Decyzje brainstorming

| # | Pytanie | Decyzja |
|---|---|---|
| Q1 | **Rendering** (form vs htmx vs raw GET) | Pure Django `Form` w `apps/cinema/forms.py`, GET submit, full reload. Zero JS, URL shareable, standard Django pattern. |
| Q2 | **Genre filter UI** (dropdown vs multiselect) | Single dropdown (`ModelChoiceField` + `empty_label="Wszystkie gatunki"`). URL: `?genre=<id>`. Multiselect deferred jako future enhancement. |
| Q3 | **Date filter semantics** | Movies z screening ON dokładnie tej dacie — `start_time` ∈ `[date 00:00, date+1d 00:00)` w timezone Europe/Warsaw. Inkluzywne na 00:00, ekskluzywne na 24:00 następnego dnia. Inny semantically od US-11 default future-only — tu zawęża result set, nie annotation. |

**Niedyskutowane (defaults dziedziczone z M1/US-11):**
- Polish copy (mirror US-11).
- Bootstrap 5.3.3 CDN (Form widgets z `class="form-control"`/`form-select`).
- Sort order: `next_screening_at` ASC (unchanged from US-11).
- Paginacja 12/strona (unchanged from US-11).

---

## 2. Form

### 2.1 Lokalizacja + sygnatura

`apps/cinema/forms.py` (NEW):

```python
from django import forms

from apps.cinema.models import Genre


class MovieFilterForm(forms.Form):
    q = forms.CharField(
        required=False, max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Tytuł filmu...", "class": "form-control"}),
        label="",
    )
    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all(), required=False,
        empty_label="Wszystkie gatunki",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="",
    )
```

### 2.2 Decyzje

- **`required=False` wszędzie** — każda kombinacja empty/present jest valid query. Nigdy nie wyrzuca form errors.
- **`max_length=200`** na `q` — defensywne ograniczenie, brak wartości UX powyżej.
- **`empty_label="Wszystkie gatunki"`** — renderuje `<option value="">Wszystkie gatunki</option>` jako default. Polish copy.
- **HTML5 `<input type="date">`** — natywny date picker w przeglądarce. Zero JS. Wartość zwracana jako `YYYY-MM-DD` string, Django `DateField` koerce'uje do `datetime.date`.
- **Brak `clean()` override** — nie ma cross-field validation. Każdy filter niezależny.
- **`label=""`** — visible label nie potrzebny przy placeholder + ikonografii Bootstrap. Jeśli a11y wymaga, można dodać aria-label przez `attrs={"aria-label": "..."}`.

---

## 3. View

### 3.1 `MovieListView.get_queryset()` extended

```python
import datetime
from datetime import time, timedelta

from django.db.models import Min, Q
from django.utils import timezone
from django.views.generic import ListView

from apps.cinema.forms import MovieFilterForm
from apps.cinema.models import Movie


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
            if date := form.cleaned_data.get("date"):
                day_start = timezone.make_aware(
                    datetime.datetime.combine(date, time.min)
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
```

### 3.2 Decyzje semantyczne

- **`next_screening_at` annotation nadal future-only** — `filter=Q(screenings__start_time__gte=now)` w `Min` jest niezmieniony. Annotation reprezentuje "soonest future screening" niezależnie od `?date=` filtra.
- **Date filter zawęża result set, nie annotation** — `qs.filter(screenings__start_time__gte=day_start, screenings__start_time__lt=day_end)`. Po dodaniu, queryset robi JOIN do Screening; `.distinct()` zapobiega duplikatom gdy movie ma >1 screening tego dnia.
- **`.distinct()` tylko w branch'u date** — genre `filter(genres=genre)` używa M2M ale jako single FK lookup → brak duplikatów; `q` filter też brak join'u.
- **Walrus `if val := form.cleaned_data.get(...)`** — applies filter tylko gdy wartość truthy. Pusty `q=""` skipowany, `None` genre skipowany.
- **`form.is_valid()` w main path** — jeśli form invalid (np. malformed `?genre=99999` lub `?date=not-a-date`), żaden filter nie aplikuje → wszystkie movies. Świadomy choice: silently ignore invalid input zamiast 400 / error.
- **Sort order unchanged** — `order_by("next_screening_at")` zachowane.

### 3.3 Day-window time math

```python
day_start = timezone.make_aware(datetime.datetime.combine(date, time.min))
# = aware datetime YYYY-MM-DD 00:00:00 Europe/Warsaw
day_end = day_start + timedelta(days=1)
# = aware datetime (YYYY-MM-DD + 1) 00:00:00 Europe/Warsaw
# Filter: start_time__gte=day_start, start_time__lt=day_end
# Inclusive at 00:00, exclusive at next day's 00:00. Covers 23:59:59.999999.
```

`timezone.make_aware` używa `settings.TIME_ZONE` (Europe/Warsaw) — DST-safe.

---

## 4. Template + UX

### 4.1 Filter bar

Wstawiony do `templates/cinema/movie_list.html` zaraz po `<h1>Repertuar</h1>`:

```html
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
```

**Decyzje:**
- `role="search"` na form — a11y region landmark.
- Reset (×) link gated by `{% if request.GET %}` — pokazuje się tylko gdy filtry aktywne. Goes to `/movies/` (drops wszystkie query params, więc redirect do canonical canonical URL bez filter state).
- `flex-grow-1` na submit — gdy reset link absent, button bierze pełną szerokość.
- Submit on Enter w `q` field — default browser, no extra wiring.
- Brak "Apply on change" — pure submit-button (no JS).

### 4.2 Pagination preservation

Replace istniejące pagination links z querystring-preserving wersją:

```html
{% if page_obj.has_previous %}
  <li class="page-item">
    <a class="page-link" href="?{% querystring page=page_obj.previous_page_number %}">&laquo;</a>
  </li>
{% endif %}
...
{% if page_obj.has_next %}
  <li class="page-item">
    <a class="page-link" href="?{% querystring page=page_obj.next_page_number %}">&raquo;</a>
  </li>
{% endif %}
```

**Wymagana wersja:** Django **≥ 5.1** (built-in `{% querystring %}` tag). Repo na Django 6 → OK.

Effect: paginacja preserves filters (`?q=star&page=2` zamiast tylko `?page=2`). Filter form changes generują fresh URL bez `page=` → naturalnie page=1 (desired UX).

### 4.3 Empty-state copy (dwie wariacje)

```html
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
```

**Dwa semantically różne "no results" cases:**
- Brak movies anywhere z future screenings (US-11 case) → "Wróć wkrótce".
- Filter combination matchuje 0 movies → "Wyczyść filtry" + reset link.

`request.GET` truthy iff jakikolwiek query param obecny (Django `QueryDict` jest "truthy if non-empty").

---

## 5. Strategia testów

### 5.1 Lokalizacje

- `tests/cinema/test_movie_filter_form.py` (~6 form unit tests, NEW).
- `tests/cinema/test_movie_list.py` — rozbudowa o `TestFilters` + empty-state variants + pagination preservation (~13 new tests).

### 5.2 `MovieFilterForm` unit tests

| Wejście | Oczekiwany wynik |
|---|---|
| `{}` (empty) | valid; `q == ""`, `genre is None`, `date is None` |
| `{"q": "Matrix"}` | valid; `cleaned_data["q"] == "Matrix"` |
| `{"genre": <genre.pk>}` | valid; `cleaned_data["genre"] == genre` |
| `{"date": "2026-05-23"}` | valid; `cleaned_data["date"] == date(2026, 5, 23)` |
| `{"date": "not-a-date"}` | invalid; `"date" in form.errors` |
| `{"genre": "99999"}` (non-existent pk) | invalid; `"genre" in form.errors` |

### 5.3 Filter integration tests (`TestFilters` w `test_movie_list.py`)

| Test | Setup | Assert |
|---|---|---|
| `test_q_filter_matches_icontains` | "The Matrix" + future screening, "Other" + future screening; `GET /?q=matrix` | tylko "The Matrix" w `context["movies"]` |
| `test_q_filter_is_case_insensitive` | "Inception" + future; `GET /?q=INCEPTION` | "Inception" present |
| `test_q_filter_empty_string_returns_all` | 2 movies; `GET /?q=` | obie present |
| `test_genre_filter_narrows_results` | movie_drama (Drama) + future, movie_action (Action) + future; `GET /?genre=<drama.pk>` | tylko movie_drama |
| `test_genre_filter_invalid_pk_returns_all` | 2 movies; `GET /?genre=99999` | obie present (form invalid → filter skipped) |
| `test_date_filter_matches_screening_on_that_day` | movie A: screening tomorrow 18:00; movie B: screening day after 18:00; `GET /?date=<tomorrow>` | tylko A |
| `test_date_filter_boundary_inclusive_at_midnight` | movie X: screening at 00:00 of date; `GET /?date=<date>` | X present |
| `test_date_filter_boundary_inclusive_at_end_of_day` | movie X: screening at 23:59 of date; `GET /?date=<date>` | X present |
| `test_date_filter_excludes_next_day` | movie X: screening at 00:00 NEXT day; `GET /?date=<date>` | X NOT present |
| `test_combined_filters_intersect` | movies seeded across genre + date axes; `GET /?q=...&genre=...&date=...` | tylko movie matching all three |
| `test_filter_form_in_context` | `GET /` | `response.context["filter_form"]` instance of `MovieFilterForm` |
| `test_filter_form_preserves_submitted_values` | `GET /?q=star&date=2026-05-23` | rendered HTML zawiera `value="star"` i `value="2026-05-23"` |

### 5.4 Reset link + empty-state variants

| Test | Setup | Assert |
|---|---|---|
| `test_reset_link_hidden_when_no_filters_active` | `GET /` | brak `Wyczyść filtry` w HTML |
| `test_reset_link_visible_when_filters_active` | `GET /?q=xyz` | `Wyczyść filtry` + `href="/movies/"` w HTML |
| `test_filter_empty_state_copy_when_no_match` | movies exist, brak match `?q=zzzzzz` | "Brak filmów pasujących" alert + reset link; **brak** "Wróć wkrótce" |
| `test_no_screenings_empty_state_copy_when_no_filters_no_movies` | 0 movies, `GET /` | "Wróć wkrótce"; **brak** "Brak filmów pasujących" |

### 5.5 Pagination + filter preservation

- `test_filter_pagination_preserves_query_params` — 13 movies wszystkie matching `?q=common`; `GET /?q=common`; assert pagination block zawiera `q=common` + `page=2` (substring check, order-insensitive: assert both `q=common` AND `page=2` w pagination block).

### 5.6 N+1 budget

Existing `assertMaxNumQueries(4)` w `TestQueryBudget`. Dodanie filter form do context_data dorzuca jedną query (Genre dropdown queryset evaluation). **Bump cap do 5** w istniejącym teście. Add comment explaining bump.

---

## 6. Zmiany w plikach

```
apps/cinema/
├── forms.py                                  ★ NEW — MovieFilterForm
└── views.py                                  ✎ extend MovieListView.get_queryset() + context

templates/cinema/
└── movie_list.html                           ✎ + filter bar + empty-state branching + querystring pagination

tests/cinema/
├── test_movie_filter_form.py                 ★ NEW (~6 form unit tests)
└── test_movie_list.py                        ✎ + TestFilters + empty-state variants + pagination preservation (~13 new); bump N+1 cap 4 → 5

.Claude/backlog.md                            ✎ status board (Task 1 + final)
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress (6/8)
```

**Brak zmian:** `settings/`, `apps/cinema/admin.py`, `apps/cinema/models.py`, dependency list, migrations.

---

## 7. Plan commitów

1. `docs(M2): add design spec + plan for US-12 + mark in progress`
2. `feat(FR-02): MovieFilterForm with q/genre/date fields` (forms.py + form unit tests)
3. `feat(FR-02): wire filter form into MovieListView queryset` (view + integration tests)
4. `feat(FR-02): filter bar + empty-state branching + querystring pagination` (template + render tests + N+1 cap bump)
5. `docs(M2): mark US-12 done, queue US-14 next`

**Branch:** `feat/FR-02-movie-list-filtering`.

---

## 8. Out of scope (follow-up)

| Feature | US/why deferred |
|---|---|
| Multiselect genre filter | Q2 wybrał dropdown. Future enhancement (no blocker). |
| Full-text search (`to_tsvector` PostgreSQL) | M2 ships `icontains`; full-text to **US-17** lub future polish per `m2_planning.md` Risk #3. |
| htmx live filtering | Q1 wybrał pure-Django. Out of M2 entirely. |
| "Sort by" controls | Out of scope; sort stays by `next_screening_at` ASC. |
| Daily schedule view (`/screenings/?date=...`) | **US-14** (FR-04) — different view, different layout (grouped by movie, not paginated). |
| Performance pass (`Prefetch` with custom QS, query budget tightening) | **US-17** (NFR). |
| Hardening: rate limit, query-string length cap | `q` ma już `max_length=200`. No DoS concerns at scale. |
