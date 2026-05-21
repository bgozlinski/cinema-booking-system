# M3 — Booking web + Stripe planning kickoff

**Milestone:** M3 — Booking web + Stripe (`v0.3.0`)
**US:** US-18..US-28 (11 user stories)
**Status:** Planning kickoff (drafted 2026-05-22 at M2 close)
**Predecessor:** M2 — Catalog web (`v0.2.0`) ✅ complete

This document is a session-start brief for M3. Read it before opening M3 brainstorming/planning sessions to avoid re-deriving context.

---

## Goal

Ship `v0.3.0` — KinoMania ma działający flow rezerwacji z prawdziwymi płatnościami w Stripe sandbox. Zalogowany user może:

- Zarezerwować bilety na seans (`/screenings/<id>/book/`)
- Zapłacić kartą test Stripe (`4242 4242 4242 4242`) przez Stripe Checkout hosted page
- Odebrać CONFIRMED booking po pomyślnej płatności (webhook)
- Zobaczyć swoje bookingi w `/my-bookings/` (taby Nadchodzące / Historia)
- Anulować booking (PENDING bez Stripe, CONFIRMED z refundem w Stripe)

Admin: pełen lifecycle booking w `BookingAdmin` + kolorowe badge dostępności w `ScreeningAdmin`.

**End-to-end smoke goal:**
1. User loguje się → `/screenings/<id>/book/` → submit form (1-10 seats)
2. Backend: PENDING booking + `select_for_update` lock + Stripe Checkout session → redirect na Stripe-hosted page
3. User płaci test card → Stripe webhook → CONFIRMED + `stripe_payment_intent_id`
4. `/my-bookings/` shows booking pod "Nadchodzące" → cancel (jeśli > 1h przed seansem) → Stripe refund → CANCELLED
5. `expire_pending_bookings` cron-able command cancels stale PENDING (15-min lock window)

**Out of M3 scope:**
- REST API endpoints dla bookings (US-32, M4)
- Email confirmation messages (lekka funkcja — może bundle do US-28 lub follow-up)
- Rate limiting na booking creation (M5 security)
- Responsive seat-picker UI (out of project — `seats_count` integer only)
- Admin UX polish / kolorowe badge tuning (M5)
- `expire_pending_bookings` na cron systemowym / Celery beat (out of MVP per FR-23)

---

## Recommended ordering (with dependency rationale)

**Strategy: Mixed.** Web booking layer stable first (US-18..23, 26), potem Stripe integration (US-24, 25, 27), potem admin (US-28). Stripe risk późno, ale web UX jest fully testable standalone — PENDING/CONFIRMED można setować w testach manualnie bez Stripe.

| # | US | Estym | Why this position |
|---|---|---|---|
| 1 | **US-18** — Booking + StripeEvent models + migracje + real `booked_seats_count` | M | Hard blocker — wszystko zależy od modeli. Plus podmiana stub `Screening.booked_seats_count()` (z US-10, returns 0) na real aggregation z CONFIRMED + active-PENDING bookings. Biggest design decision M3 (app layout). |
| 2 | **US-19** — `BookingForm` + validation logic | M | Form-only US — `seats_count` ∈ [1, min(10, available)], `screening.start_time > now()`. No view yet. Pure-Django, mechaniczne. |
| 3 | **US-20** — Booking create view (`POST /screenings/<id>/book/`) z `select_for_update` + atomic | L | Heart of booking flow — race condition handling. Stripe redirect jako **stub** (placeholder URL — replace w US-24). Wciąż testowalne unit-style. |
| 4 | **US-21** — Booking detail view (`/bookings/<int:pk>/`) z 403 dla obcych | S | Standalone post-create — booking status, total_price, screening info. Mały task. |
| 5 | **US-22** — My bookings panel (`/my-bookings/`) z tabami Nadchodzące/Historia | M | Web UX flow complete z perspektywy usera. Bez Stripe — CONFIRMED można setować w testach. |
| 6 | **US-23** — Cancel booking (PENDING-only initially) | M | Cancel PENDING bez Stripe (just status update). Refund dla CONFIRMED odłożony do US-27. |
| 7 | **US-26** — `expire_pending_bookings` command | S | Działa na real PENDING data z US-20. Cron-able. Bez Stripe — pure DB operation. |
| 8 | **US-24** — Stripe Checkout integration | L | **Replace stub z US-20.** Real `stripe.checkout.Session.create()` + idempotency key + `success_url`/`cancel_url`. Plus `.env.example` Stripe keys + `poetry add stripe`. |
| 9 | **US-25** — Stripe webhook handler + `StripeEvent` idempotency | L | Po US-24 mamy real Stripe events. Webhook verification z `construct_event` + `StripeEvent.get_or_create` idempotency. PENDING→CONFIRMED transitions. |
| 10 | **US-27** — Refund flow przy cancel CONFIRMED | M | Extends US-23 — gdy CONFIRMED i `stripe_payment_intent_id` istnieje, `stripe.Refund.create()` przed status change. Wymaga US-25. |
| 11 | **US-28** — Admin: BookingAdmin + ScreeningAdmin (z badge dostępności) | M | Last — wszystkie modele complete. ScreeningAdmin z kolorowymi badge dla `available_seats_count` (green/yellow/red threshold). |

