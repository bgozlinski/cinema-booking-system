# US-24 — Stripe Checkout integration — design

**Data:** 2026-05-24
**Branch (planned):** `feat/FR-21-stripe-checkout` (off `main`)
**Estymata:** L (replace stub + create_booking refactor + retry endpoint + config + test churn)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-24 jako #8, **brainstorm-required**)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-21 (Stripe Checkout)
- `apps/payments/services.py::create_checkout_session` (US-20 stub) — do zastąpienia
- `apps/booking/services.py::create_booking` (US-20) — refactor (Stripe call wyciągnięty)
- `apps/booking/views.py::BookingCreateView` (US-20) — refactor; `BookingDetailView` (US-21) — extend `?stripe=`
- `settings/base.py` — `environ.Env` config; `pyproject.toml` — marker `stripe` już zarejestrowany

---

## 1. Cel

US-24 zastępuje stub `create_checkout_session` (US-20) realną integracją Stripe Checkout (FR-21): zalogowany user po utworzeniu PENDING bookingu jest przekierowany na hosted Stripe Checkout page; po płatności wraca na booking detail (`?stripe=success`). Webhook PENDING→CONFIRMED to US-25.

Zakres:

1. **`poetry add stripe`** + config (`STRIPE_API_KEY`, `BASE_URL`) w `settings/base.py` + `.env.example`.
2. **Real `create_checkout_session`** (`apps/payments/services.py`) — `stripe.checkout.Session.create(...)`, zwraca `(url, session_id)`, raises `stripe.StripeError`.
3. **`start_checkout` service** (`apps/booking/services.py`) — orkiestracja: woła `create_checkout_session`, zapisuje `stripe_session_id`, zwraca url. Reused przez create-view + retry-view.
4. **Refactor `create_booking`** — wyciągnięcie Stripe call; zwraca `Booking` (było `(booking, checkout_url)`).
5. **Refactor `BookingCreateView.post`** — orkiestruje create_booking → start_checkout; StripeError → flash + redirect detail.
6. **`BookingCheckoutView`** (retry, FR-21) — `POST /bookings/<int:pk>/checkout/`.
7. **Extend `BookingDetailView`** — `?stripe=success|cancelled` flash + "Zapłać" button (PENDING) w `booking_detail.html`.
8. **Testy** — conftest fixture `mock_checkout_session` + refactor US-20 testów + nowe.

### Decyzje z brainstormingu (2026-05-24)

| # | Decyzja | Wybór | Powód |
|---|---------|-------|-------|
| 1 | Stripe-failure handling | **Redirect to detail + retry endpoint** | User może ponowić płatność; PENDING zostaje (opłacalny później) |
| 2 | Session `expires_at` | **Omit** (Stripe default 24h) | Stripe floor = 30min > nasze 15min → API by odrzucił; 15-min hold enforce'd przez `expire_pending_bookings` (US-26) |
| 3 | Test mocking | **Shared conftest fixture** `mock_checkout_session` + `@pytest.mark.stripe` | DRY, reused US-25/US-27; configurable (return / raise) |
| 4 | Service split | **`create_booking` → Booking; `start_checkout` extracted** | SRP; retry endpoint reuse'uje checkout; shared web+API |
| 5 | Idempotency key | **Per-call `uuid4().hex`** (NIE static `booking-<id>-checkout`) | Static key → Stripe replay'uje stałą (wygasłą) sesję przy retry; uuid daje fresh session każdy attempt; duplikaty harmless (client_reference_id + US-25 StripeEvent dedupe) |
| 6 | Env keys | **`STRIPE_API_KEY` + `BASE_URL` teraz** | `STRIPE_WEBHOOK_SECRET` → US-25; `STRIPE_PUBLISHABLE_KEY` skip (hosted checkout redirect nie używa client-side Stripe.js) |

### Out of scope (defer'd)

- **Webhook PENDING→CONFIRMED** (`checkout.session.completed`) + `STRIPE_WEBHOOK_SECRET` → **US-25**.
- **Refund** (cancel CONFIRMED) → US-27.
- **Admin** (BookingAdmin/ScreeningAdmin) → US-28.
- **`STRIPE_PUBLISHABLE_KEY`** — niepotrzebny dla hosted Checkout (redirect na Stripe page; brak embedded Stripe.js).
- **API endpoint** `POST /api/v1/bookings/<id>/checkout/` (DRF, zwraca JSON + 409) → M4 (US-32+). US-24 = web only.

