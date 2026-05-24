# M4 — REST API planning kickoff

**Milestone:** M4 — REST API (`v0.4.0`)
**US:** US-29..US-36 (8 user stories)
**Status:** Planning kickoff (drafted 2026-05-24 at M3 close)
**Predecessor:** M3 — Booking web + Stripe (`v0.3.0`) ✅ complete (US-01..US-28)

Session-start brief for M4. Read before opening M4 brainstorming/planning sessions to avoid re-deriving context. Mirrors `m3_planning.md`.

---

## Goal

Ship `v0.4.0` — a JWT-authed, OpenAPI-documented REST API (`/api/v1/`) over the existing domain: public catalog reads, owner-scoped booking writes, staff CRUD, all throttled.

**The big enabler:** M3's service layer is HTTP-agnostic, so the API is mostly a thin serializer + permission layer over existing logic — **no business-logic duplication**:
- `apps/booking/services.py`: `create_booking(*, user, screening, seats_count) -> Booking`, `cancel_booking(*, booking)`, `start_checkout(*, booking) -> str`
- `apps/payments/services.py`: `create_checkout_session(booking) -> (url, id)`, `create_refund(booking) -> str`, `process_webhook_event(event: dict) -> bool`

This is *why* US-32/33/34 are mostly plan-directly: the logic exists; the API is serializers + permissions + viewsets calling the same services the web views call.

**End-to-end smoke goal:**
1. `POST /api/v1/auth/token/` (email+password) → `{access, refresh}`
2. `GET /api/v1/movies/` (anon OK) → paginated catalog
3. `POST /api/v1/bookings/` (Bearer access) `{screening_id, seats_count}` → PENDING booking + `checkout_url`
4. `POST /api/v1/bookings/<id>/cancel/` → CANCELLED (+ refund if CONFIRMED)
5. `GET /api/v1/docs/` → Swagger UI with working "Authorize" (bearer)

**Out of M4 scope:**
- M5 security hardening (rate-limit tuning beyond scopes, audit) — M5.
- API email-activation re-implementation — reuse M1 web activation; API register sends the email, returns no JWT (FR-16).
- GraphQL / websockets / API client SDKs — out of project.

---

## Cross-cutting decisions (settled at kickoff)

| Decyzja | Wybór |
|---------|-------|
| **API layout** | **Per-app `api/` submodules** — `apps/cinema/api/{serializers,views,filters,urls}.py`, `apps/booking/api/...`, `apps/accounts/api/...`, `apps/payments/api/...`; aggregated by a thin top-level router (`settings/api_urls.py` or `apps/api/urls.py`) mounted at `/api/v1/`. Serializers/viewsets sit next to their models + the M3 services. Matches FR §8. |
| **Stack (US-29)** | `djangorestframework`, `djangorestframework-simplejwt`, `django-filter`, `drf-spectacular` (+ `djangorestframework-stubs` for mypy). None installed yet. |
| **JWT** | simplejwt; `access = 15 min`, `refresh = 7 dni` (env-tunable per FR-16). `JWTAuthentication` default + `SessionAuthentication` (DEBUG browsable API). |
| **Versioning** | `/api/v1/` URL prefix. |
| **Pagination/filter** | `PageNumberPagination` page_size=12; `django-filter` FilterSets + `SearchFilter` + `OrderingFilter`. |
| **Throttling** | `anon 100/h`, `user 1000/h`, `auth 20/h` (FR-16/17). Scopes defined in US-29; tested in US-36. |
| **OpenAPI** | `drf-spectacular`; `@extend_schema` added **incrementally per viewset** as built; US-35 = strict-mode CI gate + Swagger/ReDoc + examples. |

---

## Recommended ordering (with rationale)

| # | US | Estym | Type | Why this position |
|---|----|-------|------|-------------------|
| 1 | **US-29** — DRF + JWT + spectacular setup | M | **brainstorm** | Hard blocker. Decisions: settings (`REST_FRAMEWORK`/`SIMPLE_JWT`/`SPECTACULAR_SETTINGS`), router aggregation, base API test patterns (auth client fixture). App layout decided (per-app `api/`). |
| 2 | **US-30** — Auth API (register/token/refresh/me) | M | **mixed** | simplejwt token/refresh views = mechanical. `register` reuses M1 `accounts` activation/emails (no JWT on register, `is_active=False`, sends email — FR-16). `me` = simple. Auth throttle scope. |
| 3 | **US-31** — Public read API | L | **plan-directly** | `ReadOnlyModelViewSet` + serializers + FilterSets for movies/screenings/genres/halls/actors/directors. One design point: nested movie-detail serializer (genres/actors/directors/screenings). `IsAuthenticatedOrReadOnly`. |
| 4 | **US-32** — Booking API (list/create/retrieve/cancel) | L | **plan-directly** | Reuses `create_booking`/`cancel_booking`/`start_checkout`. `IsBookingOwnerOrStaff` custom permission. Create serializer returns `{booking, checkout_url}`. owner-scoped queryset. |
| 5 | **US-33** — Checkout endpoint + webhook | M | **mixed** | Reuses `start_checkout`/`process_webhook_event`. **Decision:** keep single web webhook `/webhooks/stripe/` (US-25) vs expose/duplicate under `/api/` — lean toward NOT duplicating (one idempotent handler). API `POST /bookings/<id>/checkout/` returns `{checkout_url, session_id}`. |
| 6 | **US-34** — Admin/staff write API | M | **plan-directly** | `ModelViewSet` CRUD `IsAdminUser` for cinema resources + bookings; `MultiPartParser` image uploads (5MB, JPG/PNG/WebP); manual-refund action reuses `create_refund`. |
| 7 | **US-35** — OpenAPI docs + strict CI | S | **plan-directly** | `@extend_schema` examples, Swagger (`/api/v1/docs/`) + ReDoc, `bearerAuth` security scheme; CI fails on schema warnings (strict). |
| 8 | **US-36** — Throttling per scope + tests | S | **plan-directly** | Scopes configured in US-29; this US adds throttle tests (cache-backed) + tuning. |

