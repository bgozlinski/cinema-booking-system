# US-21 — Booking detail view + permissions (FR-08)

**Data:** 2026-05-23
**Branch (planned):** `feat/FR-08-booking-detail` (off `main`)
**Estymata:** S (standard DetailView + owner/staff guard + template)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-21 jako #4, **plan-directly** — standard DetailView + permission)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-08 (strona potwierdzenia rezerwacji)
- `apps/booking/models.py::Booking` (US-18) — `total_price` property, `BookingStatus`
- `apps/booking/views.py::BookingCreateView` (US-20) — wzorzec view + booking app
- `apps/cinema/views.py::MovieDetailView` (US-13) — wzorzec `DetailView` + `select_related`

---

## 1. Cel

US-21 dostarcza **stronę potwierdzenia rezerwacji** (FR-08): `/bookings/<int:pk>/` pokazuje szczegóły bookingu jego właścicielowi (lub staffowi). Obcy zalogowany user → HTTP 403; anonim → redirect na login.

Zakres:

1. **`BookingDetailView`** w `apps/booking/views.py` — `DetailView` z `LoginRequiredMixin` + `UserPassesTestMixin` (owner-or-staff).
2. **URL** `booking:detail` na `/bookings/<int:pk>/` w `apps/booking/urls.py`.
3. **Template** `templates/booking/booking_detail.html` — numer, tytuł filmu, data+godzina, hall, seats_count, total_price, status (badge).
4. **Testy** w `tests/booking/test_detail_view.py` (~8: access matrix + content + N+1 budget).

### Out of scope (defer'd)

- **`?stripe=success|cancelled` flash** (FR-21 `success_url`/`cancel_url`) → **US-24** (Stripe integration). US-21 renderuje czysty detail niezależnie od query params.
- **"Anuluj" button** (FR-10) → US-23 (logika cancel) — przycisk dorzucany razem z akcją.
- **Zmiana US-20 stub redirect targetu** na booking detail — opcjonalne, NIE w tym US (US-24 i tak podmienia stub na Stripe).
- My-bookings list (FR-09) → US-22.

---

## 2. Architektura plików

### Tworzone

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `templates/booking/booking_detail.html` | Create | Detail render (FR-08 pola + status badge) |
| `tests/booking/test_detail_view.py` | Create | Access matrix + content + budget |

### Edytowane

| Plik | Zmiana |
|------|--------|
| `apps/booking/views.py` | + `BookingDetailView` |
| `apps/booking/urls.py` | + `path("bookings/<int:pk>/", ..., name="detail")` |
| `.Claude/backlog.md` | US-21 → Done (po merge) |

### Stan obecny (zweryfikowane)

| Element | Stan |
|---------|------|
| `apps/booking/views.py` | ✅ `BookingCreateView` (US-20) |
| `apps/booking/urls.py` | ✅ `app_name="booking"`, `booking:create`; include w `settings/urls.py` (namespace="booking") |
| `apps/booking/models.py::Booking.total_price` | ✅ property `seats_count * screening.price` |
| `apps/accounts/models.py::User.is_staff` | ✅ `BooleanField(default=False)` — staff check działa |
| `tests/accounts/factories.py::UserFactory` | ✅ `UserFactory(is_staff=True)` flows przez `create_user` extra_fields |
| `tests/booking/factories.py` | ✅ `BookingFactory` (PENDING), `ConfirmedBookingFactory`, `CancelledBookingFactory` |

Brak migracji (zero zmian modeli).

---

## 3. View — `apps/booking/views.py` (append)

```python
class BookingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Booking
    template_name = "booking/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        return Booking.objects.select_related(
            "screening__movie", "screening__hall", "user"
        )

    def get_object(self, queryset=None):
        # Cache so test_func + DetailView.get don't fetch the booking twice.
        if not hasattr(self, "_booking"):
            self._booking = super().get_object(queryset)
        return self._booking

    def test_func(self) -> bool:
        booking = self.get_object()
        return self.request.user == booking.user or self.request.user.is_staff
```

### Decyzje uzasadnione

1. **`LoginRequiredMixin` + `UserPassesTestMixin` (w tej kolejności).** MRO: `LoginRequiredMixin.dispatch` sprawdza auth pierwszy → anonim → `handle_no_permission` → redirect login (302). Authed → `super().dispatch` → `UserPassesTestMixin` → `test_func` fail → `handle_no_permission` → user authenticated → `raise PermissionDenied` (403). Dokładnie FR-08: anon→login, authed-obcy→403.
2. **`test_func`: owner OR staff.** `self.request.user == booking.user or self.request.user.is_staff`. Per FR-08.
3. **`get_object` cache (`self._booking`).** `test_func` (w `dispatch`) i `DetailView.get` oba wołają `get_object()`. Bez cache = 2 queries (każdy `select_related` JOIN). Cache = 1. Tani win (mirror US-17 perf mindset).
4. **`select_related("screening__movie", "screening__hall", "user")`.** Template iteruje `booking.screening.movie.title`, `screening.hall.name`, `total_price` (`screening.price`). Single query, brak N+1.
5. **`DetailView` (nie `View`).** Standard Django dla single-object read; `pk` z URL, `context_object_name="booking"`.

