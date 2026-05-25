# US-36 — API throttling + tests (design)

**Milestone:** M4 — REST API (`v0.4.0`) — **final story**
**User story:** US-36 — API throttling per scope + tests
**Branch:** `feat/FR-16-api-throttling`
**FR refs:** FR-16 (auth throttle 20/h), NFR security table (anon 100/h, user 1000/h)
**Date:** 2026-05-25
**Type:** plan-directly (S) — **test-only**, no production code change, no migration.
**Predecessor:** US-29 (throttle config) + US-30 (auth scope) … US-35 ✅ merged.

---

## 1. Goal

Prove the configured DRF throttles trip `429` per scope. The rates are already wired and
FR-correct, so this US adds the missing tests (NFR/FR-14 "testy throttli — N+1 zapytanie
zwraca 429").

## 2. Already configured (no change)

- **US-29** — global `DEFAULT_THROTTLE_CLASSES = (AnonRateThrottle, UserRateThrottle)`;
  `DEFAULT_THROTTLE_RATES = {"anon": "100/hour", "user": "1000/hour", "auth": "20/hour"}`
  (env-driven). Backed by the default `LocMemCache`.
- **US-30** — `ScopedRateThrottle` with `throttle_scope = "auth"` on `RegisterView` and
  `AuthTokenObtainPairView` (replaces the global classes on those two views).

The values match FR-16 (`auth` 20/h) and the NFR table — nothing to tune.

## 3. Deliverable

`tests/api/test_throttling.py` — four tests. Each shrinks the relevant rate via
`override_settings` and loops past it. The autouse `_clear_throttle_cache` fixture (US-29)
resets the cache before each test, so counters start clean and don't bleed across tests.

```python
from django.conf import settings
from django.test import override_settings

THROTTLED = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {
    "anon": "2/min", "user": "2/min", "auth": "2/min",
}}
```

- **`test_anon_throttled`** — `@override_settings(REST_FRAMEWORK=THROTTLED)`; anon
  `GET /api/v1/movies/` ×3 → first two `200`, third `429` (`AnonRateThrottle`, IP-keyed).
- **`test_user_throttled`** — authed `GET /api/v1/movies/` ×3 → third `429`
  (`UserRateThrottle`, user-keyed).
- **`test_auth_scope_throttled`** — `POST /api/v1/auth/token/` ×3 → third `429`
  (`ScopedRateThrottle` scope `auth`; throttling runs in `initial()` before authentication,
  so bad-credential posts still count — the body can be minimal).
- **`test_within_limit_not_throttled`** — a single anon `GET /api/v1/movies/` → `200`
  (sanity: throttling isn't always-on).

`override_settings(REST_FRAMEWORK=...)` triggers DRF's `setting_changed` receiver, which
reloads `api_settings`; a fresh throttle instance per request then reads the shrunk rate.
Spreading `settings.REST_FRAMEWORK` preserves the auth/pagination/filter config so the
endpoints still work under the override.

## 4. Why test-only

The rates are correct (FR-16 / NFR) and already enforced globally (US-29) + per-scope
(US-30). US-36 is the verification the backlog/FR calls for; no settings or view changes.

## 5. Testing notes / risks

1. **`override_settings` + DRF rate reload** — DRF resets `api_settings` on the
   `setting_changed` signal, and throttle instances read the rate at request time, so the
   shrunk rate applies. (If a rate somehow didn't reload, the test would not reach `429` and
   fail loudly — no silent pass.)
2. **Cache isolation** — the autouse `_clear_throttle_cache` (US-29) clears the default
   cache before each test; without it, `2/min` counters would bleed across tests.
3. **`auth` scope on a failing login** — `POST /auth/token/` with no/garbage credentials
   still increments the `auth` throttle (checked before the serializer), so the loop reaches
   `429` regardless of credential validity.

## 6. Coverage / migration

Test-only; no `apps/` code added → coverage threshold unaffected (slightly exercises the
existing throttle path). **No migration.**

## 7. Build order (for the plan)

1. `tests/api/test_throttling.py` (4 tests) — run green.
2. Quality gate (pytest cov ≥ 80%, ruff, mypy).

First branch commit folds in the `backlog.md` board update (US-35 → Done, US-36 → In
Progress). After merge: **M4 complete → `v0.4.0` tag + GitHub release**.
