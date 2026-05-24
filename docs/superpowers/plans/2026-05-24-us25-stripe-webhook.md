# US-25 — Stripe webhook + StripeEvent idempotency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /webhooks/stripe/` (FR-22) verifies Stripe's signature, idempotently logs each event, and transitions bookings: `checkout.session.completed` → CONFIRMED (+ payment_intent), `checkout.session.expired` → CANCELLED.

**Architecture:** A `@csrf_exempt` function view verifies the signature (`construct_event`) and passes the parsed `dict` to `payments.services.process_webhook_event`, which does get_or_create + dispatch + `processed_at` in one `transaction.atomic()` (event row committed ⟺ fully processed). Only PENDING bookings transition; everything else is audit-logged. The service is pure-dict (no Stripe SDK) so its tests need no mocking.

**Tech Stack:** `stripe.Webhook.construct_event`, Django function view + `@csrf_exempt`/`@require_POST`, `transaction.atomic` + `select_for_update`, pytest-django + `pytest-mock`.

**Spec źródłowy:** `docs/superpowers/specs/2026-05-24-us25-stripe-webhook-design.md`.

**Role division (per `feedback_role_division` memory):**
- Claude pisze WSZYSTKIE testy (`tests/payments/test_webhook_service.py`, `tests/payments/test_webhook_view.py`).
- Kod aplikacji (`apps/payments/services.py` append, `apps/payments/views.py`, `apps/payments/urls.py`, `settings/urls.py`, `settings/base.py`, `.env.example`) — **default: user wkleja/uruchamia** z planu.
- User odpala wszystkie komendy `git`/`gh` + `pytest`/`ruff`/`mypy` sam.

---

## Branch Strategy

```bash
git checkout main && git pull
git checkout -b feat/FR-22-stripe-webhook
git branch --show-current   # → feat/FR-22-stripe-webhook
```

Spec + plan jako pierwszy commit:

```bash
git add docs/superpowers/specs/2026-05-24-us25-stripe-webhook-design.md \
        docs/superpowers/plans/2026-05-24-us25-stripe-webhook.md
git commit -m "$(cat <<'EOF'
docs(M3): add US-25 Stripe webhook design and plan

Brainstorming + planning for US-25 (FR-22). POST /webhooks/stripe/ verifies the
signature and delegates a parsed dict to process_webhook_event (get_or_create +
dispatch + processed_at in one atomic). completed→CONFIRMED, expired→CANCELLED;
PENDING-only; rest log-only. Paid-after-cancel refund deferred to US-27.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## File Structure

| Plik | Akcja | Odpowiedzialność |
|------|-------|------------------|
| `settings/base.py` | Modify | `STRIPE_WEBHOOK_SECRET` |
| `.env.example` | Modify | webhook secret + CLI note |
| `apps/payments/services.py` | Modify | + `process_webhook_event` + dispatch helpers |
| `apps/payments/views.py` | Create | `stripe_webhook` function view |
| `apps/payments/urls.py` | Create | `payments:stripe_webhook` |
| `settings/urls.py` | Modify | mount payments urls |
| `tests/payments/test_webhook_service.py` | Create | dispatch + idempotency (pure dict) |
| `tests/payments/test_webhook_view.py` | Create | view (mock construct_event) |
| `.Claude/backlog.md` | Modify | US-25 → Done (po merge) |

No migrations (`StripeEvent` exists from US-18).

---

## Task 1: Config — STRIPE_WEBHOOK_SECRET

**Files:** `settings/base.py`, `.env.example`

- [ ] **Step 1: Add the setting** (user edits `settings/base.py`, near `STRIPE_API_KEY`)

```python
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
```

- [ ] **Step 2: Extend `.env.example`** (user edits, under the Stripe block)

```
# From `stripe listen` (Stripe CLI) — local webhook signing secret
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

- [ ] **Step 3: Commit**

