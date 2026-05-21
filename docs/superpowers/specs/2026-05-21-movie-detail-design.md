# Design — KinoMania: MovieDetail view + embedded trailer (US-13 / FR-03)

**Data:** 2026-05-21
**Status:** Approved (brainstorming session — bartek + Claude Opus 4.7)
**Powiązany US:** US-13 (`feat/FR-03-movie-detail`)
**Powiązany FR:** FR-03 (Strona szczegółów filmu)
**Cel:** Specyfikacja drugiego user-facing M2 widoku — strony szczegółów filmu pod `/movies/<int:pk>/`. Zawiera hero (poster + meta), sekcję zwiastuna (YouTube iframe na privacy-first `youtube-nocookie.com` z minimalnym sandbox), reżyserów, karuzelę aktorów i tabelę najbliższych seansów. Wraz z odblokowaniem „Szczegóły" buttona z US-11 i dodaniem `Movie.get_absolute_url()` (deferred z US-10). Dokument NIE zawiera planu — ten powstanie przez `superpowers:writing-plans`.

---

## Spis treści
1. [Decyzje brainstorming](#1-decyzje-brainstorming)
2. [Architektura](#2-architektura)
3. [Helper: `youtube_embed_url`](#3-helper-youtube_embed_url)
4. [Template](#4-template)
5. [Strategia testów](#5-strategia-testów)
6. [Zmiany w plikach](#6-zmiany-w-plikach)
7. [Plan commitów](#7-plan-commitów)
8. [Out of scope (follow-up)](#8-out-of-scope-follow-up)

---

## 1. Decyzje brainstorming

| # | Pytanie | Decyzja |
|---|---|---|
| Q1 | **Gdzie żyje logika parsowania `trailer_url` → embed URL** | Helper function `youtube_embed_url(url)` w `apps/cinema/utils.py`. Pre-compute w `MovieDetailView.get_context_data()` jako `trailer_embed_url`. Template tylko sprawdza `{% if trailer_embed_url %}`. Pole `trailer_url` zostaje wolnym `URLField` — brak walidacji modelu, brak nowych migracji. Non-YouTube URL → template renderuje fallback `<a target="_blank" rel="noopener noreferrer">`. |
| Q2 | **Layout aktorów (spec mówi „galeria/karuzela")** | Bootstrap Carousel, jeden aktor per slide (3-8 aktorów per movie po US-16 → 3-8 slides). `data-bs-ride="false"` (no auto-cycle, lepiej dla a11y). Bootstrap JS już załadowane przez `base.html`. |

**Niedyskutowane (defaults dziedziczone z M1/US-11):**
- Polish copy (mirror M1 + US-11 templates).
- Bootstrap 5.3.3 CDN (już w `base.html`).
- Emoji-only placeholders (🎬 dla blank poster, 👤 dla blank actor/director photo) — konsystencja z US-11 + brak Bootstrap Icons CDN.
- Genre badges: `badge bg-secondary` (mirror US-11).

---

## 2. Architektura

### 2.1 View

`apps/cinema/views.py` — `MovieDetailView(DetailView)` jako sibling do `MovieListView`.

```python
from django.utils import timezone
from django.views.generic import DetailView

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

**Decyzje:**
- **Orphan movie (brak seansów) renderuje stronę** z empty-state alertem w sekcji seansów — NIE 404. Bezpośredni URL `/movies/<pk>/` działa nawet zanim admin doda screening. Easier admin + share-by-link.
- **Past screenings filtered out** w queryset → `start_time__gte=now`. Public page pokazuje tylko to, co jest jeszcze do bookingu.
- **`select_related("hall")`** na screenings → unika N+1 per row w tabeli.
- **`prefetch_related("genres", "actors", "directors")`** na main queryset — pokrywa wszystkie M2M wyświetlane w hero/cast sections.

### 2.2 URLs

`apps/cinema/urls.py`:

```python
urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
    path("movies/<int:pk>/", MovieDetailView.as_view(), name="movie_detail"),
]
```

### 2.3 Movie model addition

`apps/cinema/models.py` — `get_absolute_url` (deferred z US-10):

```python
class Movie(models.Model):
    ...
    def get_absolute_url(self):
        return reverse("cinema:movie_detail", kwargs={"pk": self.pk})
```

Brak migracji (method-only).

### 2.4 Update US-11 movie list

`templates/cinema/movie_list.html` — "Szczegóły" button traci `disabled` i dostaje href:

```html
<a href="{{ movie.get_absolute_url }}" class="btn btn-primary btn-sm mt-auto">Szczegóły</a>
```

Test w `tests/cinema/test_movie_list.py::TestCardRendering::test_card_shows_disabled_details_button` zostaje przepisany na sprawdzenie aktywnego linku.

---

## 3. Helper: `youtube_embed_url`

### 3.1 Lokalizacja + sygnatura

`apps/cinema/utils.py` (NEW file):

```python
import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def youtube_embed_url(url: str | None) -> str | None:
    """Return a privacy-respecting youtube-nocookie embed URL, or None if
    the input is missing/not a recognized YouTube URL.

    Accepts:
    - https://www.youtube.com/watch?v=<id>      (incl. extra query args, m.youtube.com)
    - https://youtu.be/<id>
    - https://www.youtube.com/embed/<id>
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

### 3.2 Privacy + bezpieczeństwo

- **`youtube-nocookie.com`** — YouTube nie set'uje cookies przed pierwszym play interaction.
- **`_VIDEO_ID_RE = ^[A-Za-z0-9_-]{11}$`** — YouTube video IDs to dokładnie 11 znaków z bezpiecznego alfabetu. Wzmacnia walidację przeciwko URL injection / open redirect via crafted trailer_url.

### 3.3 Akceptowane formaty

| Wejście | Wynik |
|---|---|
| `None` lub `""` | `None` |
| `https://www.youtube.com/watch?v=<11chars>` | embed URL |
| `https://www.youtube.com/watch?v=<11chars>&t=42s` | embed URL (extra params ignorowane) |
| `https://m.youtube.com/watch?v=<11chars>` | embed URL |
| `https://youtu.be/<11chars>` | embed URL |
| `https://youtu.be/<11chars>?si=...` | embed URL (extra path/query ignorowane) |
| `https://www.youtube.com/embed/<11chars>` | embed URL |
| `https://www.youtube.com/watch` (brak `v`) | `None` |
| `https://example.com/foo` | `None` |
| `https://www.youtube.com/watch?v=short` (nie 11 chars) | `None` |
| Malformed URL (rzuca `ValueError`) | `None` |

---

## 4. Template

### 4.1 Lokalizacja

`templates/cinema/movie_detail.html` (NEW).

### 4.2 Sections (kolejność)

1. **Hero** — `row` z `col-md-4` (poster lub 🎬) + `col-md-8` (title, genre badges, `<dl>` z release_date + duration, description).
2. **Trailer** (conditional) — embed YouTube `<iframe>` jeśli `trailer_embed_url` truthy; fallback `<a target="_blank" rel="noopener noreferrer">` jeśli `movie.trailer_url` ale nie-YouTube; sekcja całkowicie ukryta jeśli `trailer_url=""`.
3. **Reżyseria** (conditional) — `row row-cols-2 row-cols-md-4` z `rounded-circle` 80px portretami; 👤 placeholder przy blank photo. Ukryte jeśli brak directors.
4. **Obsada** (conditional) — Bootstrap Carousel z `data-bs-ride="false"`, jeden aktor per slide (`carousel-item` z `.active` na `forloop.first`), 140px portrety, prev/next buttons. Ukryte jeśli brak actors.
5. **Najbliższe seanse** (always present) — `<table>` z kolumnami: Data i godzina (`d.m.Y H:i`), Sala, Cena (`{{ s.price }} zł`), Dostępne miejsca (`s.available_seats_count`), button „Zarezerwuj" (`disabled` — US-20 wires). Empty state: `alert alert-info` z „Brak zaplanowanych seansów dla tego filmu."

### 4.3 Iframe markup (trailer)

```html
<iframe src="{{ trailer_embed_url }}"
        title="Zwiastun: {{ movie.title }}"
        width="100%" style="aspect-ratio: 16/9;"
        frameborder="0"
        allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        referrerpolicy="strict-origin-when-cross-origin"
        sandbox="allow-scripts allow-same-origin allow-presentation"
        allowfullscreen></iframe>
```

**Security choices baked in:**
- **`sandbox="allow-scripts allow-same-origin allow-presentation"`** — minimum dla YT playera. Bez `allow-popups` (no "Watch later" spawning), bez `allow-top-navigation` (iframe nie redirect'uje nas), bez `allow-forms`.
- **`referrerpolicy="strict-origin-when-cross-origin"`** — leak'uje tylko origin, nie full path.
- **`youtube-nocookie.com`** origin (z helpera) — no tracking cookies pre-interaction.

### 4.4 Placeholders

- 🎬 dla blank `movie.poster` — mirror US-11 cards.
- 👤 dla blank `actor.photo` / `director.photo` — nowy pattern, ale spójny z 🎬 (emoji + `bg-light` div).
- `rounded-circle` na portretach actor/director (vs square posters).

---

## 5. Strategia testów

### 5.1 Lokalizacje

- `tests/cinema/test_youtube_embed_url.py` (~10 unit testów helpera).
- `tests/cinema/test_movie_detail.py` (~18 integration testów view + template).
- `tests/cinema/test_movie_list.py` — update istniejącego `test_card_shows_disabled_details_button`.

### 5.2 `youtube_embed_url` (unit, niezależne od DB)

| Wejście | Oczekiwany wynik |
|---|---|
| `None` | `None` |
| `""` | `None` |
| `"https://example.com/foo"` | `None` |
| `"https://www.youtube.com/watch?v=dQw4w9WgXcQ"` | `"https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"` |
| `"https://youtu.be/dQw4w9WgXcQ"` | same |
| `"https://www.youtube.com/embed/dQw4w9WgXcQ"` | same |
| `"https://m.youtube.com/watch?v=dQw4w9WgXcQ"` | same |
| `"https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"` | same (extra params ignored) |
| `"https://www.youtube.com/watch"` (brak v) | `None` |
| `"https://www.youtube.com/watch?v=tooshort"` (8 znaków) | `None` |

### 5.3 `MovieDetailView` (integration)

| Obszar | Testy |
|---|---|
| **Routing** | `GET /movies/<pk>/` → 200; missing pk → 404; `reverse("cinema:movie_detail", kwargs={"pk": pk})` resolves; template = `cinema/movie_detail.html`. |
| **`Movie.get_absolute_url`** | Returns `/movies/<pk>/`. |
| **Anon + auth** | Both → 200, brak login wall. |
| **Hero** | Title, formatted `release_date` (`d.m.Y`), `duration_minutes` + "min", description, all genre badges. Poster set → `<img>`; blank poster → 🎬. |
| **Trailer (YouTube)** | `trailer_url="https://youtu.be/dQw4w9WgXcQ"` → `<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"` + `sandbox="allow-scripts allow-same-origin allow-presentation"` w HTML. |
| **Trailer (non-YouTube)** | `trailer_url="https://example.com/clip.mp4"` → fallback `<a href="https://example.com/clip.mp4"` z `rel="noopener noreferrer"`; brak `<iframe`. |
| **Trailer (blank)** | `trailer_url=""` → brak nagłówka "Zwiastun" w HTML. |
| **Directors** | Names renderowane, photo set → `<img>`, blank → 👤; sekcja ukryta gdy `directors.all` empty. |
| **Actors carousel** | `data-bs-ride="false"` present, jeden `.carousel-item` per aktor, dokładnie jeden `.carousel-item.active`; sekcja ukryta gdy `actors.all` empty. |
| **Upcoming screenings** | Future sorted asc (D+1 < D+2 < D+3); past hidden; hall name + formatted date + price + `available_seats_count` + "Zarezerwuj" `disabled` w HTML. |
| **Empty screenings** | Movie z 0 future screenings → "Brak zaplanowanych seansów" alert; brak `<table`. |
| **Orphan movie** | No screenings + no actors + no directors + no trailer → 200; tylko hero + empty alert. |
| **N+1 budget** | `assertMaxNumQueries(6)` na populated detail page. |

### 5.4 `MovieListView` update

Replace istniejący `test_card_shows_disabled_details_button` w `test_movie_list.py` z:

```python
def test_card_links_details_button_to_movie_detail(self, client):
    movie = MovieFactory()
    ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
    response = client.get("/")
    content = response.content.decode()
    assert "Szczegóły" in content
    assert f'href="/movies/{movie.pk}/"' in content
    assert "disabled" not in content
```

---

## 6. Zmiany w plikach

```
apps/cinema/
├── views.py                                  ✎ + MovieDetailView
├── urls.py                                   ✎ + path("movies/<int:pk>/", ...)
├── models.py                                 ✎ + Movie.get_absolute_url()
└── utils.py                                  ★ NEW

templates/cinema/
├── movie_detail.html                         ★ NEW
└── movie_list.html                           ✎ Szczegóły button: drop disabled + add href

tests/cinema/
├── test_youtube_embed_url.py                 ★ NEW
├── test_movie_detail.py                      ★ NEW
└── test_movie_list.py                        ✎ replace disabled-button test → href test

.Claude/backlog.md                            ✎ status board
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress
```

**Brak zmian:** `settings/`, `apps/cinema/admin.py`, `apps/cinema/models.py` poza `get_absolute_url`, dependency list, migrations.

---

## 7. Plan commitów

1. `docs(M2): add design spec + plan for US-13 + mark in progress`
2. `feat(FR-03): youtube_embed_url helper with full URL-form coverage` (`utils.py` + unit tests)
3. `feat(FR-03): Movie.get_absolute_url + URL config for detail view` (model + urls + routing tests)
4. `feat(FR-03): MovieDetailView with prefetches + screenings context` (view + integration tests)
5. `feat(FR-03): movie_detail.html template (hero + trailer + cast + screenings)` (template + render tests)
6. `feat(FR-03): wire Szczegóły button on movie list to detail page` (list template + list test update)
7. `docs(M2): mark US-13 done, queue US-12 next`

**Branch:** `feat/FR-03-movie-detail`.

---

## 8. Out of scope (follow-up)

| Feature | US | Why deferred |
|---|---|---|
| Booking flow (clicking "Zarezerwuj") | **US-20** (M3, FR-07) | Button renders `disabled` — US-20 dropuje klasę + dodaje `href` jak US-13 zrobiło dla "Szczegóły". |
| Real `Screening.available_seats_count` (Booking aggregation) | **US-18** (M3, FR-3.8) | Stub z US-10 zwraca `hall.capacity` — detail page nie wie, że to stub. |
| Filtering/search na movie list | **US-12** (FR-02) | Niezależne od detail page. |
| Daily screenings list `/screenings/?date=...` | **US-14** (FR-04) | Osobna view; navbar link „Seanse" obecnie `disabled`. |
| Performance pass (`Prefetch` with custom QS) | **US-17** (NFR) | `assertMaxNumQueries(6)` locks current budget. |
| i18n (gettext_lazy) | — | Mirror M1 + US-11; multi-lang to osobny milestone. |
| Validation `Movie.trailer_url` przy save | — | Parse-at-render z fallback link sufficient — brak migracji + bardziej forgiving. |
