# US-33 — Checkout endpoint + webhook (API) (design)

**Milestone:** M4 — REST API (`v0.4.0`)
**User story:** US-33 — Checkout endpoint + webhook
**Branch:** `feat/FR-21-checkout-api`
**FR refs:** FR-21 (Stripe Checkout web+API), FR-22 (Stripe webhooks), §4 (endpoint map)
**Date:** 2026-05-25
**Type:** verification + documentation — **no production code change, no migration**.
**Predecessor:** US-24 (Stripe checkout service), US-25 (webhook), US-32 (booking API) ✅ merged.

---

## 1. Goal

Close the FR-21/FR-22 *API* milestone item by confirming the already-shipped pieces work
end-to-end for API-created bookings, and by recording the one deliberate deviation from
FR-22. No new endpoints or handlers.

## 2. Already delivered (no work needed)

| Requirement | Where | Status |
|-------------|-------|--------|
| FR-21 API checkout `POST /api/v1/bookings/<id>/checkout/` → `{checkout_url, session_id}`; PENDING→409 | US-32 `BookingViewSet.checkout` action (over US-24 `create_checkout_session`) | ✅ |
| FR-22 `checkout.session.completed` → CONFIRMED (+ `stripe_payment_intent_id`) | US-25 `process_webhook_event` / `_confirm_booking` | ✅ |
| FR-22 `checkout.session.expired` → CANCELLED | US-25 `_expire_booking` | ✅ |
| FR-22 signature verify (400) + idempotency (`StripeEvent`, dup→200) | US-25 `stripe_webhook` view + service | ✅ |
| Single webhook serves web **and** API bookings | `process_webhook_event` is generic on `client_reference_id` (the API create sets it via `create_checkout_session`) | ✅ |

## 3. Deliverables (this US)

1. **Integration test** — prove an **API-created** booking is confirmed by the webhook
   (the existing US-25 tests use `BookingFactory`, not the API create path).
2. **Schema check** — assert the checkout action is present in the OpenAPI schema
   (confirms US-32's `@extend_schema`; the strict-mode gate stays US-35).
3. **Documented deviation** (this spec) — FR-22 §552 `payment_intent.payment_failed` →
   CANCELLED is **intentionally not implemented** (§5).

## 4. Decision: webhook stays single (not duplicated under /api/)

Confirmation flows through the existing web `POST /webhooks/stripe/` (US-25) for both web
and API bookings. We do **not** add an `/api/v1/.../webhook/` endpoint — one idempotent
handler, one `StripeEvent` log. (Settled at M4 kickoff; restated here.)

## 5. Deliberate deviation from FR-22 §552 — `payment_intent.payment_failed`

FR-22 §552 lists `payment_intent.payment_failed` → CANCELLED (keyed via
`payment_intent.metadata`). We **intentionally do not implement it**:

- **Hosted Checkout retries.** A mid-session card decline fires
  `payment_intent.payment_failed`, but the customer can immediately retry on Stripe's
  hosted page. Cancelling the booking on that event would be **premature** — they may still
  pay successfully.
- **Authoritative non-payment paths already exist.** `checkout.session.expired` (Stripe's
  own session timeout) and the `expire_pending_bookings` management command (US-26, the
  15-minute hold) are the correct, non-premature ways a PENDING booking becomes CANCELLED.
- **No metadata plumbing.** `create_checkout_session` sets `client_reference_id` on the
  *session*, not on the payment intent; wiring this event would require
  `payment_intent_data.metadata`, added solely to support a handler we don't want.

The current `_dispatch` already treats `payment_intent.payment_failed` as audit-log-only,
and `tests/payments/test_webhook_service.py::test_unknown_event_type_logged_only` pins that
behaviour (booking stays PENDING). This US documents the rationale; no code changes.

The FR-22 line predates the hosted-Checkout decisions made in US-24/25; this deviation
should be reflected in the FR doc during the M4 close / M5 review (out of scope here).

## 6. Tests (Claude writes — `tests/booking/test_api.py`)

New class `TestApiBookingWebhookConfirm`:
- `@pytest.mark.stripe` — create a booking via `POST /api/v1/bookings/` (with
  `mock_checkout_session`), grab `booking.id` from the response, then call
  `process_webhook_event({...checkout.session.completed..., client_reference_id: id,
  payment_intent: "pi_api_1"})` → assert the booking is `CONFIRMED` and
  `stripe_payment_intent_id == "pi_api_1"`.

New schema test (`tests/booking/test_api.py`):
- `test_checkout_endpoint_in_schema(api_client)` — `GET /api/v1/schema/?format=json` →
  some path key contains `"checkout"` (the action is documented).

## 7. Coverage / migration

Test-only additions → coverage threshold unaffected (slightly exercises existing code).
**No migration. No production code change.**

## 8. Risks

1. **"Empty US" temptation** — the value is the documented decision + the API-path
   integration proof; resist adding the `payment_intent.payment_failed` handler (§5).
2. **Schema path-key brittleness** — assert by substring (`"checkout" in path`), not an
   exact `/api/v1/bookings/{id}/checkout/` string (drf-spectacular's lookup-param naming).

## 9. Build order (for the plan)

1. Integration test + schema test (one task).
2. Quality gate (pytest, ruff, mypy).

First branch commit folds in the `backlog.md` board update (US-32 → Done, US-33 → In
Progress) made at US-33 start.