---

## 2. Architektura — 3 warstwy (refactor)

```
View layer (apps/booking/views.py)
  BookingCreateView.post:   create_booking → start_checkout → redirect(url) | StripeError→detail+flash
  BookingCheckoutView.post: (retry) owner+PENDING guard → start_checkout → redirect(url) | flash+detail
  BookingDetailView:        ?stripe=success|cancelled → messages
  │
  ▼
Booking service (apps/booking/services.py)
  create_booking(*, user, screening, seats_count) -> Booking      # PENDING only (Stripe call REMOVED)
  start_checkout(*, booking) -> str                               # calls payments, saves session_id, returns url
  │
  ▼
Payments service (apps/payments/services.py)
  create_checkout_session(booking) -> (url, session_id)           # REAL stripe.checkout.Session.create; raises StripeError
```

Stripe call poza lockiem (jak US-20). `payments.create_checkout_session` = pure Stripe (no DB). `start_checkout` = domain orchestration (DB write `stripe_session_id`). `create_booking` = pure PENDING create (SRP).

---

## 3. Payments — `apps/payments/services.py` (replace stub)

```python
import uuid

import stripe
from django.conf import settings
from django.urls import reverse

from apps.booking.models import Booking

stripe.api_key = settings.STRIPE_API_KEY


def create_checkout_session(booking: Booking) -> tuple[str, str]:
    """Create a real Stripe Checkout Session for a PENDING booking (FR-21).

    Returns (checkout_url, session_id). Raises stripe.StripeError on API/network
    failure — the caller (start_checkout / view) handles it. No DB writes here.
    """
    detail_path = reverse("booking:detail", kwargs={"pk": booking.id})
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "pln",
                    "unit_amount": int(booking.total_price * 100),  # grosze
                    "product_data": {
                        "name": f"Booking #{booking.id} — {booking.screening.movie.title}",
                    },
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(booking.id),
        success_url=f"{settings.BASE_URL}{detail_path}?stripe=success",
        cancel_url=f"{settings.BASE_URL}{detail_path}?stripe=cancelled",
        idempotency_key=uuid.uuid4().hex,
    )
    return session.url, session.id
```

### Decyzje uzasadnione

