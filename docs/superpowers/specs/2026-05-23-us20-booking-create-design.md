# US-20 — Booking create view (PENDING + transakcja + select_for_update) — design

**Data:** 2026-05-23
**Branch (planned):** `feat/FR-07-booking-create` (off `main`)
**Estymata:** L (serce flow rezerwacji — concurrency + 3 warstwy + template + wiring)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-20 jako #3, **brainstorm-required**)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-07 (rezerwacja), §FR-21 (Stripe Checkout — replace stub w US-24), §5.2 (race condition), §5.3 (reguły czasowe), §8 (struktura: shared `services`, `payments/services/stripe.py`)
- `apps/booking/forms.py::BookingForm` (US-19) — pre-lock walidacja wejścia
- `apps/booking/models.py::Booking` (US-18) — model docelowy
- `apps/cinema/models.py::Screening` — `available_seats_count()`, `is_in_past()` (US-18 real impl)
- `apps/cinema/views.py` — wzorzec CBV w projekcie

---

## 1. Cel

US-20 to **serce flow rezerwacji** (FR-07): zalogowany user otwiera `/screenings/<id>/book/`, podaje liczbę miejsc, dostaje PENDING booking z 15-min oknem i redirect do (stubowanego) checkoutu. Race-safe przez `transaction.atomic()` + `select_for_update()` na wierszu Screening.

Zakres:

1. **Service** `apps/booking/services.py::create_booking(...)` — atomic + lock + authoritative re-check + PENDING create. Shared web+API (M4 US-32 reuse).
2. **Payments stub** `apps/payments/services.py::create_checkout_session(booking)` — zwraca `(checkout_url, session_id)`; stub teraz, real Stripe SDK w US-24.
3. **View** `apps/booking/views.py::BookingCreateView` — GET renderuje formularz+podsumowanie, POST waliduje (US-19 form) → service → redirect/re-render.
4. **URLs** `apps/booking/urls.py` (`app_name="booking"`) + include w `settings/urls.py`.
5. **Template** `templates/booking/booking_form.html` — podsumowanie seansu + form + JS live total.
6. **Wiring CTA** — time-pille w `movie_detail.html` + `screening_list.html` linkują do `booking:create` dla dostępnych seansów.
7. **Testy** — service (happy/errors/race deterministic + 1 threaded), view (auth/render/POST/race-loss), payments stub.

### Decyzje z brainstormingu (2026-05-23)

| # | Decyzja | Wybór | Powód |
|---|---------|-------|-------|
| 1 | Service layer | **Extract teraz** — `apps/booking/services.py::create_booking` | FR §4/§8 shared web+API; thin view; service unit-testable bez HTTP |
| 2 | Stripe stub seam | **`apps/payments/services.py::create_checkout_session(booking) -> (url, session_id)`** | FR §8 layout; US-24 wypełnia jedną funkcję = clean swap |
| 3 | Atomic boundary | **Stripe PO commit** (poza lockiem) | Nie trzymać row-locka przez network call (US-24); orphan PENDING self-healing |
| 4 | `select_for_update` granularity | **Wiersz Screening** (`select_for_update().get(pk=)`) | §5.2 settles; brak seat-level modelu (`seats_count` = int) |
| 5 | Success redirect | **Stub zwraca movie_detail URL; view: flash + redirect** | Booking detail = US-21 jeszcze nie istnieje; zero scope bleed |
| 6 | Race-loss UX | **Service raises domain error; view re-renderuje form (200) z non-field error** | Standard Django; user zostaje w kontekście z odświeżoną dostępnością |
| 7 | Race test | **Both** — deterministic re-check + 1 threaded (`transaction=True` + barrier) | Najwyższa pewność; threaded udowadnia lock |

### Out of scope (defer'd)

- **Real Stripe Checkout** (`stripe.checkout.Session.create`) → **US-24** (zastępuje payments stub).
- **Booking detail** `/bookings/<id>/` (FR-08) → US-21.
- **My-bookings** `/my-bookings/` (FR-09) → US-22.
- **Cancel** (FR-10) + refund → US-23 / US-27.
- **`expire_pending_bookings`** (FR-23) → US-26 (sprząta orphan/stale PENDING).
- **Webhook** PENDING→CONFIRMED (FR-22) → US-25.
- Email confirmation → poza M3.

---

## 2. Architektura — 3 warstwy

```
View  (apps/booking/views.py::BookingCreateView)
  │  HTTP: LoginRequiredMixin, BookingForm bind, error→re-render(200), success→flash+redirect
  ▼
Service  (apps/booking/services.py::create_booking)
  │  transaction.atomic() + select_for_update + authoritative re-check + Booking PENDING
  ▼
Payments stub  (apps/payments/services.py::create_checkout_session)
     returns (checkout_url, session_id) — US-24 fills with Stripe SDK
```

