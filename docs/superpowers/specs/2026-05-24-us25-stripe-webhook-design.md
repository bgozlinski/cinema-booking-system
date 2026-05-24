# US-25 — Stripe webhook + StripeEvent idempotency — design

**Data:** 2026-05-24
**Branch (planned):** `feat/FR-22-stripe-webhook` (off `main`)
**Estymata:** L (webhook view + dispatch service + idempotency + config + tests)
**Powiązane:**
- `.Claude/m3_planning.md` — M3 brief (US-25 jako #9, **brainstorm-required**)
- `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-22 (Stripe webhooks), §3.9 (StripeEvent)
- `apps/payments/models.py::StripeEvent` (US-18) — idempotency log (event_id unique, payload JSONField, processed_at)
- `apps/payments/services.py::create_checkout_session` (US-24) — ustawia `client_reference_id=str(booking.id)` na sesji
- `apps/booking/models.py::Booking` — `status`, `stripe_payment_intent_id`, `expires_at`
- `settings/base.py` — `STRIPE_API_KEY` (US-24); `settings/urls.py` — mount point

---

## 1. Cel

US-25 domyka pętlę płatności (FR-22): Stripe woła `POST /webhooks/stripe/` po zdarzeniach; handler weryfikuje sygnaturę, deduplikuje przez `StripeEvent`, i przenosi Booking PENDING→CONFIRMED (po opłaceniu) lub PENDING→CANCELLED (po wygaśnięciu sesji). To zdarzenie, nie redirect z US-24, jest autorytatywnym potwierdzeniem płatności.

Zakres:

1. **Webhook view** `apps/payments/views.py::stripe_webhook` — function-based, `@csrf_exempt @require_POST`; weryfikuje sygnaturę (`construct_event`), deleguje do service, zwraca 200/400.
2. **Dispatch service** `apps/payments/services.py::process_webhook_event(event: dict) -> bool` — idempotencja (all-in-one atomic) + dispatch po event_type.
3. **URL** `apps/payments/urls.py` (`app_name="payments"`) + mount w `settings/urls.py` → `/webhooks/stripe/`.
4. **Config** — `STRIPE_WEBHOOK_SECRET` w settings + `.env.example` + Stripe CLI note.
5. **Testy** — service (pure dict, bez Stripe mock) + view (mock `construct_event`).

### Decyzje z brainstormingu (2026-05-24)

| # | Decyzja | Wybór | Powód |
|---|---------|-------|-------|
| 1 | Event coverage | **`checkout.session.completed` + `checkout.session.expired`** act; reszta log-only | Oba czytają `client_reference_id` z session object (US-24 ustawia) — brak zmian US-24; `payment_intent.payment_failed` pomijamy (hosted Checkout retry'uje w-sesji + brak payment_intent metadata) |
| 2 | Idempotency | **All-in-one `transaction.atomic()`**: get_or_create + dispatch + processed_at | "Event row committed" ⟺ "fully processed"; crash → rollback → clean retry; unique event_id serializuje concurrent retries |
| 3 | Paid-after-cancel | **Tylko PENDING→CONFIRMED**; non-PENDING → log + 200, brak zmiany | MVP; płatność po naszym cancel (15-min cron vs 24h session) = known limitation, refund follow-up (US-27) |
| 4 | View/service split | **View weryfikuje sygnaturę; service bierze plain `dict`** | Service testowalny bez Stripe mocka (czyste dict); view test mockuje `construct_event` |
| 5 | View type | **Function-based `@csrf_exempt @require_POST`** | Canonical dla webhooków; CBV csrf_exempt jest fiddly |

### Out of scope (defer'd)

- **`payment_intent.payment_failed` → CANCELLED** — pomijamy (decyzja #1). Gdyby kiedyś: US-24 musi dodać `payment_intent_data.metadata.booking_id`.
- **Refund przy paid-after-cancel** — known limitation; refund machinery → **US-27**.
- **Admin StripeEvent** — minimal `StripeEventAdmin` istnieje (US-18, read-only). Enhancements (jeśli) → US-28.
- **REST/unified webhook** (pod `/api/`) → M4.

---

## 2. Architektura — verify w view, dispatch w service

```
View (apps/payments/views.py)  — @csrf_exempt @require_POST function view
  stripe_webhook(request):
    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)
    process_webhook_event(json.loads(payload))     # verified → plain dict
    return HttpResponse(status=200)
  │
  ▼