---

## 4. URL — `apps/booking/urls.py` (append)

```python
from apps.booking.views import BookingCreateView, BookingDetailView

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="detail"),
]
```

Brak konfliktu route (`screenings/<pk>/book/` vs `bookings/<pk>/`). `booking:detail` resoluje do `/bookings/<id>/`.

---

## 5. Template — `templates/booking/booking_detail.html`

Extends `base.html`. Sekcje (FR-08):
- Nagłówek `Rezerwacja #{{ booking.id }}`.
- Karta z `<dl>`: tytuł filmu, termin (`d.m.Y H:i`), hall, liczba miejsc, łączna cena (`total_price` + " zł"), status jako **badge** z `get_status_display` i kolorem per status (PENDING=`bg-warning text-dark`, CONFIRMED=`bg-success`, CANCELLED=`bg-secondary`).
- Link powrotny do repertuaru.

**Dev pitfall reminders:** `{% %}`/`{{ }}` w jednej linii (PyCharm hard-wrap); status `{% if %}` chain porównuje do literałów `'PENDING'`/`'CONFIRMED'` (wartości `BookingStatus`). `total_price` renderuje się z locale (pl_PL → "75,00" przecinek) — testy assertują integer part ("75") zamiast pełnej formy (dev pitfall #5).

---

## 6. Tests scope — `tests/booking/test_detail_view.py`

`pytestmark = pytest.mark.django_db`. Helper `_detail_url(booking) = reverse("booking:detail", pk=booking.pk)`.

### `TestBookingDetailAccess`
- `test_anonymous_redirected_to_login` — anon → 302, login URL + `next=`.
- `test_owner_gets_200` — `force_login(booking.user)` → 200, `context["booking"] == booking`.
- `test_staff_non_owner_gets_200` — `UserFactory(is_staff=True)` (nie owner) → 200.
- `test_other_user_forbidden` — inny non-staff user → 403.
- `test_404_for_missing_booking` — zalogowany, pk=999999 → 404.

### `TestBookingDetailContent`
- `test_renders_booking_fields` — booking z `MovieFactory(title="Diuna")` + `price=25.00` + `seats_count=3` (CONFIRMED) → content zawiera "Diuna", "75" (total 3×25, locale-agnostic), "Potwierdzona" (CONFIRMED display).
- `test_template_used` — `booking/booking_detail.html` w `resp.templates`.

### Budget
- `test_query_budget` — `django_assert_max_num_queries(5)` na owner GET (auth+session ~2 + booking select_related 1; cap 5 łapie zgubiony `select_related` lub utracony `get_object` cache).

**Razem:** ~8 testów.

---

## 7. Definition of Done

- [ ] **View:** `BookingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView)` — owner/staff, cache `get_object`, `select_related`.
- [ ] **403/302:** anon → login redirect; authed-obcy → 403; owner/staff → 200.
- [ ] **URL:** `booking:detail` na `/bookings/<int:pk>/`.
- [ ] **Template:** numer/tytuł/termin/hall/seats/total_price/status badge (FR-08).
- [ ] **Testy:** ~8 w `tests/booking/test_detail_view.py`, wszystkie green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff check`, `ruff format --check`, `mypy` — clean.
- [ ] **No regression:** istniejące testy pass; `makemigrations --check` exits 0.
- [ ] **Manual smoke:** login → utwórz booking (US-20) → otwórz `/bookings/<id>/` → widać szczegóły; wyloguj/inny user → 403.

---

## 8. Risks

1. **`UserPassesTestMixin` 403 vs 302 dla authed.** `AccessMixin.handle_no_permission` raises `PermissionDenied` tylko gdy `raise_exception=True` LUB user authenticated. Authed-obcy jest authenticated → 403 ✅. Anon → redirect login ✅. Brak potrzeby `raise_exception=True`. (Gdyby kiedyś dodać `LoginRequiredMixin` PO `UserPassesTestMixin` — anon dostałby 403 zamiast login redirect; kolejność `LoginRequiredMixin` FIRST jest istotna.)
2. **`get_object` double-fetch bez cache.** `test_func` + `DetailView.get` = 2× query. Cache `self._booking` rozwiązuje; budget test (cap 5) guard.
3. **`total_price` locale formatting.** pl_PL → "75,00". Test assertuje "75" substring (działa dla "75,00" i "75.00"). Dev pitfall #5.
4. **Staff factory.** `UserFactory(is_staff=True)` — `is_staff` rideuje przez `create_user` extra_fields (zweryfikowane). Gdyby manager kiedyś filtrował extra_fields → użyć `is_superuser=True` (create_superuser ustawia is_staff).
5. **`?stripe=` param.** FR-21 `success_url` = `/bookings/<id>/?stripe=success`. US-21 ignoruje query param (renderuje detail). Flash na podstawie `?stripe=` → US-24. Brak regresji (DetailView ignoruje nieznane GET params).