Każda warstwa testowana niezależnie. Service nie zależy od HTTP/requestu → reuse w M4 API serializer.

### Nowe pliki

| Plik | Odpowiedzialność |
|------|------------------|
| `apps/booking/services.py` | `create_booking` + exception hierarchy (`BookingError`/`NotEnoughSeatsError`/`ScreeningInPastError`) |
| `apps/booking/views.py` | `BookingCreateView(LoginRequiredMixin, View)` |
| `apps/booking/urls.py` | `app_name="booking"` + `booking:create` |
| `apps/payments/services.py` | `create_checkout_session(booking)` stub |
| `templates/booking/booking_form.html` | podsumowanie seansu + form + JS live total |
| `tests/booking/test_services.py` | service tests (happy/errors/race) |
| `tests/booking/test_views.py` | view tests (auth/render/POST/race-loss) |
| `tests/payments/test_services.py` | stub test |

### Edytowane pliki

| Plik | Zmiana |
|------|--------|
| `settings/urls.py` | `path("", include("apps.booking.urls", namespace="booking"))` |
| `templates/cinema/screening_list.html` | time-pill href → `booking:create` (available); `<span>` dla sold-out |
| `templates/cinema/movie_detail.html` | j.w. (linia ~135) |
| `.Claude/backlog.md` | US-20 → Done (po merge) |

Brak migracji (zero zmian modeli).

---

## 3. Service — `apps/booking/services.py`

```python
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.cinema.models import Screening
from apps.payments.services import create_checkout_session


class BookingError(Exception):
    """Base for booking-creation domain errors (caught by the view)."""


class NotEnoughSeatsError(BookingError):
    """Requested seats exceed availability at lock time (race lost or sold out)."""

    def __init__(self, available: int) -> None:
        self.available = available
        super().__init__(
            f"Dostępnych jest tylko {available} miejsc — wybierz mniejszą liczbę."
        )


class ScreeningInPastError(BookingError):
    """Screening already started by lock time."""

    def __init__(self) -> None:
        super().__init__("Seans już się rozpoczął — nie można zarezerwować miejsc.")


def create_booking(*, user, screening: Screening, seats_count: int) -> tuple[Booking, str]:
    """Create a PENDING booking race-safely and return (booking, checkout_url).

    Locks the Screening row, re-checks availability + start time under the lock
    (authoritative — the form check in US-19 is a pre-check), creates the PENDING
    booking with a 15-minute expiry, commits, then (outside the lock) creates the
    Stripe checkout session. Stripe is stubbed until US-24.

    Caller (BookingForm / API serializer) is responsible for seats_count range
    [1, 10]; this service enforces only the lock-dependent rules.
    """
    with transaction.atomic():
        locked = Screening.objects.select_for_update().get(pk=screening.pk)
        if locked.is_in_past():
            raise ScreeningInPastError()
        available = locked.available_seats_count()
        if seats_count > available:
            raise NotEnoughSeatsError(available=available)
        booking = Booking.objects.create(
            user=user,
            screening=locked,
            seats_count=seats_count,
            status=BookingStatus.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

    # Lock released on commit — external call must NOT hold the row lock (US-24).
    checkout_url, session_id = create_checkout_session(booking)
    if session_id:
        booking.stripe_session_id = session_id
        booking.save(update_fields=["stripe_session_id"])

    return booking, checkout_url
```

### Decyzje uzasadnione

1. **Keyword-only args** (`*, user, screening, seats_count`) — czytelne call-site, brak pomyłki kolejności.
2. **Re-fetch z lockiem przez `pk`** — view przekazuje (niezablokowany) `Screening`; service re-locks świeżą wersję `select_for_update().get(pk=...)`. Lock = wiersz Screening (§5.2).
3. **Authoritative re-check pod lockiem** — `is_in_past()` + `available_seats_count()` liczone po nałożeniu locka. Form (US-19) to UX pre-check bez locka; tu jest źródło prawdy. `available_seats_count()` używa `booked_seats_count()` (CONFIRMED + active-PENDING) — nowo tworzony PENDING jeszcze nie istnieje, więc nie liczy siebie.
4. **`seats_count` range NIE w service** — [1,10] to caller (form/serializer). Service skupia się na regułach zależnych od locka. (Model `MinValueValidator(1)/MaxValueValidator(10)` jest DB-side safety net.)
5. **Stripe po commit** — orphan PENDING przy Stripe-fail jest self-healing: liczy się jako zarezerwowane przez 15 min, `expire_pending_bookings` (US-26) finalnie CANCELuje, user retry przez FR-21 `POST /bookings/<id>/checkout/`.
6. **`save(update_fields=["stripe_session_id"])`** — minimalny UPDATE; w stubie `session_id=""` → save pomijany (guard `if session_id`).
7. **Returns `(booking, checkout_url)`** — view potrzebuje obu (redirect target + booking dla flash/przyszłego detalu). M4 API zwróci `{booking, checkout_url}`.
8. **Exception hierarchy** — `BookingError` base; view łapie `except BookingError`. Komunikaty PL (UI default). `NotEnoughSeatsError.available` niesie liczbę dostępnych (FR-07).

