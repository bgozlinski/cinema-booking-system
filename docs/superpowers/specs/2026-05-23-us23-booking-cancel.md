# US-23 — Cancel booking (PENDING-only) (FR-10)

**Data:** 2026-05-23
**Branch (planned):** `feat/FR-10-booking-cancel` (off `main`)
**Estymata:** M (model method + service + view + template wiring)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-23 jako #6, **plan-directly**, PENDING-only; refund → US-27)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-10 (anulowanie), §5.2/§5.x (atomic + select_for_update na state change)
- `apps/booking/services.py::create_booking` (US-20) — wzorzec service + `BookingError` hierarchy
- `apps/booking/models.py::Booking` (US-18) — `status`, `expires_at`, `BookingStatus`
- `templates/booking/my_bookings.html` (US-22) — disabled "Anuluj" placeholder do wire'owania

---

## 1. Cel

US-23 dostarcza **anulowanie rezerwacji** (FR-10): `POST /bookings/<int:pk>/cancel/` — właściciel anuluje **PENDING** booking gdy `screening.start_time > now() + 1h`. Status → CANCELLED (rekord zostaje — historia), flash + redirect na `/my-bookings/`.

Zakres:

1. **`Booking.can_be_cancelled()`** model method — `status == PENDING AND screening.start_time > now() + 1h`.
2. **`cancel_booking` service** w `apps/booking/services.py` — atomic + `select_for_update` na Booking + re-check + status update. `BookingNotCancellableError`.
3. **`BookingCancelView`** w `apps/booking/views.py` — POST-only, owner-scoped, woła service, flash + redirect.
4. **URL** `booking:cancel` na `/bookings/<int:pk>/cancel/`.
5. **Wire "Anuluj"** w `my_bookings.html` — disabled placeholder → realny POST form dla `can_be_cancelled`.
6. **Testy** — model method + service + view (~15).

### Faza (PENDING-only) — uzasadnienie

m3_planning sekwencjonuje cancel przed refundem żeby izolować ryzyko Stripe:

- **US-23 (ten):** cancel PENDING (brak płatności → czysta zmiana statusu, bez Stripe).
- **US-27:** rozszerza o CONFIRMED — `stripe.Refund.create()` przed status change. Wtedy `can_be_cancelled()` rozszerza się o `CONFIRMED`, a `cancel_booking` dostaje refund branch.

Konsekwencja: "Anuluj" button aktywny tylko dla cancellable PENDING; CONFIRMED zostaje disabled do US-27. (PENDING zwykle wygasa sam via US-26, więc user value US-23 jest ograniczony standalone — to świadomy trade-off za izolację Stripe risk.)

### Out of scope (defer'd)

- **Refund CONFIRMED** (`stripe.Refund.create`, `refund_id`/`refunded_at`) → **US-27**.
- **Cancel z poziomu booking detail page** — US-23 wire'uje tylko `my_bookings.html` (gdzie FR-09 umieszcza button). Detail page cancel opcjonalnie później.
- **`expire_pending_bookings`** (auto-cancel stale PENDING) → US-26 (osobny command).

---

## 2. Architektura plików

### Tworzone

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `tests/booking/test_cancel_view.py` | Create | `BookingCancelView` tests |

### Edytowane

| Plik | Zmiana |
|------|--------|
| `apps/booking/models.py` | + `Booking.can_be_cancelled()` + importy `timedelta`/`timezone` |
| `apps/booking/services.py` | + `cancel_booking` + `BookingNotCancellableError` |
| `apps/booking/views.py` | + `BookingCancelView` |
| `apps/booking/urls.py` | + `path("bookings/<int:pk>/cancel/", ..., name="cancel")` |
| `templates/booking/my_bookings.html` | disabled "Anuluj" → POST form dla `can_be_cancelled` |
| `tests/booking/test_models.py` | + `TestCanBeCancelled` |
| `tests/booking/test_services.py` | + `TestCancelBooking` |
| `.Claude/backlog.md` | US-23 → Done (po merge) |

Brak migracji (`can_be_cancelled` to method, nie pole).

---

## 3. Model method — `apps/booking/models.py`

Dodać importy na górze:

```python
from datetime import timedelta

from django.utils import timezone
```

Method na `Booking`:

```python
def can_be_cancelled(self) -> bool:
    """True when this booking may still be cancelled by its owner (FR-10).

    US-23 scope: PENDING bookings up to 1h before the screening. US-27 will
    broaden this to CONFIRMED (which additionally requires a Stripe refund).
    """
    return (
        self.status == BookingStatus.PENDING
        and self.screening.start_time > timezone.now() + timedelta(hours=1)
    )
```

### Decyzje uzasadnione

