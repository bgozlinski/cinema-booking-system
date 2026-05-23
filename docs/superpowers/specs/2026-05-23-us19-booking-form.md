# US-19 — BookingForm + validation logic (FR-07)

**Data:** 2026-05-23
**Branch (planned):** `feat/FR-07-booking-form` (off `main`)
**Estymata:** M (mała — ~2-3h; jeden form, jeden plik testów)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-19 jako #2, **plan-directly / brak brainstormingu** — pure-Django Form)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-07 (rezerwacja biletów), §3.8 (Booking — reguły walidacji)
- `apps/booking/models.py::Booking` — model docelowy (US-18, merged); `clean()` celowo pusty, walidacja business idzie tutaj
- `apps/cinema/models.py::Screening` — `available_seats_count()` + `is_in_past()` (US-18 real impl) — używane przez walidację formularza
- `apps/cinema/forms.py::MovieFilterForm` — wzorzec plain `forms.Form` w projekcie

---

## 1. Cel

US-19 dostarcza **warstwę walidacji wejścia** dla flow rezerwacji (FR-07). To pure-Django `Form` z jednym polem (`seats_count`) i dwiema walidacjami serwerowymi. **Bez widoku, bez transakcji, bez Stripe** — to wszystko US-20.

Zakres:

1. **`BookingForm`** w nowym pliku `apps/booking/forms.py` — `forms.Form` (NIE `ModelForm`) z polem `seats_count` ∈ [1, 10].
2. **Wstrzyknięcie `screening`** przez `__init__` (keyword-only) — formularz potrzebuje kontekstu seansu do walidacji dostępności i czasu rozpoczęcia.
3. **Walidacja `clean_seats_count`** — `seats_count <= screening.available_seats_count()`; błąd zawiera liczbę dostępnych miejsc (FR-07).
4. **Walidacja `clean`** — `not screening.is_in_past()`; błąd ogólny "Seans już się rozpoczął".
5. **Testy** w `tests/booking/test_forms.py` (~17 testów: valid/range/availability/past).

### Dlaczego walidacja w formularzu, nie w `Booking.clean()`

Per spec US-18 (§4 decyzja 6): `Booking.clean()` jest celowo pusty, bo:
- `full_clean()` NIE jest auto-wywoływany przy `objects.create(...)` (factory_boy + seed_db pomijają),
- walidacja wymaga query (`screening.available_seats_count()`) — coupling z query layer,
- form/serializer layer ma kontekst requestu i (w US-20) `transaction.atomic`,
- Django convention: model = kształt danych; form = walidacja wejścia.

### Out of scope (defer'd)

- **Booking create view** (`POST /screenings/<id>/book/`), `LoginRequiredMixin`, `select_for_update`, `transaction.atomic`, ustawianie `user`/`status`/`expires_at` → **US-20**.
- **Template** `booking_form.html` + podsumowanie (tytuł/godzina/hall/cena/łączna cena JS) → **US-20** (form renderuje się w widoku tam).
- **Race-condition recheck** wewnątrz `select_for_update` (form check to UX pre-check; autorytatywny recheck w US-20) → **US-20**.
- **Edit booking** (`seats_count` "z uwzględnieniem siebie") — US-19 to create-only; §3.8 wzmianka o edycji nie dotyczy tego flow.
- Stripe Checkout → US-24.

---

## 2. Architektura plików

### Tworzone

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `apps/booking/forms.py` | Create | `BookingForm` — pole `seats_count` + 2 walidacje FR-07 |
| `tests/booking/test_forms.py` | Create | Unit testy `BookingForm` (~17) |

### Edytowane

| Plik | Akcja | Kiedy |
|------|-------|-------|
| `.Claude/backlog.md` | US-19 status board → Done; In Progress → US-20 | Po merge |

### Stan obecny (zweryfikowane)

| Element | Stan |
|---------|------|
| `apps/booking/models.py::Booking` | ✅ exists (US-18); `clean()` pusty |
| `apps/booking/forms.py` | ❌ nie istnieje (tworzymy) |
| `apps/cinema/models.py::Screening.available_seats_count()` | ✅ real impl (US-18) — `hall.capacity - booked_seats_count()` |
| `apps/cinema/models.py::Screening.is_in_past()` | ✅ `start_time <= timezone.now()` |
| `tests/booking/factories.py` | ✅ `BookingFactory` (PENDING, expires +15m), `ConfirmedBookingFactory`, `CancelledBookingFactory` |
| `tests/cinema/factories.py` | ✅ `ScreeningFactory` (hall cap 100, start +7d, price 25.00), `HallFactory` (cap override) |