---

## 4. Payments stub — `apps/payments/services.py`

```python
from django.urls import reverse

from apps.booking.models import Booking


def create_checkout_session(booking: Booking) -> tuple[str, str]:
    """Return (checkout_url, session_id) for a PENDING booking.

    STUB (US-20): returns the screening's movie detail URL and an empty session
    id — no Stripe call yet. US-24 replaces the body with
    stripe.checkout.Session.create(...) per FR-21 (line_items, client_reference_id,
    success_url=.../bookings/<id>/?stripe=success, idempotency_key=booking-<id>-checkout)
    and returns the real (session.url, session.id).
    """
    checkout_url = reverse("cinema:movie_detail", kwargs={"pk": booking.screening.movie_id})
    return checkout_url, ""
```

**Decyzja:** stub zwraca cinema URL (intentional, udokumentowany stub smell) — daje działający redirect w US-20 bez zależności od US-21/US-24. US-24 podmienia ciało funkcji; sygnatura `(url, session_id)` i call-site w `create_booking` bez zmian.

---

## 5. View — `apps/booking/views.py`

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.booking.forms import BookingForm
from apps.booking.services import BookingError, create_booking
from apps.cinema.models import Screening


class BookingCreateView(LoginRequiredMixin, View):
    template_name = "booking/booking_form.html"

    def _get_screening(self, pk: int) -> Screening:
        return get_object_or_404(
            Screening.objects.select_related("movie", "hall"), pk=pk
        )

    def get(self, request, pk: int):
        screening = self._get_screening(pk)
        form = BookingForm(screening=screening)
        return render(request, self.template_name, {"screening": screening, "form": form})

    def post(self, request, pk: int):
        screening = self._get_screening(pk)
        form = BookingForm(request.POST, screening=screening)
        if not form.is_valid():
            return render(request, self.template_name, {"screening": screening, "form": form})
        try:
            booking, checkout_url = create_booking(
                user=request.user,
                screening=screening,
                seats_count=form.cleaned_data["seats_count"],
            )
        except BookingError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"screening": screening, "form": form})

        messages.success(request, "Rezerwacja utworzona (PENDING) — dokończ płatność.")
        return redirect(checkout_url)
```

### Decyzje uzasadnione

1. **`View` z `get`/`post`** (NIE `FormView`) — potrzeba: inject `screening` do formu, custom error handling (service exception → `add_error`), dwa różne response paths. Explicit `View` czytelniejszy niż override 4 metod `FormView`. Projekt używa CBV (spójność).
2. **`LoginRequiredMixin`** (FR-07 wymaga logowania). Anon → redirect `LOGIN_URL` (`accounts:login`) z `?next=`. `LOGIN_URL` zweryfikowane w `settings/base.py:99`.
3. **`get_object_or_404` z `select_related("movie", "hall")`** — podsumowanie i `__str__` używają `movie.title` + `hall`; jeden query.
4. **Invalid form → re-render 200** (nie 400) — standard Django form pattern; błędy przy polach.
5. **`BookingError` → `add_error(None, ...)` (non-field) + re-render 200** — race-loss/sold-out/past pokazane jako błąd ogólny formularza; user widzi odświeżoną dostępność (re-render odpytuje `available_seats_count`).
6. **Success → `messages.success` + `redirect(checkout_url)`** — PRG. W US-24 `checkout_url` = Stripe hosted page; flash wording może się zmienić (Stripe redirect jest external).

---

## 6. URLs

### `apps/booking/urls.py`

```python
from django.urls import path

from apps.booking.views import BookingCreateView