WIP=1 stays — jeden US in progress na raz.

**Alternative considered (rejected for default):** Stripe-early ordering (US-24/25 right after US-20, przed US-21..23). Plus: e2e smoke fast. Minus: web layer rebuild risk przy późniejszych adjustments na status transitions. User może override przy starcie M3 jeśli preferuje.

---

## What needs brainstorming vs. what goes straight to plan

### Brainstorm first (separate sessions, 15-30 min każda)

- **US-18** — Booking + StripeEvent models. Decyzje:
  - **App layout:** nowa `apps/booking/` (Booking + StripeEvent razem) vs `apps/cinema/` (Booking) + `apps/payments/` (StripeEvent + Stripe services, per FR §3.9 spec) vs all-in-cinema. Fundamental — wpływa na imports w 11 US.
  - StripeEvent `payload` field: `JSONField` (Postgres-native) vs `TextField` (portability)
  - `Booking.expires_at` jako field z computed default vs callable property (15-min lock w model layer vs view layer)
  - Real `booked_seats_count` aggregation: PENDING-not-expired liczone jako reserved? (FR-3.7 mówi tak — confirm)
  - Refund: separate fields (`refund_id`, `refunded_at`) vs nested Refund model (FK)
  - `Booking.total_price` jako computed property vs persisted field

- **US-20** — Booking create view (concurrency + Stripe stub). Decyzje:
  - `select_for_update` granularity (full Screening row vs subset?)
  - Stripe stub UX (placeholder URL? bypass mode? mock service injected?)
  - Race condition test design — `threading.Thread` w pytest? `pytest-django` race fixtures?
  - Error UX dla sold-out (form-level error? flash + redirect? 409 page?)
  - Atomic boundary — co dokładnie w `transaction.atomic()` (Booking create + Stripe session create razem czy tylko Booking)

- **US-24** — Stripe Checkout integration. Decyzje:
  - Service module layout (`<payments-app>/services/stripe.py` vs inline w view)
  - Test strategy — mock SDK per test (`pytest-mock` + `monkeypatch`) vs central conftest fixtures
  - Stripe SDK error handling (network error? rate limit? card declined?)
  - Idempotency key naming convention (`booking-{id}-checkout` — confirm na Stripe docs)
  - `STRIPE_API_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PUBLISHABLE_KEY` w `.env.example` + Stripe CLI setup docs (onboarding)

- **US-25** — Webhook handler + idempotency. Decyzje:
  - `StripeEvent.get_or_create(event_id=...)` race condition (concurrent identical events)
  - Event coverage: `checkout.session.completed` + `expired` + `payment_intent.payment_failed` — czy więcej?
  - `payment_intent.payment_failed` → `client_reference_id` z `payment_intent.metadata` (Stripe wymaga manual passdown podczas Checkout Session create)
  - Signature verification + replay attack tests

### Plan directly (no brainstorming needed)

