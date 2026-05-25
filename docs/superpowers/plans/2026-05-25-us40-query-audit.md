# US-40 — Debug Toolbar + API query-count budgets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `django-debug-toolbar` for dev profiling (off in tests/prod) and lock in the API read-endpoints' existing query optimizations with `django_assert_max_num_queries` regression guards.

**Architecture:** DDT is wired only in `settings/dev.py`, gated on `"pytest" not in sys.modules` (the suite runs under `settings.dev`), with the `__debug__/` URL gated on `"debug_toolbar" in INSTALLED_APPS`. New query-budget tests seed several rows and assert a fixed query cap on the booking + admin read endpoints — an N+1 would blow the cap.

**Tech Stack:** django-debug-toolbar (dev), pytest-django `django_assert_max_num_queries`, DRF APIClient fixtures (`api_client`, `auth_client`).

---

## Role division

- **User** writes app/config files (`settings/*.py`, `pyproject.toml`, any viewset fix) and runs all `git`/`pytest`/`poetry`/`manage.py` commands.
- **Claude** writes all test code (`tests/**`).

## Spec

`docs/superpowers/specs/2026-05-25-us40-query-audit-design.md`

## File structure

| File | Action | Responsibility | Author |
|------|--------|----------------|--------|
| `pyproject.toml` | modify | `django-debug-toolbar` in dev group | User |
| `settings/dev.py` | modify | DDT wiring, gated `"pytest" not in sys.modules` | User |
| `settings/urls.py` | modify | `__debug__/` URL gated on `"debug_toolbar" in INSTALLED_APPS` | User |
| `tests/test_dev_settings.py` | create | guard: DDT absent under pytest | Claude |
| `tests/booking/test_api.py` | modify | booking list + retrieve query budgets | Claude |
| `tests/booking/test_api_admin.py` | modify | admin booking list query budget | Claude |
| `tests/cinema/test_api_admin.py` | modify | admin movie + screening list/detail budgets | Claude |
| `apps/*/api/*.py` | modify *(only if a budget reveals an N+1)* | add `select_related`/`prefetch_related` | User |
| `.Claude/backlog.md` | modify | status board → US-40 In Progress | User |

No migration.

## Caps note (read before Tasks 3–4)

The caps below are **starting estimates** (auth user lookup + pagination `COUNT` + the main
`SELECT` + any prefetch). Each test seeds ~8 rows, so a real N+1 adds ~8 queries and blows the
cap. When you run a budget test:
- **PASS** → the optimization holds; optionally tighten the cap to `observed + 1` (a too-low cap's
  failure message prints the actual count).
- **FAIL** → read the actual count from the message. Re-run with the seed loop doubled (16 rows):
  if the count **rises**, it's an N+1 → add the missing `select_related`/`prefetch_related` to the
  viewset `queryset`/`get_queryset` and re-measure; if it **stays flat**, the cap was just too
  tight → raise it to `observed + 1`.

---

### Task 1: Debug Toolbar (dev-only, pytest-gated)

**Files:**
- Modify: `pyproject.toml`, `settings/dev.py`, `settings/urls.py`

- [ ] **Step 1 [User]: Add the dev dependency**

Run: `poetry add --group dev django-debug-toolbar`
Expected: `pyproject.toml` dev group gains `django-debug-toolbar`; `poetry.lock` updates.

- [ ] **Step 2 [User]: Wire DDT in `settings/dev.py` (append at the end)**

```python
import sys

# django-debug-toolbar — dev-only, and OFF during tests. The suite runs under settings.dev,
# so loading DDT here would inject toolbar HTML into responses and skew the query-count budgets.
if "pytest" not in sys.modules:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware"),
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    INTERNAL_IPS = ["127.0.0.1"]
```

- [ ] **Step 3 [User]: Gate the DDT URL in `settings/urls.py`**

Add (e.g. just after the existing `if settings.DEBUG:` static block):
```python
if "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
```
> (`path` and `include` are already imported in `settings/urls.py`.) The
> `"debug_toolbar" in INSTALLED_APPS` guard is `True` only under `runserver` — Step 2 added the
> app there, not under pytest, and never in prod.