app_name = "booking"

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
]
```

### `settings/urls.py` — dodać po cinema include

```python
path("", include("apps.cinema.urls", namespace="cinema")),
path("", include("apps.booking.urls", namespace="booking")),   # ← new
```

Brak konfliktu route: cinema `screenings/` (exact) vs booking `screenings/<int:pk>/book/` (distinct). Przyszłe `/bookings/<id>/` (US-21), `/my-bookings/` (US-22) dołączą do `apps/booking/urls.py`.

---

## 7. Template — `templates/booking/booking_form.html`

Extends `base.html`. Sekcje:
- **Podsumowanie seansu:** `movie.title`, `start_time` (`d.m.Y H:i`), `hall.name`, cena/miejsce (`screening.price` + " zł"), `available_seats_count`.
- **Form:** `{{ form.seats_count }}` (NumberInput min/max z US-19) + non-field errors (`{{ form.non_field_errors }}`) + field errors.
- **Live total (JS):** `<span data-price="{{ screening.price }}">` + input listener → `total = price × seats`, wyświetla "Razem: X zł". Per FR-07 ("łączna cena obliczana JS-em"). Pure vanilla JS, no deps.
- **Submit:** "Zarezerwuj i zapłać".

**Dev pitfall reminder (#6 + HTML tag rules):** Django `{% %}`/`{{ }}` w jednej linii (PyCharm hard-wrap psuje); JS total nie może polegać na `{{ }}` wieloliniowym.

---

## 8. CTA wiring — time-pille

Redesign (PR #18) zastąpił przyciski "Zarezerwuj" **time-pillami**. Obecny markup (`screening_list.html:47`, `movie_detail.html:135`):

```django
<a href="#" class="time-pill {% if not s.is_available %}is-soldout{% endif %}">{{ s.start_time|date:"H:i" }}</a>
```

**Zmiana** (jedna linia — Django tag rules): dostępne → link do bookingu; sold-out/past → nie-klikalny `<span>`:

```django
{% for s in hall_group.list %}{% if s.is_available %}<a href="{% url 'booking:create' pk=s.pk %}" class="time-pill">{{ s.start_time|date:"H:i" }}</a>{% else %}<span class="time-pill is-soldout">{{ s.start_time|date:"H:i" }}</span>{% endif %}{% endfor %}
```

(Analogicznie w `screening_list.html` — sprawdzić dokładny loop var w plan-phase.) Anon klikający pill → `booking:create` → `LoginRequiredMixin` redirect na login z `?next=` (po zalogowaniu wraca na booking page).

---

## 9. Tests scope

### `tests/payments/test_services.py`
- `test_create_checkout_session_returns_movie_detail_url_and_empty_session` — stub zwraca `(reverse(cinema:movie_detail, pk=movie_id), "")`.

### `tests/booking/test_services.py`
- `test_create_booking_creates_pending_with_expiry` — status PENDING, `expires_at` ≈ now+15m (tolerancja), seats/user/screening poprawne.
- `test_create_booking_returns_checkout_url` — zwraca movie_detail URL seansu.
- `test_create_booking_does_not_set_session_id_with_stub` — `stripe_session_id == ""`.
- `test_create_booking_raises_when_seats_exceed_available` — competing `ConfirmedBookingFactory` obniża dostępność; `NotEnoughSeatsError`, `.available` poprawne.
- `test_create_booking_raises_for_past_screening` — `start_time` w przeszłości → `ScreeningInPastError`.
- `test_create_booking_sequential_overbooking_impossible` — cap N; pierwszy booking bierze większość; drugi ponad resztę → raises; suma booked ≤ capacity.
- `test_create_booking_concurrent_no_overbooking` — **`@pytest.mark.django_db(transaction=True)`**; 2 wątki + `threading.Barrier(2)`, oba próbują seats sumujące > capacity na tym samym screeningu; assert dokładnie jeden sukces, drugi `NotEnoughSeatsError`, suma booked ≤ capacity. `connection.close()` w `finally` per wątek.

### `tests/booking/test_views.py`
- `test_get_requires_login` — anon GET → 302 na login z `?next=`.
- `test_post_requires_login` — anon POST → 302 na login.
- `test_get_renders_form_and_summary` — zalogowany, 200, kontekst `form`+`screening`, template `booking/booking_form.html`.
- `test_get_404_for_missing_screening` — nieistniejący pk → 404.
- `test_post_valid_creates_booking_and_redirects` — 1 Booking PENDING, redirect na movie_detail, `messages` zawiera success.
- `test_post_invalid_form_rerenders_no_booking` — seats 0/11 → 200, błąd na `seats_count`, 0 nowych Booking.
- `test_post_race_loss_rerenders_with_error` — competing booking wykupuje miejsca (lub mock `create_booking` raises `NotEnoughSeatsError`) → 200, non-field error, brak nowego Booking.
- `test_post_past_screening_rerenders_with_error` — past screening → 200, non-field error.

**Razem:** ~17 testów. Login w view testach: `client.force_login(UserFactory())`.

---

## 10. Definition of Done

- [ ] **Service:** `create_booking` — atomic + `select_for_update` + re-check (`is_in_past` + `available_seats_count`) + PENDING (`expires_at=now+15m`); Stripe po commit; zwraca `(booking, checkout_url)`.
- [ ] **Exceptions:** `BookingError`/`NotEnoughSeatsError(available)`/`ScreeningInPastError`.
- [ ] **Payments stub:** `create_checkout_session(booking) -> (movie_detail_url, "")`.
- [ ] **View:** `BookingCreateView(LoginRequiredMixin, View)` — GET render, POST valid→service→redirect+flash, invalid/`BookingError`→re-render 200.
- [ ] **URLs:** `booking:create` na `/screenings/<int:pk>/book/`; include w `settings/urls.py`.
- [ ] **Template:** `booking_form.html` — podsumowanie + form + JS live total.
- [ ] **CTA:** time-pille linkują do `booking:create` (available), `<span>` dla sold-out — w obu templateach.
- [ ] **Testy:** ~17 (service happy/errors/race deterministic + 1 threaded; view auth/render/POST/race-loss; payments stub); wszystkie green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff check`, `ruff format --check`, `mypy` — clean.
- [ ] **No regression:** istniejące testy pass; `makemigrations --check` exits 0.
- [ ] **Manual smoke:** login → klik time-pill → `/screenings/<id>/book/` → submit 3 seats → redirect na movie_detail + flash; sprawdź PENDING w `/admin/booking/booking/` z `expires_at`.