- **US-19** — BookingForm: pure-Django `Form` z 1 polem (`seats_count` ∈ [1, 10]) + 2 `clean_*` validations (FR-07). Mechanical.
- **US-21** — Booking detail view: standard `DetailView` + permission check (`booking.user == request.user OR is_staff`). 30 min implementation.
- **US-22** — My bookings panel: 2-tab layout (Nadchodzące / Historia) z server-rendered switch via `?tab=upcoming|history`. Standard `ListView` z filter.
- **US-23** — Cancel (PENDING-only): POST endpoint, status update, flash + redirect. Mechanical. Refund extension w US-27.
- **US-26** — `expire_pending_bookings`: command pattern z `seed_db.py`. Pure ORM query + status update + `--dry-run` flag.
- **US-28** — Admin: BookingAdmin + ScreeningAdmin. Pattern z US-15 + US-17 (5 ModelAdminów z `get_queryset` annotate). Mała decyzja: kolorowe badge thresholdy dla `available_seats_display` (np. <20% = red, 20-50% = yellow, >50% = green). Bundle do plan.

### Mixed (mostly mechanical + small design points)

- **US-27** — Refund flow. Plan extends US-23 cancel; 2 design points wymagają brainstormingu inline (nie osobnej sesji):
  - Stripe `Refund.create` error handling (already refunded? card revoked?)
  - Atomicity — `transaction.atomic()` boundary (Booking status change + Stripe API call — co jeśli Stripe success ale DB save fail?)

### Cross-cutting (decyzje przy starcie M3)

- **`seed_db` extension dla bookings** (FR-13: 85% CONFIRMED / 5% PENDING / 10% CANCELLED + StripeEvent entries dla CONFIRMED). Options:
  - A) Bundle do US-18 PR (model + seed razem — najnaturalniej, mirror US-10/US-16 patternu)
  - B) Micro-task między US-18 i US-19 (osobny `feat(FR-13): seed_db bookings extension` PR)
  - C) Defer do końca M3 (final polish task)
  - **Recommendation: A** — modele + ich seed idą razem.

---

## Risk areas (worth flagging now)

1. **Race conditions na booking create.** Fundament M3. Bez właściwego `select_for_update` + `transaction.atomic()` przy concurrent requests dostaje się overbooking. Plus `Screening.booked_seats_count` musi liczyć PENDING-not-expired jako "soft reserved" — inaczej 2 użytkowników w tym samym 15-min window mogą wykupić ten sam seat. **Action:** test design z `threading` lub `pytest-django`'s race fixtures w US-20 spec.

2. **Stripe sandbox onboarding cost.** Nowy dev (lub przyszły Claude w nowej sesji) potrzebuje: Stripe account (free test mode), `stripe` CLI binary install, `STRIPE_API_KEY` + `STRIPE_WEBHOOK_SECRET` w `.env`, `stripe listen --forward-to localhost:8000/webhooks/stripe/` running w terminalu. **Action:** rozszerzenie `.env.example` w US-24 + dodatek "Stripe local setup" sekcja do README (lub osobny `docs/stripe-setup.md`).

3. **Webhook idempotency + retry behavior.** Stripe retry'uje webhook przy 5xx response. Concurrent identical events (replays + retries) mogą prowadzić do race na `StripeEvent.get_or_create`. **Action:** test "same event_id 2× → 1 state change" w US-25. Plus `StripeEvent.event_id` z `unique=True` constraint jako DB-level safety net.

4. **Real `booked_seats_count` regression risk.** Stub w `Screening.booked_seats_count()` (returns 0) z US-10 zmienia się na real aggregation w US-18. Każdy istniejący test który polega na "no bookings = full capacity available" wciąż przejdzie (bo brak bookings = aggregation returns 0). ALE: w US-22+ testy które tworzą Booking będą zmieniać `available_seats_count`. **Action:** US-18 spec musi explicit zaadresować — które testy w `tests/cinema/test_models.py` wymagają update.