WIP=1. Per-US: brainstorm (if flagged) → spec → plan → TDD → PR.

---

## What needs brainstorming vs plan-directly

- **US-29** (brainstorm): settings dicts, router aggregation strategy, API test client/auth fixture pattern, where the top-level router lives.
- **US-33** (mixed, inline decision): webhook unification — keep `/webhooks/stripe/` single (recommended) or expose under `/api/`. Plus checkout-endpoint shape.
- **US-30..32, 34..36** (plan-directly): standard DRF patterns; the M3 services + M2 querysets are the hard parts and already exist.

---

## Risks

1. **simplejwt + custom User (email USERNAME_FIELD).** Token obtain serializer must auth by email. simplejwt uses `USERNAME_FIELD` → should work; verify in US-30 (login by email).
2. **drf-spectacular strict mode.** Every viewset/serializer needs clean schema or CI warnings fail (FR-20). **Mitigation:** add `@extend_schema` as each viewset lands (US-31+), don't defer all to US-35. US-35 = final gate.
3. **Webhook duplication (US-33).** Don't create a second idempotency path. Keep one `/webhooks/stripe/` (US-25). Decide explicitly in US-33.
4. **API register vs activation (US-30).** Reuse `apps/accounts` `emails.py` + token; `is_active=False`, no JWT returned (FR-16). Don't re-implement activation.
5. **Throttle tests need a cache.** DRF throttling stores counters in the cache backend. Verify `CACHES` configured (LocMemCache default works per-process; tests may need cache clear between tests). US-36.
6. **Coverage ≥80% as API grows.** Lots of new code (serializers/viewsets/permissions). Tests must keep pace per US (CI `--cov-fail-under=80`).
7. **mypy + DRF.** `djangorestframework-stubs` required; serializer/viewset generics typing. Add stubs in US-29.
8. **Owner-scoping (US-32/34).** `IsBookingOwnerOrStaff` + owner-filtered querysets (mirror web 404/403 split). Same `request.user` django-stubs cast caveat (dev pitfall #12).

---

## Pre-flight checklist (read before M4 brainstorming)

- **FR doc:** `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-16 (auth), §FR-17 (public read), §FR-18 (bookings), §FR-19 (admin write), §FR-20 (OpenAPI), §FR-21/22 (Stripe API/webhook), §4 (endpoint map), §8 (struktura — per-app `api/`).
- **Backlog:** `.Claude/backlog.md` §4 (M4 table US-29..36).
- **Template:** `m3_planning.md` (this doc mirrors it); spec/plan format `docs/superpowers/specs|plans/2026-05-24-us*`.
- **Tooling:** `.Claude/tooling_stack.md` (DRF/ruff/mypy/pytest config — check for DRF canonical config to copy in US-29).
- **Memory:** `project_kinomania_bootstrap.md` (repo state post-M3), `feedback_role_division`, `feedback_us_branch_timing` (branch-first!), `feedback_shell_environment`.
- **Reuse targets:** `apps/booking/services.py`, `apps/payments/services.py` (the services the API calls); `apps/cinema/views.py` (queryset patterns: `_annotate_booked_count`, MovieList/ScreeningList filters); `apps/cinema/admin.py` (resource shapes).

---

## M4 completion criteria

- ✅ All 8 US (US-29..US-36) merged to `main`
- ✅ Coverage ≥80%; `mypy`/`ruff` clean
- ✅ `drf-spectacular` schema generates with **no warnings** (strict, enforced in CI)
- ✅ Swagger UI `/api/v1/docs/` "Authorize" (bearer JWT) works end-to-end
- ✅ Smoke: token → list movies (anon) → create booking (bearer) + checkout_url → cancel/refund
- ✅ `v0.4.0` tag + GitHub release
- ✅ Memory update: `project_kinomania_bootstrap.md` reflects M4 close + M5 transition

---

## Branch + commit conventions (reminder)

- Branch: `chore/M4-drf-setup` (US-29), `feat/FR-16-auth-api`, `feat/FR-17-public-api`, `feat/FR-18-booking-api`, `feat/FR-21-checkout-api`, `feat/FR-19-admin-api`, `feat/FR-20-openapi-docs`, `feat/FR-16-api-throttling` (per backlog M4 table).
- Commit: Conventional Commits with FR scope (`feat(FR-17): …`).
- **Branch-first discipline** (per `feedback_us_branch_timing`): on "start US-N", create the branch BEFORE writing any spec/plan/test files.
- PR per US: Summary / Linked (Spec + Plan + Closes US-XX) / DoD / Test plan / Out of scope.

---

## Recommended next-session kickoff prompt

> Start US-29 — brainstorm DRF setup. Read `.Claude/m4_planning.md` then `.Claude/KinoMania_wymagania_funkcjonalne.md` §FR-16/20. Walk me through: settings (`REST_FRAMEWORK`/`SIMPLE_JWT`/`SPECTACULAR_SETTINGS`), top-level router aggregation for per-app `api/` submodules, and the base API test fixture (JWT-authed client).

After US-29 → US-30..36 follow the brainstorm/plan-directly classification above. After M4 → **M5 — Security & i18n polish (`v1.0.0`)**, US-37..US-43.
