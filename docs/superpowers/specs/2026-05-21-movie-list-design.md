# Design — KinoMania: MovieList view (US-11 / FR-01)

**Data:** 2026-05-21
**Status:** Approved (brainstorming session — bartek + Claude Opus 4.7)
**Powiązany US:** US-11 (`feat/FR-01-movie-list`)
**Powiązany FR:** FR-01 (Strona główna / Repertuar)
**Cel:** Specyfikacja pierwszej user-facing M2 view — listy filmów z paginacją 12/strona, sortowanej po najbliższym przyszłym seansie. Strona zastępuje obecny placeholder `HomeView` i ustanawia wzorzec template + URL + paginacja dla kolejnych M2 widoków (US-12/13/14). Dokument NIE zawiera planu implementacyjnego — ten powstanie przez `superpowers:writing-plans` po akceptacji specu.

---

## Spis treści
1. [Decyzje brainstorming](#1-decyzje-brainstorming)
2. [Architektura](#2-architektura)
3. [Queryset](#3-queryset)
4. [Template](#4-template)
5. [Strategia testów](#5-strategia-testów)
6. [Zmiany w plikach](#6-zmiany-w-plikach)
7. [Plan commitów](#7-plan-commitów)
8. [Out of scope (follow-up)](#8-out-of-scope-follow-up)

---

## 1. Decyzje brainstorming

| # | Pytanie | Decyzja |
|---|---|---|
| Q1 | **URL strategy dla `/` vs `/movies/`** (FR-01 mówi „alias") | Drop `HomeView` całkowicie. `MovieListView` zarejestrowane pod oboma path'ami — `path("")` z `name="home"` (legacy alias dla M1 navbar) + `path("movies/")` z `name="movie_list"` (canonical, używany w nowym kodzie). Reverse z obu nazw działa; brak redirectu. |
| Q2 | **Sort order** (spec nie precyzuje) | Po `next_screening_at` ascending — co jest najbliżej w czasie, wyżej. Wymaga annotation z `Min('screenings__start_time', filter=Q(screenings__start_time__gte=now))`. Annotation potrzebna i tak (karta pokazuje datę), więc darmowy bonus. |
| Q3 | **Grid density** (Bootstrap row-cols) | `row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-xl-4 g-4`. Na desktop xl: 4 kolumny × 3 rzędy = 12/strona pasuje 1:1 do paginacji. |
| Q4 | **Placeholder gdy `movie.poster=""`** | Inline `<div>` z `bg-light` + 🎬 emoji w `font-size: 3rem` (mirror navbar brand). Zero CDN/static assets. Wszystkie 20 movies z US-16 seed mają blank poster, więc placeholder MUSI wyglądać OK. |

**Niedyskutowane (defaults dziedziczone z M1):**
- Język copy: polski (mirror `templates/cinema/home.html` z US-09).
- Bootstrap 5.3.3 CDN (już w `base.html`).
- Brak Bootstrap Icons — używamy emoji bo i tak nie ma w `base.html` (decyzja konsystencji z navbar brand).

---

## 2. Architektura

### 2.1 View

`apps/cinema/views.py` — `HomeView(TemplateView)` zostaje **usunięte całkowicie** i zastąpione przez `MovieListView(ListView)`.

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

### 2.2 URLs

`apps/cinema/urls.py`:

```python
from django.urls import path

from apps.cinema.views import MovieListView

app_name = "cinema"

urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
]
```

**Migracja URL names:**
- `cinema:home` — zachowane jako alias dla legacy M1 kodu (navbar `templates/base.html:20` używa `{% url 'cinema:home' %}` — działa bez zmiany).
- `cinema:movie_list` — nowa nazwa, **preferowana** w nowym kodzie + testach.
- Po US-13/14 navbar może zostać przepięty z `cinema:home` na `cinema:movie_list` — kosmetyczne, nie blokuje.

### 2.3 Brak login wall

`MovieListView` jest publiczne (anon + auth → 200). Per FR-01 „Dostępne dla wszystkich". Brak `LoginRequiredMixin`, brak `dispatch` overrides.

---

## 3. Queryset

### 3.1 Annotation: `next_screening_at`

```python
Min("screenings__start_time", filter=Q(screenings__start_time__gte=now))
```

- `Min(...)` z embedded `filter=Q(...)` ignoruje przeszłe seanse **wewnątrz agregatu**, NIE jako outer WHERE.
- Bez `filter=Q(...)` agregat liczyłby wszystkie seanse (też przeszłe) → `next_screening_at` mogłoby być datą sprzed dziś. Subtelny bug — pokryty regresją w testach (§5).
- Django ≥ 2.0 obsługuje `filter=` w agregatach jako `FILTER (WHERE ...)` w SQL.

### 3.2 Filter: `next_screening_at__isnull=False`

Po annotation, movie z brakiem przyszłych seansów ma `next_screening_at IS NULL`. Filtrowanie `isnull=False` jest równoważne FR-01 wymaganiu „co najmniej jeden Screening z start_time >= today". Wyrażone jako `HAVING` w SQL (efektywne, single round trip).

### 3.3 `prefetch_related("genres")`

Bez tego: render 12 kart × N+1 query per `movie.genres.all` w template = 13 queries. Z prefetch: 2 queries (movies + genres). US-17 może dorzucić kolejne prefetche jeśli profile pokaże inne N+1.

### 3.4 Ordering

`order_by("next_screening_at")` ASC. Movies grane dziś wieczorem przed movies grane w przyszłym tygodniu.

---

## 4. Template

### 4.1 Lokalizacja

- **Nowy:** `templates/cinema/movie_list.html`
- **Usunięty:** `templates/cinema/home.html` (M1 placeholder; `MovieListView` go nie używa)

### 4.2 Struktura

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

### 4.3 Decyzje stylistyczne

- **`aspect-ratio: 2/3`** na poster + placeholder — uniform card height bez względu na obecność postera.
- **`mt-auto` na button** — `card-body` ma `d-flex flex-column`, więc `mt-auto` pina button do dołu karty (długość tytułu/genre nie psuje alignmentu).
- **"Szczegóły" disabled** — `MovieDetailView` powstaje w US-13. US-13 commit drop'uje klasę `disabled` + dodaje `href="{% url 'cinema:movie_detail' movie.pk %}"`. Cleaner niż fake anchor `href="#"`.
- **`aria-hidden="true"`** na emoji placeholder — czytniki ekranowe nie ogłaszają "filmu 🎬 plakat zastępczy".
- **Polish copy** — mirror M1 (np. `home.html`, `accounts/*.html`).

---

## 5. Strategia testów

### 5.1 Lokalizacja

`tests/cinema/test_movie_list.py` (~15 testów).

### 5.2 Pokrycie

| Obszar | Testy |
|---|---|
| **Routing** | `GET /` → 200; `GET /movies/` → 200; `reverse("cinema:home")` == `/`; `reverse("cinema:movie_list")` == `/movies/`; oba używają `cinema/movie_list.html`. |
| **Queryset visibility** | Movie z future screening → widoczne; movie z tylko past screening → ukryte; movie bez screenings → ukryte; movie z past+future → widoczne, `next_screening_at` = ta przyszła (regresja na bug z `Min` bez `filter=Q(...)`). |
| **Sort order** | 3 movies z future screenings na D+1, D+3, D+2 → context_data['movies'] zwraca D+1, D+2, D+3 w tej kolejności. |
| **Paginacja** | 13 movies → page 1 ma 12 cards; `?page=2` ma 1; `?page=3` → 404; paginacja UI renderowana tylko gdy >12 movies. |
| **Card content** | Tytuł, wszystkie nazwy genres jako badges, sformatowana data `d.m.Y H:i`, button "Szczegóły"; movie z `poster=""` → fallback `🎬` div renderowany; movie z uploaded posterem → `<img src="...">` w HTML. |
| **Anon vs auth** | Oba dostają 200, brak loginu wymaganego. |
| **N+1 / prefetch sanity** | `assertNumQueries(<=4)` na 12-card page. Egzekwowanie `prefetch_related` żeby US-17 startował z czystej bazy. |
| **Empty state** | Brak movies z przyszłymi seansami → komunikat "Aktualnie brak filmów..." widoczny, brak `.row.row-cols-*`. |

### 5.3 Fixtures + factories

- `MovieFactory`, `GenreFactory`, `ScreeningFactory` z `tests/cinema/factories.py` (US-10).
- Dla testów date arithmetic: `timezone.now()` + `timedelta(days=N)`.
- Dla testu posteru: `SimpleUploadedFile` + bytes z `PNG_1X1` (reuse pattern z `tests/cinema/test_admin.py`).

### 5.4 Style

Pytest functional tests, `@pytest.mark.django_db`. Mirror `tests/cinema/test_seed_db.py` (call_command-style) i `tests/cinema/test_admin.py` (registry inspection-style) — pytest functional, nie klasowy.

---

## 6. Zmiany w plikach

```
apps/cinema/views.py                          ✎ REPLACE HomeView → MovieListView
apps/cinema/urls.py                           ✎ + path("movies/") + import MovieListView
templates/cinema/movie_list.html              ★ NEW
templates/cinema/home.html                    ✖ DELETE
tests/cinema/test_movie_list.py               ★ NEW (~15 tests)
tests/cinema/test_home.py                     ✖ DELETE (tests of removed HomeView)
tests/cinema/test_base_template.py            ✎ ↑ jeśli były asercje o tytule "KinoMania — Twoje kino online" (M1 placeholder)
.Claude/backlog.md                            ✎ status board (Task 1 + final)
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress
```

**Wpływ na inne pliki:**
- `templates/base.html` — navbar `{% url 'cinema:home' %}` działa bez zmiany (alias trzymany).
- `apps/cinema/management/commands/seed_db.py` — bez zmiany.
- `apps/cinema/models.py` — bez zmiany.
- `apps/cinema/admin.py` — bez zmiany.

---

## 7. Plan commitów

Pojedynczy logiczny PR, kilka commitów:

1. `docs(M2): add implementation plan for US-11 + mark in progress` — plan + backlog DoR
2. `feat(FR-01): replace HomeView with MovieListView + URL config` — view + urls + tests routing
3. `feat(FR-01): movie_list.html template with card grid + pagination` — template + render tests
4. `feat(FR-01): queryset annotation + sorting tests` — visibility + sort + N+1 tests
5. `chore(FR-01): remove M1 HomeView + home.html template + test_home.py` — cleanup
6. `docs(M2): mark US-11 done, queue US-13 next` — backlog (po wszystkim green)

Branch: **`feat/FR-01-movie-list`** (per backlog konwencja `feat/FR-XX-short-description`).

---

## 8. Out of scope (follow-up)

| Feature | US | Why deferred |
|---|---|---|
| Filtrowanie / search (`?q=`, `?genre=`, `?date=`) | **US-12** (FR-02) | Extends `MovieListView` queryset. Brainstormowane osobno (filter UX decisions). |
| Movie detail page (`/movies/<pk>/`) | **US-13** (FR-03) | "Szczegóły" button czeka `disabled`; US-13 wires href + dropuje klasę. |
| Daily screenings list (`/screenings/?date=...`) | **US-14** (FR-04) | Osobna view, navbar link "Seanse" obecnie `disabled`. |
| Performance pass (`select_related`, query budget) | **US-17** (NFR) | `prefetch_related("genres")` w US-11 jest baseline; US-17 mierzy + dorzuca brakujące. |
| Genre badge color-per-genre | — | Kosmetyczne, post-M2. |
| Responsive `srcset` / lazy loading dla posterów | — | Performance pass z osadzonymi posterami; obecnie wszystkie blank. |
| i18n (`gettext_lazy` na hardcoded polish) | — | Konsystencja z M1; multi-lang to osobny milestone (nie M2..M5). |
| htmx live filtering / infinite scroll | — | M2 ships server-side rendering; htmx to świadoma decyzja na inny milestone. |