5. **`expires_at` enforcement zależy od cron.** 15-min PENDING window jest enforce'd PRZEZ `expire_pending_bookings` (US-26). Jeśli command nie odpala się — stale PENDING blokują seats. **W dev:** manualne `python manage.py expire_pending_bookings`. **W prod:** out-of-scope MVP per FR-23 (decyzja cron systemowy / Celery beat odłożona poza M3). **Action:** README sekcja "Local dev — czyszczenie stale PENDINGów".

6. **Stripe event coverage edge cases.** FR-22 wymienia 3 event types (`checkout.session.completed`, `checkout.session.expired`, `payment_intent.payment_failed`). Pomija: `payment_intent.canceled` (user closes Checkout), `charge.refunded` (admin manualny refund w Stripe dashboard), `payment_intent.requires_action` (3DS challenges). **Decyzja:** US-25 handles 3 z FR + reszta jako "log + skip" (StripeEvent persist ale brak state change). Edge cases jako follow-up (US-25b albo M4).

7. **Refund failure handling.** `stripe.Refund.create()` może fail: already refunded, card revoked, network error. Nie można rollback Stripe call po fakcie. **Decyzja:** atomic boundary = `transaction.atomic` z Stripe call WEWNĄTRZ ale w try/except — przy Stripe error: rollback DB, raise user-facing error, NIE zmieniać Booking.status na CANCELLED. UX: flash "Anulowanie nieudane — skontaktuj się z supportem".

8. **`Screening.booked_seats_count` perf w admin.** US-28 `ScreeningAdmin.list_display` ma `available_seats_display` z kolorowym badge. Per US-15 + US-17 patternie — annotate w `get_queryset` (avoid N+1). **Action:** plan US-28 musi explicit zaadresować — `Count("bookings", filter=Q(status="CONFIRMED")|Q(status="PENDING", expires_at__gt=now))` + budget cap test w `tests/cinema/test_admin_query_budgets.py`.

9. **Webhook view CSRF + URL routing.** `POST /webhooks/stripe/` MUSI być `csrf_exempt` (webhook nie ma CSRF token). URL nie może być w `cinema/urls.py` (nie cinema concern) — idzie do `<payments-app>/urls.py` (decyzja US-18). Plus middleware ordering — `MessagesMiddleware` itp. nie powinny być na webhook path.

10. **`BASE_URL` env var dla Stripe `success_url` / `cancel_url`.** Stripe wymaga absolutnych URLi. W dev `http://localhost:8000`, w prod `https://kinomania.example.com`. **Action:** dodać `BASE_URL` do `settings/base.py` + `.env.example` w US-24.

---

## Pre-flight checklist (read these before M3 brainstorming)

### FR doc — primary reference

- `.Claude/KinoMania_wymagania_funkcjonalne.md`:
  - **§3.7** (Screening — `booked_seats_count`/`available_seats_count` real impl)
  - **§3.8** (Booking model — fields, statuses, lifecycle)
  - **§3.9** (StripeEvent — idempotency log)
  - **§FR-07** (booking create — `select_for_update` + atomic + Stripe redirect)
  - **§FR-08..10** (detail / my-bookings / cancel)
  - **§FR-11** (BookingAdmin + ScreeningAdmin scope)
  - **§FR-21..24** (Stripe Checkout / webhook / expire / refund)
  - **§7.4** (`payments/tests/` — test patterns dla webhook/refund/expire)

### Backlog + planning

- `.Claude/backlog.md` §3 (M3 table z 11 US — short titles; flesh out per spec)
- `.Claude/m2_planning.md` (template — strukturę kopiuj dla per-US specs)
- `.Claude/m3_planning.md` (TEN dokument)

### Memory references

- `project_kinomania_bootstrap.md` — pełen stan repo (post-M2)
- `feedback_role_division.md` — Claude pisze testy + skeleton; user pisze app code; user runs git/pytest
- `feedback_workflow.md` — SCRUM/AGILE + TDD + Conventional Commits
- `feedback_shell_environment.md` — Git Bash heredoci

### Code patterns z M1/M2 do mirror