1. **`stripe.api_key` module-level** — set raz przy imporcie z settings. Standard stripe-python idiom.
2. **`currency="pln"`, `unit_amount=int(total_price*100)`** — grosze (Stripe integer minor units). `total_price` to Decimal → `int(Decimal * 100)`.
3. **`quantity=1`, jedna pozycja** — per FR-21 (unit_amount = cała total_price, nie price-per-seat × seats). Prostsze; seats_count w nazwie/booking, nie w line item quantity.
4. **`client_reference_id=str(booking.id)`** — wiąże webhook (US-25) z bookingiem (loose coupling per StripeEvent §3.9).
5. **`success_url`/`cancel_url`** absolutne przez `settings.BASE_URL` + `reverse("booking:detail")`. `?stripe=success|cancelled` query param.
6. **`idempotency_key=uuid.uuid4().hex`** (per-call) — patrz decyzja #5. NIE static `booking-<id>-checkout` (breakuje retry: Stripe replay'uje wygasłą sesję). Per-call uuid: fresh session każdy attempt; duplikaty harmless.
7. **`expires_at` omitted** — Stripe default 24h (decyzja #2; floor 30min > nasze 15min).
8. **Raises `stripe.StripeError`** — nie łapie tu; propaguje do `start_checkout` → view.

---

## 4. Booking service — `apps/booking/services.py` (refactor + add)

### `create_booking` (refactor — usuń Stripe call)

```python
def create_booking(*, user, screening: Screening, seats_count: int) -> Booking:
    """Create a PENDING booking race-safely (FR-07). Returns the booking.

    Locks the Screening row, re-checks availability + start time under the lock,
    creates the PENDING booking (expires_at = now + 15min). The Stripe checkout
    session is created separately by start_checkout (US-24) so the create flow
    and the retry endpoint share one path. Caller owns seats_count range [1,10].
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
    return booking
```

**Usunięte:** końcowy blok `checkout_url, session_id = create_checkout_session(...)` + `save(stripe_session_id)` + return tuple. Import `create_checkout_session` przenosi się do `start_checkout`.

### `start_checkout` (new)

```python
from apps.payments.services import create_checkout_session


def start_checkout(*, booking: Booking) -> str:
    """Create a Stripe Checkout session for a PENDING booking and return its URL.

    Persists the returned stripe_session_id. Lets stripe.StripeError propagate to
    the view. Shared by BookingCreateView (initial) and BookingCheckoutView (retry).
    """
    checkout_url, session_id = create_checkout_session(booking)
    booking.stripe_session_id = session_id
    booking.save(update_fields=["stripe_session_id"])
    return checkout_url
```

### Decyzje uzasadnione

1. **`create_booking` zwraca `Booking`** (było tuple). SRP — tylko PENDING create. Churn: US-20 view + testy update'owane (patrz §8).
2. **`start_checkout` osobno** — reused przez create + retry view. Zapisuje `session_id` (domain write). Propaguje StripeError (view łapie).
3. **`start_checkout` bez `transaction.atomic`** — single `save(update_fields=...)`; booking już committed. Stripe call poza lockiem (US-20 invariant zachowany).

---

## 5. Views — `apps/booking/views.py`

### `BookingCreateView.post` (refactor)

```python
def post(self, request, pk: int):
    screening = self._get_screening(pk)
    form = BookingForm(request.POST, screening=screening)
    if not form.is_valid():
        return render(request, self.template_name, {"screening": screening, "form": form})
    try:
        booking = create_booking(
            user=request.user,
            screening=screening,
            seats_count=form.cleaned_data["seats_count"],
        )
    except BookingError as exc:
        form.add_error(None, str(exc))
        return render(request, self.template_name, {"screening": screening, "form": form})
    try:
        checkout_url = start_checkout(booking=booking)
    except stripe.StripeError:
        messages.error(
            request,
            "Płatność jest chwilowo niedostępna — spróbuj ponownie z poziomu rezerwacji.",
        )
        return redirect("booking:detail", pk=booking.pk)
    return redirect(checkout_url)
```

(Usunięty `messages.success` + redirect na movie_detail z US-20 — teraz redirect na Stripe hosted page.)

### `BookingCheckoutView` (new — retry)

```python
class BookingCheckoutView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        if booking.status != BookingStatus.PENDING:
            messages.error(request, "Tej rezerwacji nie można już opłacić.")
            return redirect("booking:detail", pk=booking.pk)
        try:
            checkout_url = start_checkout(booking=booking)
        except stripe.StripeError:
            messages.error(request, "Płatność jest chwilowo niedostępna — spróbuj ponownie.")
            return redirect("booking:detail", pk=booking.pk)
        return redirect(checkout_url)
```

### `BookingDetailView` (extend — `?stripe=`)

W `get_context_data` (lub `get`) dorzuć:

```python
    def get(self, request, *args, **kwargs):
        stripe_status = request.GET.get("stripe")
        if stripe_status == "success":
            messages.info(request, "Płatność przyjęta — potwierdzenie rezerwacji wkrótce.")
        elif stripe_status == "cancelled":
            messages.warning(request, "Płatność anulowana. Możesz spróbować ponownie.")
        return super().get(request, *args, **kwargs)
```

### Decyzje uzasadnione

1. **`BookingCheckoutView` POST-only** (state-changing → Stripe call). GET → 405. Owner-scoped 404. Non-PENDING → flash + redirect (FR-21 HTTP 409 honored w API layer M4; web = flash+redirect, spójne z cancel view).
2. **`?stripe=success` → `messages.info`, NIE success** — status nadal PENDING do webhook (US-25). Komunikat honest ("potwierdzenie wkrótce").
3. **Imports:** view dorzuca `import stripe`, `start_checkout`, `BookingStatus`, `BookingCheckoutView` w urls.

---

## 6. URL — `apps/booking/urls.py`

```python
path("bookings/<int:pk>/checkout/", BookingCheckoutView.as_view(), name="checkout"),
```

(obok `create`/`detail`/`cancel`/`my_bookings`). Brak konfliktu (`/bookings/<id>/checkout/` vs `/bookings/<id>/cancel/`).

---

## 7. Template + Config

### `templates/booking/booking_detail.html` — "Zapłać" button

Dla PENDING booking, przycisk POST do `booking:checkout` (jedna linia — Django tag rules):

```django
{% if booking.status == 'PENDING' %}<form method="post" action="{% url 'booking:checkout' pk=booking.pk %}" class="mt-3">{% csrf_token %}<button type="submit" class="btn btn-success">Zapłać</button></form>{% endif %}
```

### `settings/base.py`

```python
STRIPE_API_KEY = env("STRIPE_API_KEY", default="")
BASE_URL = env("BASE_URL", default="http://localhost:8000")
```

### `.env.example`

```
# Stripe (test mode) — get keys at https://dashboard.stripe.com/test/apikeys
STRIPE_API_KEY=sk_test_xxx
BASE_URL=http://localhost:8000
# STRIPE_WEBHOOK_SECRET added in US-25 (Stripe CLI: stripe listen ...)
```

### `pyproject.toml`

`poetry add stripe` → `"stripe (>=x,<y)"` w dependencies.

---

## 8. Tests scope

### `tests/conftest.py` — `mock_checkout_session` fixture (root conftest → widoczny dla booking + payments testów)

```python
@pytest.fixture
def mock_checkout_session(mocker):
    """Patch stripe.checkout.Session.create with a fake session.

    Returns the mock; set .return_value / .side_effect per test. Default returns a
    fake session with .url + .id.
    """
    fake = mocker.MagicMock(url="https://checkout.stripe.test/c/cs_test_123", id="cs_test_123")
    return mocker.patch(
        "apps.payments.services.stripe.checkout.Session.create", return_value=fake
    )
```

### `tests/payments/test_services.py` (rewrite — real-mocked, `@pytest.mark.stripe`)
- `test_creates_session_with_expected_params` — assert `Session.create` called z `mode="payment"`, `client_reference_id=str(id)`, line_items currency/unit_amount, success/cancel urls zawierają BASE_URL + `?stripe=`.
- `test_returns_url_and_session_id` — zwraca `(fake.url, fake.id)`.
- `test_propagates_stripe_error` — fixture `side_effect=stripe.StripeError(...)` → `create_checkout_session` raises.
- (Usunięty: stary `test_create_checkout_session_returns_movie_detail_url_and_empty_session`.)

### `tests/booking/test_services.py` (refactor + add)
- `TestCreateBookingSuccess`: `create_booking(...)` zwraca `Booking` (unpack zmieniony; usunięte url/session_id asserty).
- `TestCreateBookingErrors`: bez zmian (NotEnoughSeats/Past).
- `TestStartCheckout` (new, `@pytest.mark.stripe`, używa `mock_checkout_session`): `start_checkout` zapisuje `stripe_session_id`, zwraca url; `side_effect=StripeError` → propaguje.

### `tests/booking/test_views.py` (refactor — `BookingCreateView`)
- `test_valid_creates_booking_and_redirects` (update): mock checkout → 1 PENDING booking + redirect na `fake.url` (Stripe), nie movie_detail.
- `test_valid_sets_success_message` — usunięty (brak success flash; redirect na Stripe).
- `test_stripe_failure_redirects_to_detail` (new): `mock_checkout_session.side_effect=StripeError` → redirect `booking:detail`, error flash, booking nadal PENDING.
- Reszta (auth/invalid form/service error/past) — bez zmian (create_booking raise path).

### `tests/booking/test_checkout_view.py` (new — retry, `@pytest.mark.stripe`)
- `test_anonymous_redirected_to_login`, `test_get_not_allowed` (405).
- `test_owner_pending_redirects_to_stripe` — mock → redirect `fake.url`, `stripe_session_id` zapisany.
- `test_non_pending_flashes_error` — CONFIRMED/CANCELLED → redirect detail + error, brak Stripe call.
- `test_stripe_failure_flashes_error` — side_effect StripeError → redirect detail + error.
- `test_non_owner_404`.

### `tests/booking/test_detail_view.py` (add)
- `test_stripe_success_shows_info_message` — `?stripe=success` → messages.info.
- `test_stripe_cancelled_shows_warning` — `?stripe=cancelled` → messages.warning.
- `test_pay_button_shown_for_pending` — PENDING → `booking:checkout` URL w content.

**Razem:** ~22 testów (3 payments + ~3 service + ~4 create-view + ~6 checkout-view + ~3 detail + fixture). Churn: ~5 US-20 testów zmienionych/usuniętych.

---

## 9. Definition of Done

- [ ] **Config:** `poetry add stripe`; `STRIPE_API_KEY` + `BASE_URL` w settings + `.env.example`.
- [ ] **`create_checkout_session`:** real `stripe.checkout.Session.create`, params per §3, zwraca `(url, id)`, raises StripeError.
- [ ] **`start_checkout`:** zapisuje `stripe_session_id`, zwraca url, propaguje StripeError.
- [ ] **`create_booking` refactor:** zwraca `Booking` (Stripe call wyciągnięty).
- [ ] **`BookingCreateView`:** create_booking → start_checkout → redirect Stripe; StripeError → detail+flash.
- [ ] **`BookingCheckoutView`:** retry `POST /bookings/<id>/checkout/`, owner+PENDING guard, redirect Stripe.
- [ ] **`BookingDetailView`:** `?stripe=success|cancelled` flash; "Zapłać" button (PENDING) w template.
- [ ] **Idempotency:** per-call `uuid4` key (NIE static).
- [ ] **Testy:** ~22, wszystkie green; `@pytest.mark.stripe` + `mock_checkout_session` fixture; US-20 testy zaktualizowane.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff`, `ruff format --check`, `mypy` — clean. `makemigrations --check` exits 0 (brak modeli).
- [ ] **Manual smoke (Stripe test mode):** login → book → redirect na Stripe Checkout → pay `4242 4242 4242 4242` → redirect `/bookings/<id>/?stripe=success` → info flash (status PENDING do US-25). Booking PENDING + `stripe_session_id` set w admin.

---

## 10. Risks

1. **`create_booking` refactor churn.** Sygnatura `(booking, url)` → `Booking`. Touches US-20 `BookingCreateView` + ~5 testów (test_services create tests, test_views redirect, payments stub test). **Mitigation:** §8 wylicza dokładnie które; TDD red→green pokaże.
2. **24h session vs 15-min hold.** Płatność po naszym 15-min cancel (cron US-26) → webhook (US-25) dostaje completed dla CANCELLED bookingu. **Reconciliation = US-25** (auto-refund lub reactivate). US-24 flag.
3. **Idempotency uuid deviation od FR-21.** Static key breakuje retry (replay wygasłej sesji). uuid per-call → fresh session; duplikaty harmless. Udokumentowane (decyzja #5).
4. **`mypy` + stripe-python types.** `stripe` ma type stubs od v5+? Jeśli `Session.create` zwraca `Any`/nieokreślony typ — `session.url`/`session.id` mogą wymagać `# type: ignore` lub cast. Zaadresować w quality gate (zależne od wersji stripe).
5. **`request.user` lookup w checkout view** — `get_object_or_404(Booking, pk, user=request.user)` = ten sam django-stubs `[misc]` co dev pitfall #12. Fix: `cast("User", request.user)`.
6. **`STRIPE_API_KEY` default=""**. Testy mockują Stripe (brak realnego API call) → pusty klucz OK w CI. Manual smoke wymaga realnego `sk_test_` w `.env`. README/`.env.example` note.
7. **`Session.create` kwargs vs stripe-python wersja.** `idempotency_key` jako kwarg do `.create()` — supported w stripe-python. `price_data` inline (nie pre-created Price) — supported. Zweryfikować przy `poetry add stripe` (wersja w locku).
8. **`?stripe=` open redirect / param injection** — tylko sprawdzamy `== "success"`/`"cancelled"` (whitelist), brak echo usera. Bezpieczne.