Service (apps/payments/services.py)
  process_webhook_event(event: dict) -> bool       # idempotency + dispatch (atomic)
    _dispatch(event)  → _confirm(session) | _cancel_expired(session) | no-op
    _lock_booking(client_reference_id)             # select_for_update
```

**Seam:** view = HTTP + Stripe signature (raw body + secret). Service = pure-Python dict logic (idempotency + domain). Service tests pass dicts (no Stripe SDK); view test mocks `construct_event`.

---

## 3. Service — `apps/payments/services.py` (append)

```python
from django.db import transaction
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from apps.payments.models import StripeEvent


def process_webhook_event(event: dict) -> bool:
    """Idempotently process a verified Stripe event. Returns True if newly processed.

    get_or_create + dispatch + processed_at run in ONE transaction, so a committed
    StripeEvent row means the event was fully processed. Duplicates (Stripe retries)
    return False without re-applying state. The unique event_id serializes concurrent
    retries.
    """
    with transaction.atomic():
        stripe_event, created = StripeEvent.objects.get_or_create(
            event_id=event["id"],
            defaults={"event_type": event["type"], "payload": event},
        )
        if not created:
            return False
        _dispatch(event)
        stripe_event.processed_at = timezone.now()
        stripe_event.save(update_fields=["processed_at"])
    return True


def _dispatch(event: dict) -> None:
    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type == "checkout.session.completed":
        _confirm_booking(obj)
    elif event_type == "checkout.session.expired":
        _expire_booking(obj)
    # any other type → audit-logged only (no state change)


def _confirm_booking(session: dict) -> None:
    booking = _lock_booking(session.get("client_reference_id"))
    if booking is None or booking.status != BookingStatus.PENDING:
        return
    booking.status = BookingStatus.CONFIRMED
    booking.stripe_payment_intent_id = session.get("payment_intent") or ""
    booking.expires_at = None
    booking.save(update_fields=["status", "stripe_payment_intent_id", "expires_at"])


def _expire_booking(session: dict) -> None:
    booking = _lock_booking(session.get("client_reference_id"))
    if booking is None or booking.status != BookingStatus.PENDING:
        return
    booking.status = BookingStatus.CANCELLED
    booking.save(update_fields=["status"])


def _lock_booking(client_reference_id) -> Booking | None:
    if not client_reference_id:
        return None
    try:
        return Booking.objects.select_for_update().get(pk=int(client_reference_id))
    except (Booking.DoesNotExist, ValueError, TypeError):
        return None
```

### Decyzje uzasadnione

1. **`payload=event`** w get_or_create defaults — przechowujemy pełny event dict (JSONField). View przekazuje `json.loads(request.body)` (verified raw body) jako `event`.
2. **`if not created: return False`** wewnątrz atomic — dup → 200 (view). Atomicity #2: row exists ⟺ processed.
3. **`_lock_booking` z `select_for_update`** wewnątrz outer atomic — chroni przed race z `cancel_booking`/`expire_pending_bookings`/concurrent webhook. Lock w tej samej transakcji co StripeEvent.
4. **Guard `booking.status != PENDING → return`** — tylko PENDING→CONFIRMED/CANCELLED (decyzja #3). CONFIRMED/CANCELLED booking → no-op (idempotent na poziomie domeny + paid-after-cancel limitation).
5. **`_confirm_booking` clearuje `expires_at`** (spójne z ConfirmedBookingFactory). `stripe_payment_intent_id` z `session["payment_intent"]` (FR-22).
6. **`_expire_booking` zostawia `expires_at`** (Stripe-driven expiry, jak expire command — audyt).
7. **Missing/invalid `client_reference_id` → `None` → skip** (no raise). Webhook zwraca 200 (processed_at set) → Stripe nie retry'uje w nieskończoność dla nieznanego bookingu.
8. **`_dispatch` no-op dla nieznanych typów** — StripeEvent persisted (audit), brak state change.

---

## 4. View — `apps/payments/views.py` (new)

```python
import json

