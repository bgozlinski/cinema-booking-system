# US-28 — Admin: BookingAdmin + ScreeningAdmin with availability badges (FR-11)

**Data:** 2026-05-24
**Branch (planned):** `feat/FR-11-booking-admin` (off `main`)
**Estymata:** M (2 admin classes + inline + badges + budget tests; OSTATNI M3)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-28 jako #11, **plan-directly**, last M3 → `v0.3.0`)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-11 (BookingAdmin + ScreeningAdmin)
- `apps/cinema/admin.py` (US-15/US-17) — wzorzec `get_queryset` annotate + `@admin.display(ordering=)`
- `apps/booking/admin.py` (US-18) — minimal BookingAdmin do upgrade
- `apps/cinema/views.py::_annotate_booked_count` — booked-count annotation (logika do mirror, NIE import)
- `tests/cinema/test_admin_query_budgets.py` (US-17) — budget test pattern + `admin_client` fixture

---

## 1. Cel

US-28 (OSTATNI M3) dokańcza admin booking-side (FR-11): pełny `BookingAdmin` (upgrade minimal z US-18) + nowy `ScreeningAdmin` z kolorowymi badge dostępności. Po merge: M3 complete → `v0.3.0`.

Zakres:

1. **`BookingAdmin` upgrade** (`apps/booking/admin.py`) — `total_price_display`, rozszerzone filtry, `list_editable=("status",)`, `get_queryset` `select_related` (kill N+1).
2. **`ScreeningAdmin`** (NEW, `apps/cinema/admin.py`) — `available_seats_display` (kolorowy badge) + `booked_seats_display`, `BookingInline`, `get_queryset` `select_related` + booked-count annotate (kill N+1).
3. **Testy** — 2 budget tests (`test_admin_query_budgets.py`) + update istniejących admin shape testów + badge unit test.

### Decyzje (plan-directly)

| # | Decyzja | Wybór | Powód |
|---|---------|-------|-------|
| 1 | Badge thresholds | **available/capacity: <20% red / 20-50% yellow(orange) / >50% green** | m3_planning; FR-11 "kolorowe badge" |
| 2 | Booked-count annotation w ScreeningAdmin | **Inline w `get_queryset`** (NIE import `_annotate_booked_count` z views) | admin→views import = zła kierunkowość warstw; inline = self-contained, brak views.py churn; ~4 linie duplikacji (filter CONFIRMED\|active-PENDING) guarded budget testem |
| 3 | `Screening.booked_seats_count` reuse | **Annotation `_annotated_booked_count`** — metoda short-circuituje na `hasattr` (US-18) | badge helpery czytają `available_seats_count()`/`booked_seats_count()` → annotation → 0 N+1 |

### Out of scope (defer'd)

