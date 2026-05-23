# US-22 — My bookings panel (FR-09)

**Data:** 2026-05-23
**Branch (planned):** `feat/FR-09-my-bookings` (off `main`)
**Estymata:** M (ListView + 2 taby + template + navbar wiring)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-22 jako #5, **plan-directly** — ListView + tab filter)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-09 (panel rezerwacji), §FR-10 (cancel rule — gating "Anuluj")
- `apps/booking/views.py::BookingDetailView` (US-21) — wzorzec view + booking app
- `apps/booking/models.py::Booking` (US-18) — `total_price`, `BookingStatus`, `Meta.ordering=("-created_at",)`
- `apps/cinema/views.py::ScreeningListView` (US-14) — wzorzec tab/grouping + `select_related`
- `templates/base.html:32-49` — navbar (wire "Moje rezerwacje")

---

## 1. Cel

US-22 dostarcza **panel rezerwacji zalogowanego usera** (FR-09): `/my-bookings/` listuje jego bookingi w dwóch tabach — **Nadchodzące** (`screening.start_time >= now`) i **Historia** (reszta) — server-rendered switch przez `?tab=upcoming|history`.

Zakres:

1. **`MyBookingsView`** w `apps/booking/views.py` — `ListView` z `LoginRequiredMixin`, filtr per user + per tab, sort `-created_at`.
2. **URL** `booking:my_bookings` na `/my-bookings/`.
3. **Template** `templates/booking/my_bookings.html` — tab nav (pills) + lista kart (tytuł→detail, data, hall, seats, status badge, total_price, disabled "Anuluj" placeholder) + empty state per tab.
4. **Navbar wiring** — auth-gated "Moje rezerwacje" link w `base.html`.
5. **Testy** w `tests/booking/test_my_bookings.py` (~10: access/scoping/tabs/ordering/content/budget).

### Out of scope (defer'd)

- **Cancel logika** (`POST /bookings/<id>/cancel/`, status→CANCELLED, FR-10 1h rule) → **US-23**. US-22 renderuje "Anuluj" jako **disabled placeholder** (wzorzec US-13 disabled button); US-23 liczy realną cancellability + wire'uje akcję.
- **Refund przy cancel CONFIRMED** → US-27.
- **Paginacja** — FR-09 nie wymaga; pomijamy (YAGNI; dodać gdy realnie potrzebne).
- **`?stripe=` flash** na detail → US-24.

---

## 2. Architektura plików

### Tworzone

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `templates/booking/my_bookings.html` | Create | Tab nav + lista kart + empty state |
| `tests/booking/test_my_bookings.py` | Create | access/scoping/tabs/ordering/content/budget |

### Edytowane

| Plik | Zmiana |
|------|--------|
| `apps/booking/views.py` | + `MyBookingsView` |
| `apps/booking/urls.py` | + `path("my-bookings/", ..., name="my_bookings")` |
| `templates/base.html` | + auth-gated "Moje rezerwacje" nav item (w `me-auto` ul) |
| `.Claude/backlog.md` | US-22 → Done (po merge) |

Brak migracji (zero zmian modeli).

### Stan obecny (zweryfikowane)

| Element | Stan |
|---------|------|
| `apps/booking/views.py` | ✅ `BookingCreateView` (US-20), `BookingDetailView` (US-21); importuje `LoginRequiredMixin`, `DetailView` |
| `apps/booking/urls.py` | ✅ `booking:create`, `booking:detail` |
| `apps/booking/models.py::Booking` | ✅ `total_price`, `BookingStatus`, `Meta.ordering=("-created_at",)`, `created_at=auto_now_add` |
| `templates/base.html:31-50` | ✅ navbar `{% with un=request.resolver_match.url_name %}` — active przez `un == '<name>'` |
| `tests/booking/factories.py` | ✅ `BookingFactory` (PENDING, screening +7d), `ConfirmedBookingFactory`, `CancelledBookingFactory` |

---

## 3. View — `apps/booking/views.py` (append)