- `apps/cinema/models.py` — model + factories pattern (zwłaszcza `Screening` stub methods które US-18 podmienia)
- `apps/cinema/admin.py` — ModelAdmin z `get_queryset` annotate (US-15 + US-17 pattern dla BookingAdmin/ScreeningAdmin)
- `apps/cinema/management/commands/seed_db.py` — extension pattern dla seed bookings (per-entity helpers jako Command method sibling)
- `apps/cinema/views.py` — view + queryset patterns (MovieListView z `prefetch_related`)
- `tests/cinema/test_admin_query_budgets.py` — admin perf test pattern (kopiowane dla BookingAdmin/ScreeningAdmin w US-28)
- `tests/cinema/factories.py` — factory_boy z lazy string references (`model = "booking.Booking"` jeśli new app)

### Stripe docs (external)

- Stripe Checkout Session API: https://stripe.com/docs/api/checkout/sessions/create
- Stripe Webhooks: https://stripe.com/docs/webhooks
- Stripe CLI for local dev: https://stripe.com/docs/stripe-cli
- Stripe Refunds: https://stripe.com/docs/api/refunds/create
- Test card numbers: https://stripe.com/docs/testing#cards (4242 4242 4242 4242 = success)

### Spec/plan templates

- Spec format: `docs/superpowers/specs/2026-05-21-us17-performance-pass.md` (najnowszy)
- Plan format: `docs/superpowers/plans/2026-05-21-us17-performance-pass.md`

---

## M3 completion criteria

- ✅ All 11 US (US-18..US-28) merged do `main`
- ✅ Coverage stays ≥80% globally
- ✅ **Manual smoke (end-to-end):**
  - Anon → register/activate → login
  - Login → `/movies/<id>/` → click "Zarezerwuj" → `/screenings/<id>/book/`
  - Submit form (3 seats) → redirect na Stripe Checkout
  - Pay with `4242 4242 4242 4242` (Stripe test card) → redirect back na `/bookings/<id>/?stripe=success`
  - Verify CONFIRMED status
  - `/my-bookings/` shows booking pod "Nadchodzące" tab
  - Click "Anuluj" → CANCELLED + Stripe refund triggered (sprawdź w Stripe dashboard)
  - `python manage.py expire_pending_bookings` cancels stale PENDING
- ✅ Admin smoke:
  - `/admin/cinema/screening/` shows kolorowe badge dla available_seats (green/yellow/red threshold)
  - `/admin/<booking-app>/booking/` shows full lifecycle (status filter + search po user email)
- ✅ `v0.3.0` tag + GitHub release cut
- ✅ Memory update: `project_kinomania_bootstrap.md` reflect M3 close + M4 transition

---

## Branch + commit convention reminder

- **Branch naming:**
  - `feat/FR-XX-<slug>` (US-18..28)
  - `chore/M3-<slug>` dla milestone-scoped baseline (np. Stripe SDK install)
  - `perf/FR-XX-<slug>` dla optymalizacji (rzadko w M3)
- **Commit scope:** `feat(FR-XX): ...`, `test(FR-XX): ...`, `refactor(FR-XX): ...`, `docs(FR-XX): ...`, `feat(M3): ...` dla milestone-wide changes
- **Branch protection on `main`** — każdy US dostaje PR z strukturą:
  - Summary
  - Linked (Spec + Plan + Closes US-XX)
  - Definition of Done checklist
  - Test plan checkboxes
  - Out of scope (follow-up)

---

## Recommended next session kickoff prompt

> Start M3 — brainstorm US-18 (Booking + StripeEvent models). Read `.Claude/m3_planning.md` first, then `.Claude/KinoMania_wymagania_funkcjonalne.md` §3.7-3.9. Walk me through model decisions one at a time (app layout, payload field type, expires_at strategy, refund storage, real booked_seats_count aggregation).

To daje następnej sesji focused entry point. Po US-18 spec/plan/merge, pattern repeats: brainstorm → spec → plan → TDD execution → PR per US.

---

After M3 → **M4 — REST API (`v0.4.0`)**, 8 US (US-29..US-36). DRF setup + JWT + public read API + booking write API + OpenAPI schema + throttling.
