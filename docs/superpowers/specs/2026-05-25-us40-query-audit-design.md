# US-40 — performance audit: Debug Toolbar + query-count budgets (design)

**Milestone:** M5 — Polish (`v1.0.0`)
**User story:** US-40 — Performance audit (Debug Toolbar + query-count assertions)
**Branch:** `perf/M5-query-audit`
**FR refs:** NFR (performance)
**Date:** 2026-05-25
**Type:** dev tooling + test-hardening (regression guards) — no production behavior change.
**Predecessor:** US-39 ✅ (error pages, merged #44).

---

## 1. Goal

Two things: (a) give the project an interactive query/timing profiler for development
(`django-debug-toolbar`), and (b) extend the `django_assert_max_num_queries` budget coverage to
the **API read endpoints** that lack it, locking in the already-applied `select_related`/
`prefetch_related` optimizations as regression guards.

**Definition of done:**
1. `django-debug-toolbar` is available under `runserver` (dev), shows SQL/timing on the HTML
   pages, and is **absent during tests and in production**.
2. The N+1-prone API read endpoints have query-count budgets: booking list + retrieve, admin
   booking list, admin cinema movie list/detail + screening list/detail.
3. Full suite + ruff/format/mypy green; coverage ≥ 80%; no behavior change for users.

## 2. Scope boundary

**In scope:**
- `django-debug-toolbar` as a **dev** dependency + dev-only wiring (`settings/dev.py`,
  `settings/urls.py`).
- New `django_assert_max_num_queries` tests for: booking API list + retrieve, admin booking
  list, admin cinema movie list/detail, admin cinema screening list/detail.
- Any `select_related`/`prefetch_related` fix a budget run reveals (likely none — viewsets are
  already optimized).

**Out of scope:**
- Web views + public API budgets — already covered (M2/M3 + `test_api_public.py`).
- Budgets on auth endpoints / flat-model admin (genre/hall/actor/director) — no relations to
  N+1 on.
- Optimizing endpoints that are already fast (this is a guard pass, not a rewrite).
- Production DDT; the Docker-gateway `INTERNAL_IPS` case (app runs on the host via `poetry`).

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| **DDT must not load in tests** | The suite runs under `settings.dev` (`DEBUG=True`, per `pyproject` `DJANGO_SETTINGS_MODULE`). DDT in `dev.py` would otherwise inject toolbar HTML into responses and add its own queries — breaking content assertions and skewing budgets. Gate the DDT wiring on `"pytest" not in sys.modules`. |
| DDT location | `settings/dev.py` (the dev profile) — never touches `base.py`/`prod.py`, so DDT can't reach production. |
| DDT URL gate | `settings/urls.py` adds `__debug__/` only when `"debug_toolbar" in settings.INSTALLED_APPS` — true under `runserver`, false in tests (gated out above) and prod. |
| Budget endpoints | The N+1-prone read endpoints lacking budgets (§2). Skips auth + flat-model admin. |
| Caps via measurement | Caps are set from an actual DB run (the engineer runs the test, reads the count, sets the cap). Tight enough to catch a regression; if a run exceeds the optimized expectation, that's a real N+1 → fix the viewset queryset. |
| Audit record | The budget assertions are the audit record — no separate audit doc (YAGNI). |

## 4. Debug Toolbar (`settings/dev.py` + `settings/urls.py`)

`pyproject.toml` dev group gains `django-debug-toolbar` (`poetry add --group dev
django-debug-toolbar`).

`settings/dev.py` — append at the end:
```python
import sys

# django-debug-toolbar — dev-only, and OFF during tests (the suite runs under settings.dev,
# so loading DDT here would inject toolbar HTML into responses and skew query-count budgets).
if "pytest" not in sys.modules:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware"),
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    INTERNAL_IPS = ["127.0.0.1"]
```
(`INSTALLED_APPS`/`MIDDLEWARE` are list-typed in `base.py`; `dev.py` already imports `*` from
base, so `+=`/`.insert()` mutate the dev copy.)

`settings/urls.py` — add inside/after the existing `if settings.DEBUG:` block:
```python
if "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
```
This is `True` only when §4's `dev.py` guard added the app (i.e. `runserver`, not pytest, not
prod).