---

## 3. Design — `BookingForm`

### `apps/booking/forms.py`

```python
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.cinema.models import Screening


class BookingForm(forms.Form):
    """Reservation input form (FR-07).

    Collects only ``seats_count``. The owning view (US-20) supplies user,
    screening, status and expires_at when persisting the Booking. The screening
    being booked is injected via ``__init__`` so the two server-side validations
    can run: seats within current availability, and the screening not in the past.
    The view re-checks availability inside ``select_for_update`` (US-20) — this
    form check is the user-facing pre-check, not the authoritative race guard.
    """

    seats_count = forms.IntegerField(
        label=_("Liczba miejsc"),
        min_value=1,
        max_value=10,
        error_messages={
            "required": _("Podaj liczbę miejsc."),
            "invalid": _("Podaj poprawną liczbę miejsc."),
            "min_value": _("Musisz zarezerwować co najmniej 1 miejsce."),
            "max_value": _("Maksymalnie możesz zarezerwować 10 miejsc."),
        },
        widget=forms.NumberInput(attrs={"min": 1, "max": 10, "class": "form-control"}),
    )

    def __init__(self, *args: Any, screening: Screening, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.screening = screening

    def clean_seats_count(self) -> int:
        seats_count: int = self.cleaned_data["seats_count"]
        available = self.screening.available_seats_count()
        if seats_count > available:
            raise forms.ValidationError(
                _("Dostępnych jest tylko %(available)d miejsc — wybierz mniejszą liczbę."),
                code="exceeds_available",
                params={"available": available},
            )
        return seats_count

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if self.screening.is_in_past():
            raise forms.ValidationError(
                _("Seans już się rozpoczął — nie można zarezerwować miejsc."),
                code="screening_in_past",
            )
        return cleaned_data
```

### Decyzje uzasadnione

1. **`forms.Form`, NIE `ModelForm`.** Formularz zbiera tylko `seats_count`. Pozostałe pola Booking (`user`, `screening`, `status`, `expires_at`) ustawia widok (US-20), nie input usera. `ModelForm(fields=["seats_count"])` dorzuciłby ukrytą zależność od modelu bez zysku — walidacja dostępności i tak potrzebuje `screening` spoza pól formularza. Plain `Form` jest jaśniejszy i mirroruje `MovieFilterForm`.

2. **`screening` jako keyword-only w `__init__`.** Widok wywołuje `BookingForm(request.POST, screening=screening)`. Keyword-only (brak default) wymusza podanie — formularz bez seansu nie ma sensu. `*args, **kwargs` zachowuje kompatybilność z `BaseForm.__init__`.

3. **Zakres [1, 10] przez `IntegerField(min_value, max_value)`.** Walidacja pola (przed `clean_seats_count`). Django pomija `clean_seats_count` jeśli pole nie przeszło walidacji bazowej — więc w `clean_seats_count` `seats_count` jest gwarantowanym int ∈ [1, 10].

4. **Dostępność w `clean_seats_count` (błąd przy polu).** Błąd ląduje pod polem `seats_count` (dobre UX). Komunikat zawiera liczbę dostępnych miejsc przez `params` + `%(available)d` placeholder (idiom Django — odracza interpolację, działa z `gettext_lazy`).

5. **Czas seansu w `clean` (błąd ogólny / non-field).** Sprawdzenie nie zależy od żadnego pola — to własność seansu. Plain `ValidationError` w `clean()` → `non_field_errors()` / `__all__`. Reużywa istniejącego `Screening.is_in_past()` (`start_time <= now`).

6. **Dwa niezależne błędy mogą wystąpić razem.** Jeśli seans jest w przeszłości I `seats_count` przekracza dostępność — pokażą się oba błędy (field + non-field). To akceptowalne (rzadki przypadek; oba są prawdziwe). Brak short-circuit upraszcza logikę.

7. **Custom polskie `error_messages`.** UI domyślnie polski (LocaleMiddleware). Komunikaty zakresu/required/invalid spójne językowo zamiast domyślnych angielskich Django.

8. **Brak ochrony przed race condition tutaj.** Form check czyta `available_seats_count()` w momencie walidacji (bez locka). Autorytatywny recheck idzie do US-20 wewnątrz `select_for_update` + `transaction.atomic`. Spec US-20 MUSI to zaadresować.

---

## 4. Tests scope — `tests/booking/test_forms.py`

Pattern jak `tests/cinema/test_movie_filter_form.py` (`pytestmark = pytest.mark.django_db`, klasy grupujące).