```bash
git add settings/base.py .env.example
git commit -m "$(cat <<'EOF'
chore(FR-22): add STRIPE_WEBHOOK_SECRET setting

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Dispatch service + idempotency

**Files:**
- Test: `tests/payments/test_webhook_service.py` (Create)
- Modify: `apps/payments/services.py`

- [ ] **Step 1: Write the failing tests** (`tests/payments/test_webhook_service.py`)

```python
"""Tests for process_webhook_event dispatch + idempotency (US-25 / FR-22)."""

import pytest

from apps.booking.models import BookingStatus
from apps.payments.models import StripeEvent
from apps.payments.services import process_webhook_event
from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)

pytestmark = pytest.mark.django_db


def _event(event_type, *, client_reference_id, payment_intent="pi_test_1", event_id="evt_test_1"):
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "client_reference_id": str(client_reference_id),
                "payment_intent": payment_intent,
            }
        },
    }


class TestProcessWebhookEvent:
    def test_completed_confirms_pending_booking(self):
        booking = BookingFactory()  # PENDING
        result = process_webhook_event(
            _event("checkout.session.completed", client_reference_id=booking.id)
        )
        assert result is True
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.stripe_payment_intent_id == "pi_test_1"
        assert booking.expires_at is None

    def test_expired_cancels_pending_booking(self):
        booking = BookingFactory()
        process_webhook_event(
            _event("checkout.session.expired", client_reference_id=booking.id, event_id="evt_e1")
        )
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_duplicate_event_is_noop(self):
        booking = BookingFactory()
        event = _event("checkout.session.completed", client_reference_id=booking.id)
        assert process_webhook_event(event) is True
        assert process_webhook_event(event) is False  # same event_id
        assert StripeEvent.objects.filter(event_id="evt_test_1").count() == 1
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_completed_on_confirmed_booking_no_change(self):
        booking = ConfirmedBookingFactory()
        original_pi = booking.stripe_payment_intent_id
        process_webhook_event(
            _event(
                "checkout.session.completed",
                client_reference_id=booking.id,
                payment_intent="pi_other",
                event_id="evt_c1",
            )
        )
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.stripe_payment_intent_id == original_pi  # not overwritten

    def test_completed_on_cancelled_booking_no_change(self):
        booking = CancelledBookingFactory()
        process_webhook_event(
            _event("checkout.session.completed", client_reference_id=booking.id, event_id="evt_x1")
        )
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_unknown_event_type_logged_only(self):
        booking = BookingFactory()
        result = process_webhook_event(
            _event(
                "payment_intent.payment_failed",
                client_reference_id=booking.id,
                event_id="evt_u1",
            )
        )
        assert result is True
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING
        assert StripeEvent.objects.filter(event_id="evt_u1").exists()

    def test_missing_booking_does_not_crash(self):
        result = process_webhook_event(
            _event("checkout.session.completed", client_reference_id=999999, event_id="evt_m1")
        )
        assert result is True
        assert StripeEvent.objects.filter(event_id="evt_m1").exists()

    def test_invalid_client_reference_id_does_not_crash(self):
        result = process_webhook_event(
            _event("checkout.session.completed", client_reference_id="abc", event_id="evt_i1")
        )
        assert result is True

    def test_processed_at_set_on_success(self):
        booking = BookingFactory()
        process_webhook_event(
            _event("checkout.session.completed", client_reference_id=booking.id, event_id="evt_p1")
        )
        assert StripeEvent.objects.get(event_id="evt_p1").processed_at is not None
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/payments/test_webhook_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'process_webhook_event'`.

- [ ] **Step 3: Append to `apps/payments/services.py`** (user pastes)

Add these imports at the top (alongside the existing `import stripe` / `from django.conf import settings` / `from django.urls import reverse` / `from apps.booking.models import Booking`):

```python
from django.db import transaction
from django.utils import timezone