- **`ScreeningInline` na MovieAdmin/HallAdmin** (FR-11 §308/§340) — US-15 ich nie dodało; touching US-17 perf-tuned MovieAdmin = needless risk. Follow-up (M5 polish).
- **`UserAdmin`** (FR-11 §326) — istnieje z M1 (US-06). Bez zmian.
- **StripeEventAdmin** — read-only minimal z US-18, wystarcza.
- **DRY booked-count do `utils.py`** — możliwe później (decyzja #2 inline na teraz).

---

## 2. Architektura plików

### Edytowane

| Plik | Zmiana |
|------|--------|
| `apps/booking/admin.py` | BookingAdmin upgrade (total_price_display, filters, list_editable, get_queryset) |
| `apps/cinema/admin.py` | + `ScreeningAdmin` + `BookingInline` + importy (Q/Sum/Coalesce/timezone/Booking/BookingStatus/Screening) |
| `tests/cinema/test_admin_query_budgets.py` | + TestScreeningAdminQueryBudget + TestBookingAdminQueryBudget |
| `tests/booking/test_admin.py` | update BookingAdmin shape (total_price_display, list_editable) |
| `tests/cinema/test_admin.py` | + ScreeningAdmin registered + badge color unit test |
| `.Claude/backlog.md` | US-28 → Done (po merge) |

Brak migracji (zero zmian modeli).

---

## 3. BookingAdmin — `apps/booking/admin.py` (upgrade)

```python
from django.contrib import admin

from apps.booking.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "screening",
        "seats_count",
        "status",
        "total_price_display",
        "created_at",
    )
    list_filter = ("status", "screening__movie", "created_at")
    list_editable = ("status",)
    search_fields = ("user__email", "screening__movie__title")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "screening__movie")

    @admin.display(description="total price")
    def total_price_display(self, obj):
        return obj.total_price
```

### Decyzje uzasadnione

1. **`get_queryset` `select_related("user", "screening__movie")`** — `Booking.__str__` (changelist `screening` col) używa `screening.movie.title`; `user` col używa User.__str__; `total_price_display` używa `screening.price`. Bez select_related = N+1 per row. (Dev pitfall #7 pattern.)
2. **`list_editable=("status",)`** — quick status edit na changelist (FR-11). "status" NIE jest pierwszą kolumną (id link), więc OK.
3. **`total_price_display` bez `ordering`** — `total_price` to computed property (seats×price), nie DB column; brak sortowania.
4. **`list_filter` rozszerzone** `("status", "screening__movie", "created_at")` per FR-11.

---

## 4. ScreeningAdmin — `apps/cinema/admin.py` (new)

Dodać importy: `from django.db.models import Count, Q, Sum` (Count już jest), `from django.db.models.functions import Coalesce`, `from django.utils import timezone`, `from apps.booking.models import Booking, BookingStatus`, oraz `Screening` do `from apps.cinema.models import ...`.

```python
class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ("user", "seats_count", "status", "created_at")
    readonly_fields = ("user", "seats_count", "status", "created_at")
    can_delete = False
    show_change_link = True


@admin.register(Screening)
class ScreeningAdmin(admin.ModelAdmin):
    list_display = (
        "movie",
        "start_time",
        "hall",
        "price",
        "available_seats_display",
        "booked_seats_display",
    )
    list_filter = ("hall", "movie", "start_time")
    search_fields = ("movie__title",)
    date_hierarchy = "start_time"
    inlines = (BookingInline,)

    def get_queryset(self, request):
        now = timezone.now()
        return (
            super()
            .get_queryset(request)
            .select_related("movie", "hall")
            .annotate(
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
        )

    @admin.display(description="booked")
    def booked_seats_display(self, obj):
        return obj.booked_seats_count()

    @admin.display(description="available")
    def available_seats_display(self, obj):
        available = obj.available_seats_count()
        capacity = obj.hall.capacity
        ratio = available / capacity if capacity else 0
        if ratio > 0.5:
            color = "green"
        elif ratio >= 0.2:
            color = "orange"
        else:
            color = "red"
        return format_html('<b style="color: {};">{}</b>', color, available)
```

### Decyzje uzasadnione

1. **`_annotated_booked_count` annotate (inline)** — `Screening.booked_seats_count()` (US-18) short-circuituje na `hasattr(self, "_annotated_booked_count")`. Więc badge helpery (`booked_seats_count()`/`available_seats_count()`) czytają annotation → 0 N+1. Logika filtra (CONFIRMED | active-PENDING) mirror do `views._annotate_booked_count` — inline (decyzja #2), NIE import (admin→views zła kierunkowość).
2. **`select_related("movie", "hall")`** — `movie`/`hall` cols (FK __str__) + `available_seats_display` używa `hall.capacity`. Bez select_related = N+1.
3. **Badge** `format_html` (już importowany w cinema/admin.py). Ratio = available/capacity: `>0.5` green, `[0.2, 0.5]` orange, `<0.2` red (decyzja #1). `capacity == 0` guard (ratio 0 → red).
4. **`booked_seats_display` bez badge** — plain int (annotation). `@admin.display` description.
5. **`BookingInline`** — `extra=0`, readonly (user/seats_count/status/created_at), `can_delete=False`, `show_change_link=True` (link do BookingAdmin). Renderuje się tylko na change page (NIE changelist) → brak wpływu na changelist budget.
6. **`format_html` z `color` jako placeholder** — `{}` dla color + available; bezpieczne (color z whitelist green/orange/red, available int).

---

## 5. Tests scope

### `tests/cinema/test_admin_query_budgets.py` (+2 klasy)

Dodać import `from tests.booking.factories import BookingFactory`.

```python
class TestScreeningAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 screenings x 2 active-PENDING bookings. available/booked_seats_display
        call booked_seats_count() — without get_queryset annotate that's 1+ query per
        row. After annotate + select_related: absorbed into the main fetch."""
        for _ in range(12):
            screening = ScreeningFactory()
            BookingFactory.create_batch(2, screening=screening)
        url = reverse("admin:cinema_screening_changelist")
        with django_assert_max_num_queries(12):  # baseline + annotate + buffer; tighten after measure
            response = admin_client.get(url)
            assert response.status_code == 200


class TestBookingAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 bookings. __str__ (movie title) + user + total_price (screening.price)
        are N+1 without select_related("user", "screening__movie")."""
        for _ in range(12):
            BookingFactory()
        url = reverse("admin:booking_booking_changelist")
        with django_assert_max_num_queries(12):  # baseline + select_related joins + buffer
            response = admin_client.get(url)
            assert response.status_code == 200
```

### `tests/booking/test_admin.py` (update shape)
- Update istniejący BookingAdmin test: `list_display` zawiera `"total_price_display"`; `list_editable == ("status",)`; `total_price_display(booking)` zwraca `booking.total_price`.

### `tests/cinema/test_admin.py` (+ ScreeningAdmin)
- `test_screening_admin_registered` — `Screening` w `admin.site._registry`.
- `test_available_seats_display_color` — unit: ScreeningAdmin().available_seats_display(obj) → assert kolor wg ratio (np. sold-out screening → "red"; pusty → "green"). Użyć ScreeningFactory(hall cap N) + ConfirmedBookingFactory żeby ustawić availability; potrzebne `_annotated_booked_count` annotation albo wywołać przez `ma.get_queryset(...).get(pk=)`. **Adapter:** `ma = ScreeningAdmin(Screening, admin.site); annotated = ma.get_queryset(RequestFactory().get("/admin/")).get(pk=screening.pk); html = ma.available_seats_display(annotated)` → assert `"green"/"orange"/"red"` w html (pattern jak US-17 helper test adapter, dev pitfall #7).

**Razem:** ~2 budget + ~2-3 shape/badge + 1 registration.

---

## 6. Definition of Done

- [ ] **BookingAdmin:** `total_price_display`, `list_filter`+`list_editable`, `get_queryset` select_related.
- [ ] **ScreeningAdmin:** `available_seats_display` (kolorowy badge <20/20-50/>50), `booked_seats_display`, `BookingInline`, `get_queryset` select_related + booked annotate.
- [ ] **Budget:** ScreeningAdmin + BookingAdmin changelist bounded (no N+1); 2 budget tests green.
- [ ] **Testy:** budget + shape + badge + registration; istniejące admin testy zaktualizowane; wszystkie green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff`, `ruff format --check`, `mypy` — clean. `makemigrations --check` exits 0.
- [ ] **Manual smoke:** `/admin/cinema/screening/` — kolorowe badge dostępności (zielony/żółty/czerwony); change page pokazuje BookingInline. `/admin/booking/booking/` — total_price column + status list-editable + filter po movie/status/created_at.
- [ ] **M3 close (po merge):** `v0.3.0` tag + GitHub release + memory update M3→M4.

---

## 7. Risks

1. **Budget cap guess.** ScreeningAdmin/BookingAdmin caps (12) to educated guess (jak US-17). Jeśli list_editable formset / list_filter dropdowns dodają query — zmierzyć i poluzować/zacisnąć. Cap z bufforem.
2. **`available_seats_display` test wymaga annotation.** `available_seats_count()` → `booked_seats_count()` → bez annotation robi query (działa, ale test helpera na model instance powinien przejść przez `ma.get_queryset(...)` żeby annotation był obecny — inaczej testuje slow path). Adapter pattern (dev pitfall #7). Alternatywnie wywołać na surowym obj (slow path) — też zwróci poprawny kolor, ale nie testuje annotation. Użyć adaptera.
3. **`BookingInline` na ScreeningAdmin change page N+1.** Inline iteruje bookings → user per row. Tylko change page (nie changelist), few bookings per screening → akceptowalne. Budget test pokrywa tylko changelist.
4. **`list_editable=("status",)` + `list_display_links`.** "id" (pierwsza kol) to default link; "status" editable OK. Gdyby Django narzekało (status w list_display_links) — explicit `list_display_links=("id",)`.
5. **Cross-app import (cinema/admin importuje booking.models).** OK — admin może importować dowolny model. Brak cyklu (booking.models nie importuje cinema.admin).
6. **`@admin.display` total_price_display** zwraca Decimal — admin renderuje str(Decimal). Locale ("76,50") — OK w admin (nie testujemy formatu, tylko obecność/wartość property).