Helper: `_future_screening(capacity=100)` → `ScreeningFactory(hall=HallFactory(capacity=capacity))`.

### `TestBookingFormValid`
- `test_valid_seats_within_availability` — cap 100, request 3 → valid, `cleaned_data["seats_count"] == 3`
- `test_one_seat_boundary_valid` — request 1 → valid
- `test_ten_seats_boundary_valid` — cap 100, request 10 → valid
- `test_seats_equal_to_available_valid` — cap 5, request 5 → valid (granica)

### `TestBookingFormFieldRange`
- `test_zero_seats_invalid` — request 0 → invalid, błąd na `seats_count`
- `test_eleven_seats_invalid` — request 11 → invalid, błąd na `seats_count`
- `test_missing_seats_invalid` — `data={}` → invalid, `seats_count` required
- `test_non_integer_seats_invalid` — `"abc"` → invalid

### `TestBookingFormAvailability`
- `test_seats_exceed_capacity_invalid` — cap 5, request 6 (pole OK bo ≤10, dostępność fail) → invalid
- `test_error_message_includes_available_count` — cap 4, request 5 → invalid, `"4"` w treści błędu
- `test_confirmed_bookings_reduce_availability` — cap 10, `ConfirmedBookingFactory(seats_count=7)` → request 4 invalid (dostępne 3)
- `test_active_pending_reduces_availability` — cap 10, `BookingFactory(seats_count=8)` (PENDING, expires +15m) → request 3 invalid
- `test_expired_pending_does_not_reduce_availability` — cap 10, PENDING z `expires_at = now - 1min` → request 9 valid (expired nie liczone)
- `test_sold_out_screening_invalid` — cap 5, CONFIRMED 5 seats → request 1 invalid

### `TestBookingFormPastScreening`
- `test_past_screening_invalid` — `start_time = now - 1h` → invalid
- `test_past_screening_error_is_non_field` — j.w. → `form.non_field_errors()` niepuste
- `test_screening_starting_now_invalid` — `start_time = now()` → invalid (`is_in_past` = `<= now`)

**Razem:** ~17 testów.

---

## 5. Definition of Done

- [ ] **`BookingForm`:** `apps/booking/forms.py` — `forms.Form`, pole `seats_count` ∈ [1,10], `screening` injected w `__init__`, `clean_seats_count` (dostępność) + `clean` (past).
- [ ] **Komunikat dostępności** zawiera liczbę dostępnych miejsc (FR-07).
- [ ] **Past-screening błąd** jako non-field error.
- [ ] **Testy:** ~17 w `tests/booking/test_forms.py`, wszystkie green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff check`, `ruff format --check`, `mypy` — clean.
- [ ] **No regression:** istniejące testy pass; `makemigrations --check` exits 0 (brak zmian modeli — sanity).
- [ ] **Backlog:** US-19 → Done; In Progress → US-20.

---

## 6. Risks

1. **mypy + LSP na `__init__`.** Dodanie wymaganego keyword-only `screening` do `__init__` może wywołać ostrzeżenie django-stubs o niekompatybilnej sygnaturze z `BaseForm.__init__`. **Mitigation:** `*args/**kwargs` zachowane; jeśli mypy zgłosi LSP violation — `screening` z default `None` + assert, lub `# type: ignore[override]` z komentarzem. Zweryfikować w plan-phase quality gate.

2. **`is_in_past` granica "now".** Test `start_time = now()` polega na tym, że `timezone.now()` w `is_in_past()` jest minimalnie późniejszy niż przy tworzeniu screeningu → `<= now` True. Mikrosekundowa różnica gwarantuje invalid. Stabilne, ale gdyby kiedyś flakowało — użyć `now - timedelta(seconds=1)`.

3. **`clean_seats_count` zakłada obecność `seats_count` w `cleaned_data`.** Bezpieczne: Django wywołuje `clean_<field>` TYLKO gdy pole przeszło walidację bazową. Przy invalid (0/11/brak/"abc") metoda nie jest wołana. Brak `KeyError`.

4. **Form check ≠ race guard.** `available_seats_count()` bez locka → dwóch userów może przejść walidację jednocześnie. **To akceptowalne w US-19** (UX pre-check). Autorytatywny recheck = US-20 spec (flagged w §3 decyzja 8).

5. **TZ-aware `expires_at` w testach.** `BookingFactory` default `expires_at = now + 15min` (active). Test "expired" override na `now - 1min`. `booked_seats_count` Q używa `expires_at__gt=now` — expired poprawnie wykluczone. Brak DST gotcha bo wszystko relatywne do `timezone.now()`.