```python
class MyBookingsView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = "booking/my_bookings.html"
    context_object_name = "bookings"

    def _active_tab(self) -> str:
        return "history" if self.request.GET.get("tab") == "history" else "upcoming"

    def get_queryset(self):
        qs = Booking.objects.filter(user=self.request.user).select_related(
            "screening__movie", "screening__hall"
        )
        now = timezone.now()
        if self._active_tab() == "history":
            qs = qs.filter(screening__start_time__lt=now)
        else:
            qs = qs.filter(screening__start_time__gte=now)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_tab"] = self._active_tab()
        return ctx
```

Nowe importy: `from django.utils import timezone`, dorzuć `ListView` do `from django.views.generic import DetailView` → `DetailView, ListView`.

### Decyzje uzasadnione

1. **`ListView` + `LoginRequiredMixin`.** FR-09 wymaga logowania; anon → login redirect (`LOGIN_URL`). Single ListView z filtrem per tab (m3_planning: "Standard ListView z filter").
2. **`_active_tab()` helper.** Tylko `?tab=history` → "history"; wszystko inne (brak param / "upcoming" / śmieci) → "upcoming" (default, defensywne). Używane w `get_queryset` i `get_context_data` (DRY).
3. **Filtr per user.** `filter(user=self.request.user)` — owner-only z definicji (brak cudzych bookingów). Brak potrzeby permission mixin (lista zawsze własna).
4. **Tab filter na `screening__start_time`.** Upcoming = `>= now`, History = `< now`. Per FR-09.
5. **`order_by("-created_at")`.** Per FR-09 (malejąco po created_at) — explicit (matchuje `Meta.ordering`, ale jawnie dla czytelności + po `.filter()`).
6. **`select_related("screening__movie", "screening__hall")`.** Template iteruje `booking.screening.movie.title` + `hall.name` + `total_price` (`screening.price`). Single query, brak N+1.

---

## 4. URL — `apps/booking/urls.py` (append)

```python
from apps.booking.views import BookingCreateView, BookingDetailView, MyBookingsView

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="detail"),
    path("my-bookings/", MyBookingsView.as_view(), name="my_bookings"),
]
```

`booking:my_bookings` → `/my-bookings/`.

---

## 5. Template — `templates/booking/my_bookings.html`

Extends `base.html`. Struktura:
- `<h1>Moje rezerwacje</h1>`.
- Tab nav (`nav nav-pills`): Nadchodzące (`?tab=upcoming`) / Historia (`?tab=history`), active class z `active_tab`.
- Jeśli `bookings`: lista kart. Każda karta: tytuł filmu jako link do `booking:detail`, meta (data `d.m.Y H:i` · sala · seats · total_price + " zł"), status badge (`get_status_display`, kolor per status), **disabled "Anuluj"** button (tylko upcoming + status != CANCELLED — placeholder do US-23).
- Else: empty state per tab ("Brak historycznych rezerwacji." / "Nie masz nadchodzących rezerwacji. <link repertuar>").

**Dev pitfall reminders:** Django `{% %}`/`{{ }}` w jednej linii; status `{% if %}` chain porównuje do literałów `'PENDING'`/`'CONFIRMED'`; `total_price` locale ("75,00") — testy assertują substring integer part.

---

## 6. Navbar wiring — `templates/base.html`

W lewym `me-auto` ul (wewnątrz `{% with un=... %}`, po `Seanse` li, przed `</ul>` linia ~49) dodać auth-gated item:

```django
{% if user.is_authenticated %}
<li class="nav-item">
    {% if un == 'my_bookings' %}
    <a class="nav-link active" href="{% url 'booking:my_bookings' %}">Moje rezerwacje</a>
    {% else %}
    <a class="nav-link" href="{% url 'booking:my_bookings' %}">Moje rezerwacje</a>
    {% endif %}
</li>
{% endif %}
```

`un == 'my_bookings'` matchuje `url_name` (bez namespace, jak istniejące `screening_list`). Anon nie widzi linku.

---

## 7. Tests scope — `tests/booking/test_my_bookings.py`

`pytestmark = pytest.mark.django_db`. `reverse("booking:my_bookings")` wołane wewnątrz testów (nie module-level).

### `TestMyBookingsAccess`
- `test_anonymous_redirected_to_login` — anon → 302, login URL + `next=`.

