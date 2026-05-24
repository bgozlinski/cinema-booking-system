# US-29 — DRF + JWT + drf-spectacular setup (design)

**Milestone:** M4 — REST API (`v0.4.0`)
**User story:** US-29 — DRF + JWT + drf-spectacular setup
**Branch:** `chore/M4-drf-setup`
**FR refs:** FR-16 (auth/JWT), FR-20 (OpenAPI), §4 (endpoint map), §8 (per-app `api/` structure)
**Date:** 2026-05-24
**Type:** brainstorm-required (per `.Claude/m4_planning.md`)

---

## 1. Goal

Remove the M4 hard blocker: install and configure the REST stack so that every
later US (US-30..US-36) is a thin serializer + permission + viewset layer over
the existing HTTP-agnostic M3 services. This US ships **infrastructure only** —
no domain endpoints.

**Definition of done (smoke):**
1. `GET /api/v1/schema/` → `200`, valid OpenAPI **3.1**, title "KinoMania API".
2. `GET /api/v1/docs/` → `200` (Swagger UI).
3. `GET /api/v1/redoc/` → `200` (ReDoc).
4. The `auth_client` fixture mints a working `Bearer` JWT for a user (proves simplejwt
   is installed and wired).
5. `tests/conftest.py` provides reusable API client fixtures (`api_client`, `auth_client`)
   that US-30+ tests build on.

> **Not in US-29 DoD — deferred to US-30:** the OpenAPI **security scheme**
> (`jwtAuth`/`bearerAuth` in `components.securitySchemes`). drf-spectacular only emits
> a security scheme for auth classes attached to *actual endpoints* in the schema; with
> zero domain endpoints in infra-only US-29, no `securitySchemes` block is generated.
> The first `JWTAuthentication`-protected endpoint (US-30 `me`/`token`) makes it appear,
> and US-30 asserts it. The FR-20 `bearerAuth` rename stays in US-35.

## 2. Scope boundary

**In scope (US-29):**
- Add deps: `djangorestframework`, `djangorestframework-simplejwt`, `django-filter`,
  `drf-spectacular`, and dev `djangorestframework-stubs[compatible-mypy]`.
- `REST_FRAMEWORK`, `SIMPLE_JWT`, `SPECTACULAR_SETTINGS` in `settings/base.py`.
- Top-level `/api/v1/` aggregation in a new `settings/api_urls.py` module, mounting
  only the drf-spectacular views (`schema`/`docs`/`redoc`). It carries a marked
  placeholder where US-30+ app `api/urls.py` includes will be added.
- API test fixtures in `tests/conftest.py` (anon client, JWT-auth client factory,
  autouse throttle-cache clear).
- Smoke tests under `tests/api/test_setup.py`.
- `pyproject.toml` mypy plugin + `.env.example` env vars.

**Out of scope (later US):**
- `token`/`token/refresh`/`register`/`me` endpoints → **US-30**.
- Domain viewsets/serializers/filters (movies, screenings, bookings, …) → **US-31+**.
- Per-view `auth` scope throttle wiring (token/register anti-bruteforce) → **US-30**.
- drf-spectacular **strict-mode** CI gate (fail on schema warnings) → **US-35**.
- Throttle-trip (`429`) tests → **US-36**.
- Redis / external cache backend → deployment / M5. Default LocMemCache suffices here.

## 3. Cross-cutting decisions (from `m4_planning.md`, confirmed)

| Decision | Choice |
|----------|--------|
| API layout | Per-app `api/` submodules, aggregated by a top-level router. |
| Router location | **`settings/api_urls.py`** (plain module, no new app — consistent with `settings/urls.py` being `ROOT_URLCONF`). Each app owns its own `DefaultRouter` in `apps/<app>/api/urls.py` from US-31 on. |
| Versioning | `/api/v1/` URL prefix. |
| JWT | simplejwt; `access = 15 min`, `refresh = 7 days` (env-tunable). |
| Pagination | `PageNumberPagination`, `PAGE_SIZE = 12`. |
| Throttling | **Enforced from US-29**: `anon 100/h`, `user 1000/h` global; `auth 20/h` scope defined now, wired per-view in US-30. |
| Throttle in tests | autouse `cache.clear()` fixture resets per-test counters (prevents cross-test `429` bleed in the shared per-process LocMemCache). |
| OpenAPI | drf-spectacular; `bearerAuth` auto-detected from simplejwt; `@extend_schema` added incrementally per viewset (US-31+); strict CI gate at US-35. |

