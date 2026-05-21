# Design — KinoMania: daily ScreeningList view (US-14 / FR-04)

**Data:** 2026-05-21
**Status:** Approved (brainstorming session — bartek + Claude Opus 4.7)
**Powiązany US:** US-14 (`feat/FR-04-screening-list`)
**Powiązany FR:** FR-04 (Harmonogram seansów na dany dzień)
**Cel:** Specyfikacja widoku dziennego harmonogramu seansów pod `/screenings/?date=YYYY-MM-DD` (default: dziś). Date picker ograniczony do `today..today+30`; out-of-range → silent clamp + `messages.warning`. Wyniki pogrupowane po filmie (card per movie + embedded table), kolejność grup wg najwcześniejszego seansu tego dnia. Włącza navbar link "Seanse" usunięty z `disabled` w US-09. Dokument NIE zawiera planu — ten powstanie przez `superpowers:writing-plans`.

---

## Spis treści
1. [Decyzje brainstorming](#1-decyzje-brainstorming)
2. [Architektura + view](#2-architektura--view)
3. [Template](#3-template)
4. [Strategia testów](#4-strategia-testów)
5. [Zmiany w plikach](#5-zmiany-w-plikach)
6. [Plan commitów](#6-plan-commitów)
7. [Out of scope (follow-up)](#7-out-of-scope-follow-up)

---

## 1. Decyzje brainstorming

| # | Pytanie | Decyzja |
|---|---|---|
| Q1 | **Out-of-range `?date=` handling** | Clamp + `messages.warning("Data poza zakresem; pokazano dla <YYYY-MM-DD>.")`. Past → today; future > +30 → today+30; malformed → today. Forgiving UX, friendly dla shared/old links, konsystentne z US-12 silent-ignore policy. |
| Q2 | **Layout grouping** | Card per movie z embedded mini-table seansów (godzina, sala, cena, miejsca, "Zarezerwuj" disabled). Mirror US-13 screenings table dla cohesion. Header karty: poster thumb 80×120 + tytuł (link do detail page) + genre badges. |

**Niedyskutowane (defaults dziedziczone z M1/M2):**
- Polish copy (mirror M2).
- Bootstrap 5.3.3 CDN.
- No pagination (one day fits in memory ~5-15 movies × ~5 screenings).
- "Zarezerwuj" `disabled` (US-20 wires) — same handoff pattern jak "Szczegóły" z US-11/13.

---

## 2. Architektura + view

### 2.1 View

`apps/cinema/views.py` — `ScreeningListView(TemplateView)` jako sibling do `MovieListView`/`MovieDetailView`.

```python
import datetime
from collections import OrderedDict
from datetime import time, timedelta

from django.contrib import messages
from django.utils import timezone
from django.views.generic import TemplateView

from apps.cinema.models import Screening


class ScreeningListView(TemplateView):
    template_name = "cinema/screening_list.html"

    def _resolve_date(self):
        """Parse ?date= and clamp to today..today+30.

        Returns (effective_date, was_clamped, raw_input_str).
        - No ?date= → (today, False, "").
        - Empty ?date= → (today, False, "").
        - Past or > today+30 or malformed → (clamped, True, raw).
        """
        today = timezone.localdate()
        max_date = today + timedelta(days=30)
        raw = self.request.GET.get("date", "")
        if not raw:
            return today, False, ""
        try:
            requested = datetime.date.fromisoformat(raw)
        except ValueError:
            return today, True, raw
        if requested < today:
            return today, True, raw
        if requested > max_date:
            return max_date, True, raw
        return requested, False, raw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        effective, clamped, _raw = self._resolve_date()
        if clamped:
            messages.warning(
                self.request,
                f"Data poza zakresem; pokazano dla {effective.isoformat()}.",
            )
        day_start = timezone.make_aware(
            datetime.datetime.combine(effective, time.min)
        )
        day_end = day_start + timedelta(days=1)

        screenings = (
            Screening.objects
            .filter(start_time__gte=day_start, start_time__lt=day_end)
            .select_related("movie", "hall")
            .prefetch_related("movie__genres")
            .order_by("movie__title", "start_time")
        )

        grouped: "OrderedDict" = OrderedDict()
        for s in screenings:
            grouped.setdefault(s.movie, []).append(s)
        movie_groups = sorted(grouped.items(), key=lambda item: item[1][0].start_time)

        ctx["effective_date"] = effective
        ctx["today"] = timezone.localdate()
        ctx["max_date"] = timezone.localdate() + timedelta(days=30)
        ctx["movie_groups"] = movie_groups
        return ctx
```

### 2.2 URL

`apps/cinema/urls.py`:

```python
urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
    path("movies/<int:pk>/", MovieDetailView.as_view(), name="movie_detail"),
    path("screenings/", ScreeningListView.as_view(), name="screening_list"),
]
```

### 2.3 Navbar wiring

`templates/base.html` line 21 — drop `disabled` + wire href:

```html
<li class="nav-item"><a class="nav-link" href="{% url 'cinema:screening_list' %}">Seanse</a></li>
```

### 2.4 Date form

Hand-rolled (no Django `Form` class) — single field, validation already done w view's `_resolve_date()`:

```html
<input type="date" name="date"
       min="{{ today|date:'Y-m-d' }}"
       max="{{ max_date|date:'Y-m-d' }}"
       value="{{ effective_date|date:'Y-m-d' }}">
```

Browser `min`/`max` to friendly hint dla native picker — większość browserów greys out invalid dates. Server-side `_resolve_date()` to actual gate.

### 2.5 Decyzje semantyczne

- **`TemplateView` zamiast `ListView`** — output to *grouped* structure, nie flat queryset. No pagination. Custom context shape: `list[tuple[Movie, list[Screening]]]`.
- **Movie group ordering** — by earliest screening that day (`item[1][0].start_time` po inner sort by `start_time`). Matches cinema-bulletin convention "what's playing first goes first".
- **Past screenings dla today nadal included** — view filtruje po calendar day, NIE `>= now`. Movie z screeningiem o 06:00 (już minął jak ktoś otwiera o 14:00) nadal pokazany. Spec FR-04 nie wymaga ukrywania.
- **`messages.warning` rather than `add_message`** — używa Django's `contrib.messages`, renderowane przez istniejący `base.html:42-50` messages block (Bootstrap alert dismissable). Zero template change dla warning rendering.
- **Day-window math identical do US-12** — `make_aware(combine(date, time.min))` + 1 day. DST-safe via `settings.TIME_ZONE="Europe/Warsaw"`. Inkluzywne 00:00, ekskluzywne 24:00.

---

## 3. Template

### 3.1 Lokalizacja

`templates/cinema/screening_list.html` (NEW).

### 3.2 Sections

1. **Header `<h1>Seanse</h1>`** + date form (input type="date" + "Pokaż" button + conditional "Dzisiaj" reset link gdy `request.GET.date`).
2. **Movie groups** (cards) — for each `(movie, screenings)` in `movie_groups`:
   - Card header: poster thumb 80×120 (lub 🎬 placeholder) + tytuł jako link `{{ movie.get_absolute_url }}` + genre badges (`bg-secondary`).
   - Card body: `<table>` z kolumnami Godzina (`H:i`) / Sala / Cena / Dostępne miejsca / "Zarezerwuj" button (`disabled`).
3. **Empty state** — `alert-info` z "Brak seansów na dzień {{ effective_date|date:'d.m.Y' }}." gdy `movie_groups` puste.

### 3.3 UX decyzje

- **Time column `H:i`** only — date already w page header, no need to repeat per row.
- **"Dzisiaj" quick-reset** — link tylko gdy `request.GET.date` truthy. Href to canonical `/screenings/` (today). Mirror "Wyczyść filtry" pattern z US-12.
- **Poster thumb 80×120** — smaller niż detail-page hero, larger niż movie list card thumb. Visual breathing room dla card header layout.
- **Tytuł linkuje do detail page** — single most useful interaction obok rezerwacji.
- **"Zarezerwuj" `disabled`** — handoff comment dla US-20 (drop class + wire href).

### 3.4 Warning toast

`messages.warning` z `_resolve_date()` rendered przez istniejący `base.html:42-50` block (Django messages framework). User widzi yellow Bootstrap alert "Data poza zakresem; pokazano dla <YYYY-MM-DD>" przy submit out-of-range date.

---

## 4. Strategia testów

### 4.1 Lokalizacje

- `tests/cinema/test_screening_list.py` (~22 tests, NEW).
- `tests/cinema/test_base_template.py` — replace istniejącą Seanse-disabled assertion z Seanse-active.

### 4.2 `_resolve_date` semantics (via `?date=`)

| Test | Setup | Assert |
|---|---|---|
| `test_no_date_param_defaults_to_today` | `GET /screenings/` | `context["effective_date"] == today`; brak warning. |
| `test_explicit_today_renders_today` | `GET /screenings/?date=<today>` | same; brak warning. |
| `test_future_within_30_days_passes_through` | `GET /screenings/?date=<today+15>` | `effective_date == today+15`; brak warning. |
| `test_past_date_clamps_to_today` | `GET /screenings/?date=<today-5>` | `effective_date == today`; warning present. |
| `test_far_future_clamps_to_today_plus_30` | `GET /screenings/?date=<today+90>` | `effective_date == today+30`; warning present. |
| `test_malformed_date_clamps_to_today` | `GET /screenings/?date=not-a-date` | `effective_date == today`; warning present. |
| `test_empty_date_string_defaults_to_today_no_warning` | `GET /screenings/?date=` | `effective_date == today`; **brak** warning. |

### 4.3 Grouping + ordering

| Test | Setup | Assert |
|---|---|---|
| `test_screenings_grouped_by_movie` | 2 movies × 2 screenings tomorrow | `len(movie_groups) == 2`; each tuple has 2 screenings |
| `test_movies_ordered_by_earliest_screening` | A: 18:00, B: 14:00, tomorrow | `movie_groups[0][0] == B`, `[1][0] == A` |
| `test_screenings_within_group_sorted_by_start_time` | X: 21:00, 14:00, 18:00 tomorrow | times = `[14:00, 18:00, 21:00]` |
| `test_past_screenings_for_today_still_included` | screening today at 06:00 (potentially already past) | screening present przy `?date=<today>` — filter by calendar day, NIE `>= now`. |

### 4.4 Day-window boundary (mirrors US-12)

| Test | Setup | Assert |
|---|---|---|
| `test_boundary_inclusive_at_midnight` | screening at 00:00 local target date | present |
| `test_boundary_inclusive_at_end_of_day` | screening at 23:59:59 local | present |
| `test_boundary_excludes_next_day_midnight` | screening at 00:00 local `target+1` | NOT present |

### 4.5 Routing + template

| Test | Assert |
|---|---|
| `test_url_returns_200_anon` | 200 |
| `test_url_returns_200_authenticated` | 200 |
| `test_url_name_reverses` | `reverse("cinema:screening_list") == "/screenings/"` |
| `test_uses_screening_list_template` | `cinema/screening_list.html` w `response.templates` |

### 4.6 Rendering

| Test | Setup | Assert |
|---|---|---|
| `test_movie_title_links_to_detail_page` | movie + screening tomorrow | `href="/movies/<pk>/"` w HTML |
| `test_screening_row_shows_hour_hall_price_seats` | tomorrow 18:00, Hall A, 42.50, capacity 100 | "18:00", "Hall A", "42,50" or "42.50", "100", "Zarezerwuj" disabled w HTML |
| `test_empty_state_when_no_screenings_for_day` | no screenings today | "Brak seansów na dzień" alert + empty groups |
| `test_dzisiaj_link_visible_when_date_param_present` | `GET ?date=<tomorrow>` | `>Dzisiaj<` z `href="/screenings/"` |
| `test_dzisiaj_link_hidden_without_date_param` | `GET /screenings/` | no `>Dzisiaj<` |
| `test_clamp_warning_shows_in_messages_block` | `GET ?date=<today-5>` | "Data poza zakresem" w HTML |

### 4.7 Base template

W `tests/cinema/test_base_template.py` — replace `test_navbar_seanse_link_disabled` (or equivalent) z:

```python
def test_navbar_seanse_links_to_screening_list(response):
    content = response.content.decode()
    match = re.search(r'<a[^>]*>\s*Seanse\s*</a>', content)
    assert match is not None
    anchor = match.group(0)
    assert 'href="/screenings/"' in anchor
    assert "disabled" not in anchor
```

### 4.8 N+1 budget

Nowy `assertMaxNumQueries` test:
- Populated day: ~5 movies × 3 screenings each = 15 rows.
- Queryset: `select_related("movie", "hall") + prefetch_related("movie__genres")` → 1 query screenings (joined), 1 query genres prefetch.
- Budget cap **3** (1 screenings + 1 genres prefetch + 1 harness overhead).

---

## 5. Zmiany w plikach

```
apps/cinema/
├── views.py                                  ✎ + ScreeningListView
└── urls.py                                   ✎ + path("screenings/", ..., name="screening_list")

templates/cinema/
└── screening_list.html                       ★ NEW

templates/
└── base.html                                 ✎ navbar Seanse: drop `disabled` + add href

tests/cinema/
├── test_screening_list.py                    ★ NEW (~22 tests)
└── test_base_template.py                     ✎ swap "Seanse disabled" → "Seanse links to /screenings/"

.Claude/backlog.md                            ✎ status board
memory/project_kinomania_bootstrap.md         ✎ after merge — M2 progress (7/8)
```

**Brak zmian:** `settings/`, `apps/cinema/admin.py`, `apps/cinema/models.py`, `apps/cinema/forms.py`, dependency list, migrations.

---

## 6. Plan commitów

1. `docs(M2): add design spec + plan for US-14 + mark in progress`
2. `feat(FR-04): ScreeningListView with date clamping + grouped queryset` (view + URL + routing/date/grouping tests)
3. `feat(FR-04): screening_list.html template with date form + movie cards` (template + render tests)
4. `feat(FR-04): wire Seanse navbar link to screening list` (base.html + test update)
5. `docs(M2): mark US-14 done, queue US-17 next`

**Branch:** `feat/FR-04-screening-list`.

---

## 7. Out of scope (follow-up)

| Feature | US/why deferred |
|---|---|
| Booking flow (clicking "Zarezerwuj") | **US-20** (M3, FR-07) — drops `disabled` + wires href, same handoff jak US-11/13. |
| Real `Screening.available_seats_count` (Booking aggregation) | **US-18** (M3, FR-3.8). Stub returns `hall.capacity` do M3. |
| Performance pass | **US-17** (NFR, last M2 task). `assertMaxNumQueries(3)` budget na ten widok już w US-14. |
| Filter by genre / movie na schedule page | Out of scope. MovieList (US-11/12) i MovieDetail (US-13) cover browsing path. |
| Multi-day view / weekly schedule | Out of M2. FR-04 explicitly per-day. |
| iCalendar / "Add to calendar" export | Out of M2. |
| Highlighting "now playing" / sold-out state | Booking model needed → M3. |
| Pagination | Day fits in memory; no need. |
