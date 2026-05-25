# US-36 — API throttling + tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tests proving the configured DRF throttles trip `429` per scope (anon / user / auth) — the last M4 story, test-only.

**Architecture:** `tests/api/test_throttling.py` shrinks each rate via `override_settings` (spreading the real `REST_FRAMEWORK` so other config survives) and loops past it. The autouse `_clear_throttle_cache` fixture (US-29) isolates counters per test. No production code changes — the rates are already FR-correct.

**Tech Stack:** DRF throttling (`AnonRateThrottle`, `UserRateThrottle`, `ScopedRateThrottle`); pytest / pytest-django; `override_settings`.

---

## Role division

- **Claude** writes all test code (`tests/**`).
- **User** runs all `git`/`pytest`.

## Spec

`docs/superpowers/specs/2026-05-25-us36-throttling-design.md`

## File structure

| File | Action | Responsibility | Author |
|------|--------|----------------|--------|
| `tests/api/test_throttling.py` | create | 429 tests per scope + within-limit sanity | Claude |

No production files change. No migration.

## Note on TDD

Like US-33, this US adds **no production code** — throttling is already enabled (US-29/30).
The tests are verification: they pass on first run (with the shrunk rates). If a test does
*not* reach `429`, that's a real signal (e.g. `override_settings` didn't reload the rate) —
investigate, don't paper over.

---

### Task 1: Throttle tests

**Files:**
- Create: `tests/api/test_throttling.py`

- [ ] **Step 1 [Claude]: Write the throttle tests**

Create `tests/api/test_throttling.py`:
```python
import pytest
from django.conf import settings
from django.test import override_settings

from tests.accounts.factories import UserFactory

pytestmark = pytest.mark.django_db

MOVIES_URL = "/api/v1/movies/"
TOKEN_URL = "/api/v1/auth/token/"

# Shrink every rate but keep the rest of the REST_FRAMEWORK config intact.
THROTTLED = {
    **settings.REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"anon": "2/min", "user": "2/min", "auth": "2/min"},
}


@override_settings(REST_FRAMEWORK=THROTTLED)
def test_anon_throttled(api_client):
    assert api_client.get(MOVIES_URL).status_code == 200
    assert api_client.get(MOVIES_URL).status_code == 200
    assert api_client.get(MOVIES_URL).status_code == 429  # AnonRateThrottle (IP-keyed)


@override_settings(REST_FRAMEWORK=THROTTLED)
def test_user_throttled(auth_client):
    client = auth_client(UserFactory())
    assert client.get(MOVIES_URL).status_code == 200
    assert client.get(MOVIES_URL).status_code == 200
    assert client.get(MOVIES_URL).status_code == 429  # UserRateThrottle (user-keyed)


@override_settings(REST_FRAMEWORK=THROTTLED)
def test_auth_scope_throttled(api_client):
    # Throttling runs in initial() before auth, so bad-credential posts still count.
    payload = {"email": "nobody@example.com", "password": "wrong"}
    assert api_client.post(TOKEN_URL, payload, format="json").status_code in (200, 401)
    api_client.post(TOKEN_URL, payload, format="json")
    assert api_client.post(TOKEN_URL, payload, format="json").status_code == 429


def test_within_limit_not_throttled(api_client):
    # Real rates (anon 100/h) — a single request is not throttled.
    assert api_client.get(MOVIES_URL).status_code == 200
```

- [ ] **Step 2 [User]: Run the throttle tests**

Run: `poetry run pytest tests/api/test_throttling.py -q --no-cov`
Expected: PASS (4 passed). These verify already-configured throttles; they should pass on
first run. (If `test_anon_throttled`/`test_user_throttled`/`test_auth_scope_throttled` don't
reach `429`, the rate override didn't apply — stop and report rather than weaken the test.)

- [ ] **Step 3 [User]: Commit (folds in the backlog board update)**

```bash
git add tests/api/test_throttling.py .Claude/backlog.md
git commit -m "test(FR-16): API throttling 429 per scope (anon/user/auth) (US-36)"
```

---

### Task 2: Quality gate

- [ ] **Step 1 [User]: Full suite with coverage**

Run: `poetry run pytest`
Expected: PASS, coverage ≥ 80%.

- [ ] **Step 2 [User]: Lint + format + type-check**

Run: `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .`
Expected: clean (test-only change; `tests.*` is mypy-excluded).

---

## Out of scope

Rate tuning beyond the FR values · M5 security hardening · the `v0.4.0` tag/release (a separate step after this PR merges).

## Test plan summary

- `tests/api/test_throttling.py`: anon `429` (movies), user `429` (movies authed), `auth`
  scope `429` (token), within-limit `200` sanity. Rates shrunk via `override_settings`;
  cache isolated by the autouse `_clear_throttle_cache` fixture.
- No migration; coverage ≥ 80%.

## After merge — M4 close

Once this PR merges, M4 (US-29..US-36) is complete:
1. `git tag v0.4.0` + `gh release create v0.4.0` (REST API milestone).
2. Update `project_kinomania_bootstrap.md`: M4 COMPLETE, transition to M5 (US-37..US-43,
   Security & i18n polish, `v1.0.0`).