## 4. Dependencies

```
poetry add djangorestframework djangorestframework-simplejwt django-filter drf-spectacular
poetry add --group dev "djangorestframework-stubs[compatible-mypy]"
```

Poetry resolves the latest versions compatible with Django 6.0. **Risk:** if DRF /
Django-6.0 resolution conflicts, surface it before continuing (DRF ≥ 3.16 is expected
to be fine). User runs all `poetry`/`git` commands; Claude proposes content only.

## 5. Settings — `settings/base.py`

Claude proposes the skeleton; the user writes the file (per role division).

**New `env()` defaults** (in the `environ.Env(...)` block):

| Var | Type | Default |
|-----|------|---------|
| `JWT_ACCESS_TOKEN_LIFETIME_MIN` | int | `15` |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | int | `7` |
| `THROTTLE_ANON` | str | `"100/hour"` |
| `THROTTLE_USER` | str | `"1000/hour"` |
| `THROTTLE_AUTH` | str | `"20/hour"` |

**`INSTALLED_APPS`** += `rest_framework`, `django_filters`, `drf_spectacular`
(after Django contrib apps, before/around the `apps.*` block).

**`REST_FRAMEWORK`:**
- `DEFAULT_AUTHENTICATION_CLASSES`: `JWTAuthentication`, `SessionAuthentication`
  (both always — Session is harmless for token clients and enables the browsable API).
- `DEFAULT_PERMISSION_CLASSES`: `IsAuthenticated` — secure baseline; public read
  viewsets relax to `IsAuthenticatedOrReadOnly` in US-31.
- `DEFAULT_PAGINATION_CLASS`: `PageNumberPagination`; `PAGE_SIZE`: `12`.
- `DEFAULT_FILTER_BACKENDS`: `DjangoFilterBackend`, `SearchFilter`, `OrderingFilter`.
- `DEFAULT_THROTTLE_CLASSES`: `AnonRateThrottle`, `UserRateThrottle`.
- `DEFAULT_THROTTLE_RATES`: `{"anon": THROTTLE_ANON, "user": THROTTLE_USER, "auth": THROTTLE_AUTH}`.
- `DEFAULT_SCHEMA_CLASS`: `drf_spectacular.openapi.AutoSchema`.

**`SIMPLE_JWT`:**
- `ACCESS_TOKEN_LIFETIME = timedelta(minutes=JWT_ACCESS_TOKEN_LIFETIME_MIN)`.
- `REFRESH_TOKEN_LIFETIME = timedelta(days=JWT_REFRESH_TOKEN_LIFETIME_DAYS)`.
- `AUTH_HEADER_TYPES = ("Bearer",)`.