import stripe
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payments.services import process_webhook_event


@csrf_exempt
@require_POST
def stripe_webhook(request) -> HttpResponse:
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:  # malformed payload
        return HttpResponseBadRequest("Invalid payload")
    except stripe.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")
    process_webhook_event(json.loads(payload))
    return HttpResponse(status=200)
```

### Decyzje uzasadnione

1. **`@csrf_exempt`** — webhook nie ma CSRF tokenu; Stripe signature = autentyczność (FR-22).
2. **`@require_POST`** — GET → 405 (Django).
3. **`construct_event` tylko do weryfikacji** — `ValueError` (malformed) / `stripe.SignatureVerificationError` (bad sig) → 400. Potem `json.loads(payload)` → dict do service.
4. **`stripe.SignatureVerificationError`** — top-level (dev pitfall #13, jak StripeError). Zweryfikować dokładną ścieżkę przy implementacji (może `stripe.error.SignatureVerificationError` w niektórych wersjach — top-level preferowane).
5. **Zwraca 200 nawet gdy `process_webhook_event` → False** (dup) lub no-op — Stripe oczekuje 2xx żeby przestać retry'ować. Tylko sygnatura/payload errors → 400.

---

## 5. URL + config

### `apps/payments/urls.py` (new)

```python
from django.urls import path

from apps.payments.views import stripe_webhook

app_name = "payments"

urlpatterns = [
    path("webhooks/stripe/", stripe_webhook, name="stripe_webhook"),
]
```

### `settings/urls.py` (mount)

```python
path("", include("apps.payments.urls", namespace="payments")),
```

→ `/webhooks/stripe/`. Brak konfliktu (booking/cinema nie używają `webhooks/`).

### `settings/base.py`

```python
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
```

### `.env.example`

```
# From `stripe listen` (Stripe CLI) — local webhook signing secret
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

Plus README/onboarding note: `stripe listen --forward-to localhost:8000/webhooks/stripe/` (CLI prints the `whsec_…` to copy into `.env`).

---

## 6. Tests scope

### `tests/payments/test_webhook_service.py` (pure dicts — NO Stripe mock)

Helper `_event(event_type, *, client_reference_id, payment_intent="pi_test_1", event_id=...)` builds the FR-22 dict shape (`{"id","type","data":{"object":{...}}}`).

- `test_completed_confirms_pending_booking` — PENDING → CONFIRMED + `stripe_payment_intent_id` saved + `expires_at` None; returns True.
- `test_expired_cancels_pending_booking` — PENDING → CANCELLED.
- `test_duplicate_event_is_noop` — call twice z tym samym `event_id` → 2nd returns False; 1 StripeEvent row; booking confirmed once (no double-processing); `StripeEvent.objects.count() == 1`.
- `test_completed_on_confirmed_booking_no_change` — already CONFIRMED → no change (status stays), event still logged + processed_at.
- `test_completed_on_cancelled_booking_no_change` — already CANCELLED (paid-after-cancel) → status stays CANCELLED, event logged.
- `test_unknown_event_type_logged_only` — `payment_intent.payment_failed` → StripeEvent persisted, processed_at set, no booking change.
- `test_missing_booking_does_not_crash` — `client_reference_id="999999"` → no raise, event recorded (processed_at set).
- `test_invalid_client_reference_id_does_not_crash` — `client_reference_id="abc"` → no raise.
- `test_processed_at_set_on_success` — `processed_at is not None` po przetworzeniu.

### `tests/payments/test_webhook_view.py` (`@pytest.mark.stripe`, mock `construct_event`)

Fixture/mock: `mocker.patch("apps.payments.views.stripe.Webhook.construct_event")` (+ patch `process_webhook_event` or let it run with a real booking).