from apps.booking.models import BookingStatus  # add to the existing booking.models import
from apps.payments.models import StripeEvent
```

Append the functions:

```python
def process_webhook_event(event: dict) -> bool:
    """Idempotently process a verified Stripe event. Returns True if newly processed.

    get_or_create + dispatch + processed_at run in one transaction, so a committed
    StripeEvent row means the event was fully processed. Duplicates return False.
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

- [ ] **Step 4: Run → GREEN**

Run: `poetry run pytest tests/payments/test_webhook_service.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/payments/services.py tests/payments/test_webhook_service.py
git commit -m "$(cat <<'EOF'
feat(FR-22): add process_webhook_event dispatch + idempotency

get_or_create + dispatch + processed_at in one atomic, so a committed StripeEvent
row means fully processed (duplicates are no-ops). checkout.session.completed →
PENDING booking CONFIRMED (+ payment_intent); checkout.session.expired → CANCELLED;
other events audit-logged only. Booking locked via select_for_update; only PENDING
transitions (paid-after-cancel left for US-27).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Webhook view + URL

**Files:**
- Test: `tests/payments/test_webhook_view.py` (Create)
- Create: `apps/payments/views.py`, `apps/payments/urls.py`
- Modify: `settings/urls.py`

- [ ] **Step 1: Write the failing tests** (`tests/payments/test_webhook_view.py`)

```python
"""Tests for the stripe_webhook view (US-25 / FR-22)."""

import json

import pytest
import stripe
from django.test import Client
from django.urls import reverse

from apps.booking.models import BookingStatus
from tests.booking.factories import BookingFactory

pytestmark = [pytest.mark.django_db, pytest.mark.stripe]


def _payload(booking_id, event_type="checkout.session.completed", event_id="evt_view_1"):
    return json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "data": {"object": {"client_reference_id": str(booking_id), "payment_intent": "pi_1"}},
        }
    )


def _post(client, payload):
    return client.post(
        reverse("payments:stripe_webhook"),
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=fake",
    )


class TestStripeWebhookView:
    def test_valid_signature_returns_200_and_confirms(self, client, mocker):
        booking = BookingFactory()
        mocker.patch("apps.payments.views.stripe.Webhook.construct_event")
        resp = _post(client, _payload(booking.id))
        assert resp.status_code == 200
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_bad_signature_returns_400(self, client, mocker):
        mocker.patch(
            "apps.payments.views.stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError("bad", "sig"),
        )
        resp = _post(client, _payload(1))
        assert resp.status_code == 400

    def test_malformed_payload_returns_400(self, client, mocker):
        mocker.patch(
            "apps.payments.views.stripe.Webhook.construct_event",
            side_effect=ValueError("bad json"),
        )
        resp = _post(client, "not-json")
        assert resp.status_code == 400

    def test_get_not_allowed(self, client):
        resp = client.get(reverse("payments:stripe_webhook"))
        assert resp.status_code == 405

    def test_csrf_exempt_allows_post_without_token(self, mocker):
        mocker.patch("apps.payments.views.stripe.Webhook.construct_event")
        booking = BookingFactory()
        csrf_client = Client(enforce_csrf_checks=True)
        resp = _post(csrf_client, _payload(booking.id))
        assert resp.status_code != 403
```

- [ ] **Step 2: Run → RED**

Run: `poetry run pytest tests/payments/test_webhook_view.py -v`
Expected: FAIL — `NoReverseMatch` for `payments:stripe_webhook`.

- [ ] **Step 3: Create `apps/payments/views.py`** (user pastes)

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
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")
    process_webhook_event(json.loads(payload))
    return HttpResponse(status=200)
```

> If `stripe.SignatureVerificationError` is not found in the installed version (dev pitfall #13 territory), it's `stripe.error.SignatureVerificationError` — adjust the `except`. Top-level is expected.

- [ ] **Step 4: Create `apps/payments/urls.py`** (user pastes)

```python
from django.urls import path

from apps.payments.views import stripe_webhook

app_name = "payments"

urlpatterns = [
    path("webhooks/stripe/", stripe_webhook, name="stripe_webhook"),
]
```

- [ ] **Step 5: Mount in `settings/urls.py`** (user edits — add after the booking include)

```python
    path("", include("apps.payments.urls", namespace="payments")),
```

- [ ] **Step 6: Run → GREEN**

Run: `poetry run pytest tests/payments/test_webhook_view.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add apps/payments/views.py apps/payments/urls.py settings/urls.py \
        tests/payments/test_webhook_view.py
git commit -m "$(cat <<'EOF'
feat(FR-22): add POST /webhooks/stripe/ endpoint

csrf-exempt, POST-only view that verifies the Stripe signature via
construct_event (400 on bad signature/payload) and delegates the parsed event to
process_webhook_event. Mounted at /webhooks/stripe/ (payments:stripe_webhook).

Closes US-25.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Quality gates

- [ ] **Step 1: Lint + format + types + full suite + coverage**

```bash
poetry run ruff check apps/payments tests/payments
poetry run ruff format --check apps/payments tests/payments
poetry run mypy apps/payments
poetry run python manage.py makemigrations --check --dry-run   # expect: no changes
poetry run pytest --cov
```

Expected: ruff clean; mypy clean; `makemigrations --check` exits 0; full suite green; coverage ≥80%.

> mypy notes: `process_webhook_event(event: dict) -> bool` and `_lock_booking(...) -> Booking | None` are explicit. `json.loads` returns `Any` (fine). If `stripe.SignatureVerificationError` typing complains, it's a runtime class — no annotation needed.

- [ ] **Step 2: Manual smoke (Stripe CLI — optional, needs real keys)**

```bash
# terminal A: stripe listen --forward-to localhost:8000/webhooks/stripe/
#   → copy the printed whsec_... into .env (STRIPE_WEBHOOK_SECRET), restart runserver
# terminal B: poetry run python manage.py runserver
# browser: book → pay with 4242 4242 4242 4242
#   → checkout.session.completed hits the webhook → booking CONFIRMED
#   → /bookings/<id>/ shows "Potwierdzona" + stripe_payment_intent_id set in admin
```

---

## Task 5: Backlog + PR

- [ ] **Step 1: Update `.Claude/backlog.md`**

- `Done` → add US-25; M3 count → 9/11
- `Ready (DoR ✅)` → US-27 (refund on CONFIRMED cancel) — mixed (extends `cancel_booking`)

```bash
git add .Claude/backlog.md
git commit -m "$(cat <<'EOF'
docs(M3): mark US-25 done — Stripe webhook shipped

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/FR-22-stripe-webhook
gh pr create --fill
```

PR body: Summary / Linked (Spec + Plan + Closes US-25) / DoD / Test plan / Out of scope (payment_failed action, paid-after-cancel refund US-27).

---

## Self-Review (wykonane)

**Spec coverage:** §2 view → Task 3. §3 service → Task 2. §4 view detail → Task 3 Step 3. §5 URL/config → Tasks 1 + 3 Steps 4-5. §6 tests → Tasks 2 (9) + 3 (5) = 14. §7 DoD → covered. §8 risk #1 (SignatureVerificationError path) → Task 3 Step 3 note; #3 (raw body) → view uses `request.body`; #6 (CSRF test) → `test_csrf_exempt_allows_post_without_token` uses `Client(enforce_csrf_checks=True)`.

**Placeholder scan:** no TBD/TODO; every step has full code/command.

**Type consistency:** `process_webhook_event(event: dict) -> bool` consistent (service def, view call, tests). `_dispatch`/`_confirm_booking`/`_expire_booking`/`_lock_booking` consistent. URL name `payments:stripe_webhook` consistent (urls, both test files, mount). Event dict shape (`id`/`type`/`data.object.client_reference_id`/`payment_intent`) consistent between service tests, view payload, and `_dispatch`. `mock_checkout_session` not used here (separate from US-24); view tests patch `apps.payments.views.stripe.Webhook.construct_event` directly.