### `TestMyBookingsScoping`
- `test_shows_only_own_bookings` — `BookingFactory(user=me)` + `BookingFactory()` (inny user) → context `bookings` ma 1, owner=me.

### `TestMyBookingsTabs`
- `test_upcoming_is_default` — future (+7d) + past screening booking; brak `?tab` → `active_tab=="upcoming"`, tylko future w liście.
- `test_history_tab_shows_past` — `?tab=history` → `active_tab=="history"`, tylko past booking.
- `test_unknown_tab_falls_back_to_upcoming` — `?tab=garbage` → `active_tab=="upcoming"`.

### `TestMyBookingsOrdering`
- `test_newest_first` — 2 bookingi (oba future), assert `bookings[0]` = drugi utworzony (późniejszy `created_at`).

### `TestMyBookingsContent`
- `test_empty_state` — brak bookingów → 200, `bookings == []`.
- `test_links_to_detail` — `reverse("booking:detail", pk=booking.pk)` w content.
- `test_template_used` — `booking/my_bookings.html` w `resp.templates`.
- `test_cancel_button_disabled_placeholder` — upcoming non-CANCELLED booking → "Anuluj" w content + `disabled` (placeholder do US-23).

### Budget
- `test_query_budget` — 3 bookingi, `django_assert_max_num_queries(6)` (select_related = 1 list query; cap łapie N+1).

**Razem:** ~10 testów.

---

## 8. Definition of Done

- [ ] **View:** `MyBookingsView(LoginRequiredMixin, ListView)` — filtr user + tab, sort `-created_at`, `select_related`.
- [ ] **Taby:** `?tab=upcoming` (default) / `?tab=history`; `active_tab` w kontekście; nieznany tab → upcoming.
- [ ] **URL:** `booking:my_bookings` na `/my-bookings/`.
- [ ] **Template:** lista kart (tytuł→detail, data, hall, seats, status badge, total_price, disabled Anuluj) + empty state per tab.
- [ ] **Navbar:** auth-gated "Moje rezerwacje" link, active na my-bookings.
- [ ] **Testy:** ~10 w `tests/booking/test_my_bookings.py`, green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff check`, `ruff format --check`, `mypy` — clean.
- [ ] **No regression:** istniejące testy pass; `makemigrations --check` exits 0.
- [ ] **Manual smoke:** login → utwórz booking (US-20) → navbar "Moje rezerwacje" → widać w Nadchodzące; przełącz Historia; klik tytuł → booking detail.

---

## 9. Risks

1. **`reverse` na module-level.** Wywołanie `reverse("booking:my_bookings")` przy imporcie modułu testów może odpalić przed konfiguracją URLconf. **Mitigation:** wołać `reverse` wewnątrz funkcji testowych (nie jako stała modułowa).
2. **`created_at` ordering determinism.** `auto_now_add` — 2 bookingi utworzone sekwencyjnie różnią się o mikrosekundy (Postgres timestamp). Order_by("-created_at") deterministyczny. (Gdyby kiedyś flake — nie da się ustawić auto_now_add; rozważyć explicit timestamps via `Booking.objects.filter(pk=).update(created_at=)`.)
3. **"Anuluj" placeholder vs FR-10.** US-22 renderuje disabled "Anuluj" dla upcoming non-CANCELLED — NIE liczy pełnej reguły 1h (FR-10). To US-23 doda realną cancellability + akcję. Placeholder unika `NoReverseMatch` (brak `booking:cancel` URL do US-23). Wzorzec: US-13 disabled "Zarezerwuj".
4. **Navbar `un` bez namespace.** Istniejące itemy używają `un == 'screening_list'` (url_name bez namespace). `un == 'my_bookings'` spójne. Jeśli kiedyś dwa app URL names się zderzą — rozważyć namespace-aware check; teraz brak kolizji.
5. **`total_price` locale.** Test asertuje substring (np. seats×price integer part), nie pełną sformatowaną wartość. Dev pitfall #5.
6. **Tab filter granica `now`.** Booking na seans dokładnie `start_time == now` trafi do upcoming (`>= now`). Edge bez znaczenia praktycznego; spójne z FR-09 (`>= now`).