1. **Model method (nie view/template helper).** Reused przez: cancel view (authorize), `my_bookings.html` (show/hide button), `cancel_booking` service (re-check), US-27 (broaden). Single source of truth dla reguły FR-10.
2. **PENDING-only teraz.** US-27 zmienia warunek na `status in (PENDING, CONFIRMED)`. Trzymanie PENDING-only unika half-implemented CONFIRMED cancel (button by się pokazał, a cancel by nie zwracał kasy).
3. **`> now() + 1h`** dokładnie per FR-10 (`start_time > now() + timedelta(hours=1)`).
4. **`screening.start_time` access** — 1 query jeśli screening nie prefetched. W template (`my_bookings.html`) screening jest `select_related` (US-22) → 0 extra. W service re-check po locku — booking re-fetched, screening lazy (1 query, akceptowalne).

---

## 4. Service — `apps/booking/services.py` (append)

```python
class BookingNotCancellableError(BookingError):
    """Booking can't be cancelled (wrong status, too late, or already cancelled)."""

    def __init__(self) -> None:
        super().__init__("Tej rezerwacji nie można już anulować.")


def cancel_booking(*, booking: Booking) -> Booking:
    """Cancel a PENDING booking race-safely (FR-10).

    Locks the booking row, re-checks can_be_cancelled() under the lock, flips
    status to CANCELLED and clears expires_at. Raises BookingNotCancellableError
    if the booking is no longer cancellable (e.g. expire_pending_bookings or a
    concurrent cancel won the race). Caller verifies ownership. US-27 will add a
    Stripe refund branch for CONFIRMED bookings before the status change.
    """
    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(pk=booking.pk)
        if not locked.can_be_cancelled():
            raise BookingNotCancellableError()
        locked.status = BookingStatus.CANCELLED
        locked.expires_at = None
        locked.save(update_fields=["status", "expires_at"])
    return locked
```

### Decyzje uzasadnione

1. **Service (nie inline w view).** Mirror `create_booking` (US-20) — shared web+API (M4), extended przez US-27 (refund w tym samym atomic boundary). Unit-testable bez HTTP.
2. **`transaction.atomic()` + `select_for_update()` na Booking.** Per FR §5.x ("każda zmiana stanu w atomic z select_for_update na Booking"). Chroni przed race z `expire_pending_bookings` (US-26) i double-cancel — lost-update prevention.
3. **Re-check `can_be_cancelled()` POD lockiem.** Booking mógł zmienić status między template render a POST (expire/concurrent). Authoritative.
4. **`expires_at = None` przy CANCELLED.** Spójne z `CancelledBookingFactory` (US-18). Cancelled booking nie ma expiry semantyki; clear.
5. **`save(update_fields=[...])`.** Minimalny UPDATE.
6. **Caller verifies ownership** (jak create_booking trusts seats range). View robi owner-scoped fetch; service operuje na bookingu. M4 API zrobi własny owner check.
7. **Booking re-fetch bez `select_related("screening")`.** `select_for_update` + select_related lockowałby też wiersz screening (Postgres) — niepotrzebny lock kontendujący z create_booking. Lazy screening access w `can_be_cancelled` = 1 unlocked query, OK.

---

## 5. View — `apps/booking/views.py` (append)

```python
class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        try:
            cancel_booking(booking=booking)
        except BookingError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Rezerwacja została anulowana.")
        return redirect("booking:my_bookings")
```

Import: dorzuć `cancel_booking` do `from apps.booking.services import BookingError, create_booking` → `BookingError, cancel_booking, create_booking`.

### Decyzje uzasadnione

1. **`View` z tylko `post()`.** State-changing → POST only. GET → 405 automatycznie (View bez `get`). FR-10 `POST /bookings/<id>/cancel/`.
2. **`LoginRequiredMixin`.** FR-10 wymaga logowania; anon → login redirect.
3. **Owner-scoped `get_object_or_404(Booking, pk=pk, user=request.user)`.** Non-owner → 404 (hides existence; lepiej niż 403 dla owner-scoping przy state change). FR-10 "tylko właściciel".
4. **`except BookingError`** (base — łapie `BookingNotCancellableError`). Error flash; success flash gdy OK. Oba → redirect `my_bookings` (FR-10).
5. **Brak własnego re-check w view** — deleguje do `cancel_booking` (authoritative pod lockiem). View tylko owner + flash.

---

## 6. URL — `apps/booking/urls.py` (append)

```python
from apps.booking.views import (
    BookingCancelView,
    BookingCreateView,
    BookingDetailView,
    MyBookingsView,
)

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="detail"),
    path("bookings/<int:pk>/cancel/", BookingCancelView.as_view(), name="cancel"),
    path("my-bookings/", MyBookingsView.as_view(), name="my_bookings"),
]
```

`booking:cancel` → `/bookings/<id>/cancel/`. Brak konfliktu z `booking:detail` (`/bookings/<id>/` vs `/bookings/<id>/cancel/`).

---

## 7. Template — `templates/booking/my_bookings.html`

Zamienić disabled placeholder (US-22):

```django
{% if active_tab == 'upcoming' and booking.status != 'CANCELLED' %}<button class="btn btn-sm btn-outline-danger" disabled title="Dostępne wkrótce">Anuluj</button>{% endif %}
```

na realny POST form gated by `can_be_cancelled` (jedna linia — Django tag rules):