**`SPECTACULAR_SETTINGS`:**
- `TITLE = "KinoMania API"`.
- `DESCRIPTION = "REST API for the KinoMania cinema booking system — public catalog, JWT-authenticated bookings, and staff administration."`.
- `VERSION = "0.4.0"`.
- `OAS_VERSION = "3.1.0"` — FR-20 requires OpenAPI 3.1 (drf-spectacular defaults to 3.0.3).
- `SERVE_INCLUDE_SCHEMA = False` (don't embed the raw schema endpoint in itself).
- `COMPONENT_SPLIT_REQUEST = True` (separate request/response components — cleaner
  schema as serializers land).

US-35 owns the strict-mode CI gate, request/response examples, and `@extend_schema`
polish; US-29 only sets the base config above so the version/title/security scheme
are correct from the start.

**No `CACHES` block** — Django's default LocMemCache backs throttling here.

## 6. URL aggregation

**New `settings/api_urls.py`:**
```
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # US-30+: include each app's api/urls.py here, e.g.
    #   path("", include("apps.cinema.api.urls")),
]
```

**`settings/urls.py`:** add `path("api/v1/", include("settings.api_urls"))` to
`urlpatterns` (before the `if settings.DEBUG:` static block).

## 7. Test fixtures — `tests/conftest.py` (Claude writes; all test code is Claude's)

Extend the existing file (keeps the Stripe fixtures):
- `api_client` → `rest_framework.test.APIClient()` (anonymous).
- `auth_client` → **factory** fixture: `auth_client(user)` returns a fresh
  `APIClient` credentialed with `Authorization: Bearer <access>`, where the access
  token comes from `rest_framework_simplejwt.tokens.RefreshToken.for_user(user).access_token`.
  This is the canonical authed-client pattern reused by all US-30+ API tests.
- `_clear_throttle_cache` → **autouse** fixture: `from django.core.cache import cache; cache.clear()`
  before each test so DRF throttle counters reset per-test.

## 8. Smoke tests — `tests/api/test_setup.py` (Claude writes)

New `tests/api/` package (`__init__.py` + `test_setup.py`):
- `GET /api/v1/schema/?format=json` → `200`; `response.json()["info"]["title"]` ==
  "KinoMania API" and `response.json()["openapi"]` starts with `"3.1"`.
- `GET /api/v1/docs/` → `200` (Swagger UI HTML renders; body contains "swagger").
- `GET /api/v1/redoc/` → `200` (ReDoc HTML renders; body contains "redoc").
- `auth_client(UserFactory())` returns a client whose `Authorization` header is a
  `Bearer …` token (proves the simplejwt token-mint path works). Needs the DB
  (`@pytest.mark.django_db`).

The first three use the `api_client` fixture. The OpenAPI **security scheme** is
**not** asserted here — see the §1 deferral note (no endpoints yet → drf-spectacular
emits no `securitySchemes`; US-30 covers it once `me`/`token` land).

## 9. `pyproject.toml` + `.env.example` (Claude proposes; user writes)

- `[tool.mypy]` `plugins` += `"mypy_drf_plugin.main"` (alongside `mypy_django_plugin.main`).
- `.env.example` += the five JWT/throttle vars from §5 (all documented, all defaulted).

## 10. No changes needed

- **CI (`.github/workflows/ci.yml`)** — the new settings vars all have safe defaults;
  no new CI env vars required.
- **pre-commit (`.pre-commit-config.yaml`)** — the mypy hook runs `language: system`
  (the Poetry venv), so it picks up `djangorestframework-stubs` and the DRF mypy
  plugin automatically once they're installed. No `additional_dependencies` edit.

## 11. Coverage impact

US-29 adds **no `apps/` code** — settings, `settings/api_urls.py`, `tests/`, and
config files are all outside `[tool.coverage.run] source = ["apps"]` (and `settings/*`
is explicitly omitted). So `--cov-fail-under=80` is unaffected by this US.

## 12. Risks

1. **DRF + Django 6.0 compatibility.** Verify Poetry resolves a DRF version supporting
   Django 6.0 (≥ 3.16 expected). Surface any conflict before writing code.
2. **JWT security scheme only appears with endpoints.** drf-spectacular emits a
   security scheme (default `jwtAuth`) only for auth classes attached to enumerated
   endpoints. Infra-only US-29 has none, so `components.securitySchemes` is absent —
   US-29 does **not** assert it (proves JWT via the token-minting `auth_client` fixture
   instead). US-30 asserts the scheme once `me`/`token` exist; US-35 renames to
   `bearerAuth` per FR-20.
3. **mypy + DRF stubs.** New `settings/api_urls.py` + conftest fixtures must pass mypy
   with `mypy_drf_plugin.main` enabled. Keep typing minimal/explicit.
4. **Throttle cross-test bleed.** Mitigated by the autouse `cache.clear()` fixture
   (§7). Without it, the shared per-process LocMemCache would accumulate anon counts
   across tests and eventually `429`.

## 13. Build order (for the plan)

1. Deps (`poetry add`) → confirm resolution.
2. `settings/base.py` (env vars + 3 DRF dicts + INSTALLED_APPS).
3. `settings/api_urls.py` + `settings/urls.py` mount.
4. `pyproject.toml` mypy plugin + `.env.example`.
5. `tests/conftest.py` fixtures + `tests/api/test_setup.py` smoke tests.
6. Green: `pytest`, `mypy .`, `ruff` clean.

First branch commit folds in the (currently untracked) `.Claude/m4_planning.md`
alongside this spec.