- `test_valid_signature_returns_200_and_processes` — construct_event ok → 200; `process_webhook_event` called (or booking confirmed).
- `test_bad_signature_returns_400` — `construct_event.side_effect = stripe.SignatureVerificationError("bad", "sig")` → 400; no processing.
- `test_malformed_payload_returns_400` — `construct_event.side_effect = ValueError` → 400.
- `test_get_not_allowed` — GET `/webhooks/stripe/` → 405.
- `test_csrf_exempt_post_without_token` — POST bez CSRF (Django test client csrf_checks) → not 403 (csrf-exempt works).

**Razem:** ~14 testów. (Booking lookups via `BookingFactory` PENDING/`ConfirmedBookingFactory`/`CancelledBookingFactory`.)

---

## 7. Definition of Done

- [ ] **View:** `stripe_webhook` — `@csrf_exempt @require_POST`, `construct_event` verify (400 on bad sig/payload), delegates to service, 200.
- [ ] **Service:** `process_webhook_event(dict) -> bool` — all-in-one atomic idempotency (get_or_create + dispatch + processed_at); `_confirm_booking`/`_expire_booking`/no-op; `select_for_update` Booking; PENDING-only guard.
- [ ] **Events:** `checkout.session.completed` → CONFIRMED + payment_intent_id; `checkout.session.expired` → CANCELLED; reszta log-only.
- [ ] **URL:** `payments:stripe_webhook` na `/webhooks/stripe/`; mount w settings.
- [ ] **Config:** `STRIPE_WEBHOOK_SECRET` w settings + `.env.example` + CLI note.
- [ ] **Testy:** ~14 (service pure-dict + view mocked), green.
- [ ] **Quality gates:** `pytest --cov` ≥80%, `ruff`, `ruff format --check`, `mypy` — clean. `makemigrations --check` exits 0 (brak modeli).
- [ ] **Manual smoke (Stripe CLI):** `stripe listen --forward-to localhost:8000/webhooks/stripe/` → kopiuj `whsec_` do `.env` → book + pay (`4242…`) → webhook `checkout.session.completed` → booking CONFIRMED + `stripe_payment_intent_id` set; `/bookings/<id>/` pokazuje status Potwierdzona. End-to-end (US-24 + US-25): book → Stripe → pay → back → CONFIRMED.

---

## 8. Risks

1. **`stripe.SignatureVerificationError` import path.** Top-level (dev pitfall #13). Zweryfikować przy implementacji; jeśli tylko `stripe.error.X` w danej wersji — dostosować (mało prawdopodobne, stripe-python eksponuje top-level).
2. **Paid-after-cancel = money, no seat.** Known MVP limitation (decyzja #3). Refund → US-27. Udokumentować w PR + README.
3. **`construct_event` raw body.** Musi być `request.body` (bytes), NIE parsed — Django nie konsumuje body dla webhook POST (brak form parsing przy non-form content-type). Sig verify potrzebuje exact bytes. `json.loads(payload)` PO weryfikacji.
4. **`get_or_create` w atomic + IntegrityError race.** Django get_or_create używa savepoint (nested atomic) dla IntegrityError — bezpieczne wewnątrz outer atomic. Concurrent dup: Postgres unique blokuje 2nd insert do commitu 1st → loser dostaje created=False. (Decyzja #2.)
5. **`payload` JSONField z `event` dict.** Plain dict (z `json.loads`) — serializowalny do JSONB. Bez problemu (w przeciwieństwie do stripe.Event object). View robi `json.loads` → czysty dict.
6. **CSRF test.** Django `Client` domyślnie nie enforce'uje CSRF (`enforce_csrf_checks=False`). Żeby przetestować csrf_exempt realnie → `Client(enforce_csrf_checks=True).post(...)` i assert nie-403. Inaczej test jest no-op. Test używa `enforce_csrf_checks=True`.
7. **`mypy` function view.** `-> HttpResponse` (HttpResponseBadRequest jest subklasą). `process_webhook_event(event: dict)` — `json.loads` zwraca `Any`, OK. `_lock_booking(client_reference_id)` param untyped (`Any` z dict.get) → `-> Booking | None`.