---

## 11. Risks / dev pitfalls

1. **Threaded test (`transaction=True`) Postgres-only + flaky.** pytest-django domyślnie owija test w transakcję → `select_for_update` nie blokuje cross-thread. Threaded test wymaga `@pytest.mark.django_db(transaction=True)` (truncate między testami, wolniej) + osobne connections per wątek + `connection.close()` w `finally`. SQLite nie wspiera prawdziwego row-locka → test wymaga Postgres (dev/CI mają). **Mitigation:** deterministic re-check testy jako core; threaded jako 1 guarded proof. Udokumentować jako dev pitfall #11.
2. **Orphan PENDING przy Stripe-fail (US-24).** Po commit, jeśli `create_checkout_session` rzuci (real Stripe w US-24) — PENDING istnieje bez sesji. Self-healing (15-min expire). W US-20 stub nie rzuca → brak problemu; flag dla US-24 spec (try/except + user-facing retry).
3. **Form pre-check vs service re-check rozjazd komunikatów.** US-19 form daje "Dostępnych jest tylko N miejsc..." (przy polu); service `NotEnoughSeatsError` daje podobny tekst (non-field przy re-renderze). Akceptowalne — różne layery, rzadki race. Komunikaty celowo zbliżone.
4. **`available_seats_count()` N+1 w booking page.** Single screening (nie loop) → 1 query, brak N+1. Time-pille w cinema templateach już mają `_annotate_booked_count` (US-18) — bez zmian.
5. **Stub zwraca cinema URL z payments app.** Intentional stub smell; udokumentowany; usunięty w US-24. `apps.payments.services` importuje `apps.booking.models.Booking` (type hint) — sprawdzić brak circular (booking.services importuje payments.services; payments.services importuje booking.models — OK, models nie importuje services).
6. **Import cycle booking.services ↔ payments.services.** `booking.services` → `payments.services` (`create_checkout_session`); `payments.services` → `booking.models` (type hint). Brak cyklu (models ≠ services). Gdyby type hint `Booking` powodował problem → użyć `TYPE_CHECKING` guard.
7. **`movie_id` na Screening.** Stub używa `booking.screening.movie_id` (FK id, bez extra query). Zweryfikować że `select_related` w view daje screening z movie (tak — `_get_screening`).

---

## 12. Decisions data-driven (do plan phase)

1. **Dokładny loop var time-pilli w `screening_list.html`** — sprawdzić (`s` vs inny) przed edycją template.
2. **JS live total — inline `<script>` vs static file.** Default: mały inline `<script>` na końcu template (jednorazowy, ~10 linii). Jeśli rośnie → `static/js/booking.js`.
3. **Threaded test seats split** — np. cap=5, oba wątki proszą o 3 (suma 6 > 5) → jeden wygrywa (3 booked), drugi `NotEnoughSeatsError`. Dobrać wartości żeby deterministycznie dokładnie jeden mógł przejść.
4. **`force_login` user fixture** — inline `UserFactory()` per test vs shared fixture. Default: inline (spójność z istniejącymi testami).