> DDT injects into **HTML** responses for `INTERNAL_IPS` clients — it profiles the web pages
> (movie list/detail, screenings, bookings), not the JSON API. The API endpoints are covered by
> the §5 budgets instead.

## 5. Query-count budgets (Claude — extend the API test files)

Reuse the existing authenticated-API-client fixtures (JWT/force-auth as used in
`tests/booking/test_api.py`, `tests/cinema/test_api_admin.py`). For each endpoint, seed a
handful of rows (so an N+1 would show up as count growth), then wrap the request in
`django_assert_max_num_queries(cap)`:

| Endpoint | Test file | Optimization being guarded |
|----------|-----------|----------------------------|
| `GET` booking list | `tests/booking/test_api.py` | `select_related("screening__movie","screening__hall")` |
| `GET` booking retrieve | `tests/booking/test_api.py` | same |
| `GET` admin booking list | `tests/booking/test_api_admin.py` | `select_related("user","screening__movie")` |
| `GET` admin movie list + retrieve | `tests/cinema/test_api_admin.py` | `prefetch_related("genres","actors","directors")` |
| `GET` admin screening list + retrieve | `tests/cinema/test_api_admin.py` | `select_related("movie","hall")` |

**Caps:** set from the observed count (auth/user lookup + pagination `COUNT` + the main
`SELECT` + prefetch queries). The test seeds ≥ ~5 rows so the cap is independent of row count
(that's the N+1 guarantee — a fixed cap that doesn't grow with N). If the observed count grows
with the seeded row count, that's an N+1 → add the missing `select_related`/`prefetch_related`
to the viewset's `queryset`/`get_queryset` and re-measure.

## 6. Testing / verification

- New budget tests (above) — the deliverable.
- A guard that DDT stays out of tests: `assert "debug_toolbar" not in settings.INSTALLED_APPS`
  (a one-line test) — proves the `sys.modules` gate works, so future contributors don't
  accidentally activate it in CI.
- Full suite green; the rest of the suite is unaffected (no production code change unless a
  budget reveals an N+1 fix).

## 7. Coverage / migration

Dev-settings wiring + new tests (+ possibly a `select_related` line). No new app logic of
substance → coverage ≥ 80% holds. **No migration.**

## 8. Risks

1. **DDT in tests** (the central nuance) — would inject HTML + skew query counts. Mitigation:
   `"pytest" not in sys.modules` gate (§4) + the §6 guard test.
2. **Caps need a real DB** — set them from an actual run, not a guess; a too-tight cap fails
   loudly (then read the count and adjust or fix the N+1).
3. **DDT middleware ordering** — must sit after response-encoding middleware; this project has
   none, and inserting before `CommonMiddleware` is the conventional, safe spot.
4. **`INTERNAL_IPS` + Docker** — only matters if the *app* runs in a container; it runs on the
   host via `poetry`, so `127.0.0.1` is correct (out of scope otherwise).

## 9. Build order (for the plan)

1. `poetry add --group dev django-debug-toolbar`.
2. `settings/dev.py` DDT wiring (pytest-gated) + `settings/urls.py` URL gate.
3. Guard test: `"debug_toolbar"` not in `INSTALLED_APPS` under pytest.
4. Budget tests per §5 — write, run to read the count, set caps; fix a viewset queryset only if
   a run reveals an N+1.
5. Quality gate (pytest cov ≥ 80%, ruff, ruff format, mypy) + manual DDT smoke (`runserver`).

Status board (`.Claude/backlog.md`) flips US-40 → In Progress in the first commit.
