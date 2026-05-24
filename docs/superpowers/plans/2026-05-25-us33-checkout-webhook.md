# US-33 — Checkout endpoint + webhook (API) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the already-shipped FR-21/FR-22 API path end-to-end (API-created booking → webhook confirm) and confirm the checkout action is in the schema — no production code change.

**Architecture:** Test-only. An integration test creates a booking through `POST /api/v1/bookings/` and feeds the result id to `process_webhook_event` (the single web webhook handler), asserting PENDING→CONFIRMED. A schema test confirms the checkout action is documented. The deliberate FR-22 §552 deviation lives in the spec.

**Tech Stack:** pytest / pytest-django; DRF test client; Stripe mocked via the existing `mock_checkout_session` fixture.

---

## Role division

- **Claude** writes all test code (`tests/**`).
- **User** runs all `git`/`pytest` commands.

## Spec

`docs/superpowers/specs/2026-05-25-us33-checkout-webhook-design.md`

## File structure

| File | Action | Responsibility | Author |
|------|--------|----------------|--------|
| `tests/booking/test_api.py` | modify | add `TestApiBookingWebhookConfirm` + checkout-schema test | Claude |

No production files change. No migration.

---

### Task 1: Integration + schema tests

**Files:**
- Modify: `tests/booking/test_api.py`

- [ ] **Step 1 [Claude]: Add the integration + schema tests**

Extend the imports at the top of `tests/booking/test_api.py` — the file currently imports
`from apps.booking.models import BookingStatus`; change it to also import `Booking`, and add
the service import:
```python
from apps.booking.models import Booking, BookingStatus
from apps.payments.services import process_webhook_event
```

Append at the end of the file:
```python
class TestApiBookingWebhookConfirm:
    @pytest.mark.stripe
    def test_api_created_booking_confirmed_via_webhook(self, auth_client, mock_checkout_session):
        # Create through the API (not BookingFactory) so we exercise the real
        # client_reference_id wiring, then confirm via the single web webhook handler.
        screening = ScreeningFactory()
        create_resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 2}, format="json"
        )
        assert create_resp.status_code == 201
        booking_id = create_resp.data["booking"]["id"]

        event = {
            "id": "evt_api_confirm_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": str(booking_id),
                    "payment_intent": "pi_api_1",
                }
            },
        }
        assert process_webhook_event(event) is True

        booking = Booking.objects.get(pk=booking_id)
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.stripe_payment_intent_id == "pi_api_1"
        assert booking.expires_at is None


def test_checkout_endpoint_in_schema(api_client):
    paths = api_client.get("/api/v1/schema/?format=json").json()["paths"]
    assert any("checkout" in path for path in paths)
```

- [ ] **Step 2 [User]: Run the new tests**

Run: `poetry run pytest tests/booking/test_api.py::TestApiBookingWebhookConfirm tests/booking/test_api.py::test_checkout_endpoint_in_schema -q --no-cov`
Expected: PASS (2 passed). These assert already-working behaviour — they should pass
immediately (this US is verification, not red→green feature work).

- [ ] **Step 3 [User]: Commit (folds in the backlog board update)**

```bash
git add tests/booking/test_api.py .Claude/backlog.md
git commit -m "test(FR-21): verify API booking confirmed via webhook + checkout in schema (US-33)"
```

---

### Task 2: Quality gate

- [ ] **Step 1 [User]: Full suite with coverage**

Run: `poetry run pytest`
Expected: PASS, coverage ≥ 80%.

- [ ] **Step 2 [User]: Lint + format + type-check**

Run: `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .`
Expected: clean (test-only change; `tests.*` is excluded from mypy).

---

## Out of scope

`payment_intent.payment_failed` handling (deliberately not implemented — spec §5) · strict CI schema gate (US-35) · admin write API (US-34) · throttle 429 tests (US-36).

## Note on TDD

Unlike the other M4 stories, US-33 adds **no production code** — the behaviour already
exists (US-24/25/32). The tests are characterization/integration proofs, so they pass on
first run rather than going red→green. The real deliverable is the documented FR-22 §552
deviation (spec §5).

## Test plan summary

- `tests/booking/test_api.py`: API-created booking → `checkout.session.completed` webhook →
  CONFIRMED (+ payment_intent + cleared expiry); checkout action present in the OpenAPI schema.
- No migration; coverage ≥ 80% maintained.