```django
{% if booking.can_be_cancelled %}<form method="post" action="{% url 'booking:cancel' pk=booking.pk %}" class="d-inline">{% csrf_token %}<button type="submit" class="btn btn-sm btn-outline-danger">Anuluj</button></form>{% endif %}
```

`can_be_cancelled` (method, bez parens w template). PENDING-only → CONFIRMED nie pokazuje buttona (do US-27).

---

## 8. Tests scope

### `tests/booking/test_models.py` — append `TestCanBeCancelled`
- `test_pending_future_over_1h_true` — PENDING, start +7d → True.
- `test_pending_under_1h_false` — PENDING, start +30min → False.
- `test_pending_past_false` — PENDING, start -1d → False.
- `test_confirmed_false` — CONFIRMED, start +7d → False (PENDING-only).
- `test_cancelled_false` — CANCELLED → False.

### `tests/booking/test_services.py` — append `TestCancelBooking`
- `test_cancels_pending` — PENDING cancellable → status CANCELLED, `expires_at is None`.
- `test_raises_for_confirmed` — CONFIRMED → `BookingNotCancellableError`, status unchanged.
- `test_raises_when_too_late` — PENDING start +30min → raises, status unchanged.
- `test_raises_when_already_cancelled` — CANCELLED → raises (idempotent double-cancel guard).

### `tests/booking/test_cancel_view.py` (new)
- `test_anonymous_redirected_to_login` — anon POST → 302 login.
- `test_get_not_allowed` — GET → 405.
- `test_owner_cancels_pending` — owner POST PENDING cancellable → 302 `my_bookings`, status CANCELLED, success message.
- `test_non_owner_404` — inny user POST → 404, booking status unchanged.
- `test_not_cancellable_flashes_error` — CONFIRMED (lub too-late) POST → 302 `my_bookings`, error message, status unchanged.
- `test_404_for_missing_booking` — pk=999999 → 404.

**Razem:** ~15 testów.

---

## 9. Definition of Done

- [ ] **Model:** `Booking.can_be_cancelled()` — PENDING + `start_time > now+1h`.
- [ ] **Service:** `cancel_booking` — atomic + `select_for_update` + re-check + CANCELLED + clear expires_at; `BookingNotCancellableError`.
- [ ] **View:** `BookingCancelView` — POST-only, owner-scoped (404), flash + redirect `my_bookings`.
- [ ] **URL:** `booking:cancel` na `/bookings/<int:pk>/cancel/`.
- [ ] **Template:** "Anuluj" POST form dla `can_be_cancelled` w `my_bookings.html`.
- [ ] **Testy:** ~15 (model 5 + service 4 + view 6), green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff`, `ruff format --check`, `mypy` — clean.
- [ ] **No regression:** istniejące testy pass; `makemigrations --check` exits 0 (method, nie pole).
- [ ] **Manual smoke:** login → utwórz PENDING booking (US-20) → `/my-bookings/` → "Anuluj" widoczny → klik → flash "anulowana" + status CANCELLED w Historia (nie, zostaje — sprawdź że znika z upcoming bo... status CANCELLED nadal upcoming jeśli start future; pokazuje się w Nadchodzące z badge "Anulowana", bez buttona).

---

## 10. Risks

1. **Race z `expire_pending_bookings` (US-26) / double-cancel.** Concurrent flip tego samego PENDING. `select_for_update` + re-check `can_be_cancelled()` pod lockiem → drugi przegrywa (status już != PENDING → raises). Test `test_raises_when_already_cancelled` pokrywa logikę (deterministic, bez threadów — US-23 nie wymaga threaded testu jak US-20, bo to prosty single-row guard).
2. **`mypy` `get_object_or_404(Booking, ..., user=request.user)`.** Ten sam django-stubs problem co dev pitfall #12 (`user` lookup = `User | AnonymousUser`). Fix: `cast("User", request.user)` (jak US-22) lub `user=request.user.pk`. Zaadresować w quality gate.
3. **CANCELLED booking nadal w "Nadchodzące" tab.** Tab filter (US-22) jest po `screening.start_time`, NIE po statusie. Cancelled future booking pokazuje się w Nadchodzące z badge "Anulowana" i bez "Anuluj" buttona (`can_be_cancelled` False bo status != PENDING). To poprawne (user widzi że anulował). Brak zmiany US-22 logiki.
4. **`can_be_cancelled` N+1 w my_bookings loop.** Wywołuje `self.screening.start_time` — US-22 ma `select_related("screening__movie","screening__hall")` więc screening prefetched → 0 extra. Budget test US-22 (cap 6) nadal trzyma (bez nowych queries per row). Zweryfikować że budget nie pęka.
5. **GET → 405.** `View` bez `get()` zwraca 405 z `Allow: POST`. Test `test_get_not_allowed` pokrywa. (Browser nie zrobi GET — button to POST form; ale endpoint hygiene.)
6. **Owner 404 vs 403.** US-21 detail użył 403 (UserPassesTestMixin). US-23 cancel używa owner-scoped queryset → 404. Niespójność celowa: detail to read (403 mówi "istnieje, brak dostępu"), cancel to state change (404 hides existence — bezpieczniejsze przy mutacji). Udokumentowane.