- [ ] **Step 4 [User]: Sanity-check imports/migrations resolve**

Run: `poetry run python manage.py check`
Expected: `System check identified no issues`. (DDT is active here since this isn't pytest.)

---

### Task 2: Guard test — DDT absent under pytest

**Files:**
- Create: `tests/test_dev_settings.py`

- [ ] **Step 1 [Claude]: Write the guard**

Create `tests/test_dev_settings.py`:
```python
from django.conf import settings


def test_debug_toolbar_not_loaded_under_pytest():
    # DDT is gated on "pytest" not in sys.modules in settings/dev.py — it must stay out of the
    # test run, or it would inject toolbar HTML and add its own queries (breaking query budgets).
    assert "debug_toolbar" not in settings.INSTALLED_APPS
    assert not any("debug_toolbar" in m for m in settings.MIDDLEWARE)
```

- [ ] **Step 2 [User]: Run — should pass**

Run: `poetry run pytest tests/test_dev_settings.py -q --no-cov`
Expected: 1 passed (proves the `sys.modules` gate keeps DDT out of tests).

- [ ] **Step 3 [User]: Commit Tasks 1–2**

```bash
git add pyproject.toml poetry.lock settings/dev.py settings/urls.py tests/test_dev_settings.py
git commit -m "perf(NFR): django-debug-toolbar dev-only + test gate (US-40)"
```

---

### Task 3: Booking API query budgets

**Files:**
- Modify: `tests/booking/test_api.py`

- [ ] **Step 1 [Claude]: Add a budget class**

Append to `tests/booking/test_api.py` (module already has `BOOKINGS_URL`, `pytestmark =
pytest.mark.django_db`, and imports `UserFactory`, `BookingFactory`):
```python
class TestBookingQueryBudget:
    def test_list_is_bounded(self, auth_client, django_assert_max_num_queries):
        owner = UserFactory()
        for _ in range(8):
            BookingFactory(user=owner)
        client = auth_client(owner)  # token minted outside the assertion block
        with django_assert_max_num_queries(8):
            resp = client.get(BOOKINGS_URL)
        assert resp.status_code == 200
        assert resp.data["count"] == 8

    def test_retrieve_is_bounded(self, auth_client, django_assert_max_num_queries):
        owner = UserFactory()
        booking = BookingFactory(user=owner)
        client = auth_client(owner)
        with django_assert_max_num_queries(6):
            resp = client.get(f"{BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 200
```

- [ ] **Step 2 [User]: Run + finalize caps (see "Caps note")**

Run: `poetry run pytest tests/booking/test_api.py::TestBookingQueryBudget -v --no-cov`
Expected: 2 passed. If a cap fails, follow the Caps note (check for growth with 16 rows → fix
viewset, else raise cap). The booking viewsets use `select_related("screening__movie",
"screening__hall")` (list) and the same on retrieve, so the count should be flat/low.

---

### Task 4: Admin API query budgets

**Files:**
- Modify: `tests/booking/test_api_admin.py`, `tests/cinema/test_api_admin.py`

- [ ] **Step 1 [Claude]: Admin booking list budget — `tests/booking/test_api_admin.py`**

Append (module has `ADMIN_BOOKINGS_URL`, `pytestmark = pytest.mark.django_db`, `UserFactory`,
`BookingFactory`):
```python
class TestAdminBookingQueryBudget:
    def test_list_is_bounded(self, auth_client, django_assert_max_num_queries):
        for _ in range(8):
            BookingFactory()
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(8):
            resp = client.get(ADMIN_BOOKINGS_URL)
        assert resp.status_code == 200
        assert resp.data["count"] == 8
```
(Admin booking viewset: `Booking.objects.select_related("user", "screening__movie")`.)

- [ ] **Step 2 [Claude]: Admin cinema budgets — `tests/cinema/test_api_admin.py`**

Append (module has `pytestmark = pytest.mark.django_db` and imports the cinema factories +
`UserFactory`; if a factory import is missing, add it to the existing import block):
```python
class TestAdminCinemaQueryBudget:
    def test_movie_list_is_bounded(self, auth_client, django_assert_max_num_queries):
        for _ in range(8):
            MovieFactory(genres=[GenreFactory()], actors=[ActorFactory()], directors=[DirectorFactory()])
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(10):
            resp = client.get("/api/v1/admin/movies/")
        assert resp.status_code == 200
        assert resp.data["count"] == 8

    def test_movie_detail_is_bounded(self, auth_client, django_assert_max_num_queries):
        movie = MovieFactory(
            genres=[GenreFactory() for _ in range(4)],
            actors=[ActorFactory() for _ in range(4)],
            directors=[DirectorFactory() for _ in range(4)],
        )
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(9):
            resp = client.get(f"/api/v1/admin/movies/{movie.id}/")
        assert resp.status_code == 200

    def test_screening_list_is_bounded(self, auth_client, django_assert_max_num_queries):
        for _ in range(8):
            ScreeningFactory()
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(8):
            resp = client.get("/api/v1/admin/screenings/")
        assert resp.status_code == 200
        assert resp.data["count"] == 8

    def test_screening_detail_is_bounded(self, auth_client, django_assert_max_num_queries):
        screening = ScreeningFactory()
        client = auth_client(UserFactory(is_staff=True))
        with django_assert_max_num_queries(7):
            resp = client.get(f"/api/v1/admin/screenings/{screening.id}/")
        assert resp.status_code == 200
```
Required imports at the top of `tests/cinema/test_api_admin.py` (add any missing):
```python
from tests.accounts.factories import UserFactory
from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    MovieFactory,
    ScreeningFactory,
)
```

- [ ] **Step 3 [User]: Run + finalize caps**

Run: `poetry run pytest tests/booking/test_api_admin.py::TestAdminBookingQueryBudget tests/cinema/test_api_admin.py::TestAdminCinemaQueryBudget -v --no-cov`
Expected: 5 passed. Apply the Caps note to any failure (admin movie uses
`prefetch_related("genres","actors","directors")`; admin screening uses
`select_related("movie","hall")` — counts should be flat regardless of seeded rows).

- [ ] **Step 4 [User]: Commit Tasks 3–4**

```bash
git add tests/booking/test_api.py tests/booking/test_api_admin.py tests/cinema/test_api_admin.py
git commit -m "test(NFR): API read-endpoint query-count budgets (US-40)"
```
(If a budget revealed an N+1, include the viewset fix in this commit and mention it in the message.)

---

### Task 5: Quality gate + status board

- [ ] **Step 1 [User]: Full suite with coverage**

Run: `poetry run pytest`
Expected: PASS, coverage ≥ 80%. (`test_dev_settings.py` confirms DDT stays out of the run; no
production behavior changed unless a budget forced a viewset fix.)

- [ ] **Step 2 [User]: Lint + format + type-check**

Run: `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy .`
Expected: clean.

- [ ] **Step 3 [User]: Manual DDT smoke (optional)**

`poetry run python manage.py runserver` → open `http://127.0.0.1:8000/` → the Debug Toolbar
panel appears on the right; the SQL panel shows the page's queries. (It won't appear on the JSON
API endpoints — DDT injects into HTML only.)

- [ ] **Step 4 [User]: Status board**

In `.Claude/backlog.md` §7, move US-40 → In Progress (US-41 → Ready). Fold into a commit (or the
Task 4 commit).

---

## Out of scope

Web/public-API budgets (already covered) · auth + flat-model admin budgets · optimizing
already-fast endpoints · production DDT.

## Test plan summary

- `tests/test_dev_settings.py` — DDT absent under pytest (the gate works).
- Booking API: list + retrieve query budgets. Admin API: booking list, movie list/detail,
  screening list/detail budgets. Each seeds rows so an N+1 blows a fixed cap.
- Caps finalized from a real run (Caps note); a viewset `select_related`/`prefetch` fix only if a
  budget reveals growth-with-N. Coverage ≥ 80%; no migration.
