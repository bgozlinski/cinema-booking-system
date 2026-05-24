# US-35 — OpenAPI docs + strict CI (design)

**Milestone:** M4 — REST API (`v0.4.0`)
**User story:** US-35 — OpenAPI docs + strict-mode CI gate
**Branch:** `feat/FR-20-openapi-docs`
**FR refs:** FR-20 (OpenAPI docs), §4
**Date:** 2026-05-25
**Type:** plan-directly (S) — one warning fix + a security-scheme rename + a strict gate + light polish.
**Predecessor:** US-29 (spectacular setup) … US-34 ✅ merged.

---

## 1. Goal

Make the OpenAPI schema warning-clean and CI-enforced, rename the JWT security scheme to
`bearerAuth` (FR-20 §524), and add targeted endpoint documentation. Swagger UI (`/docs/`)
and ReDoc (`/redoc/`) already exist (US-29).

**Definition of done:**
1. `drf-spectacular` generates the schema with **zero warnings**, enforced by a pytest test
   (runs in the existing CI test job — FR-20 §525).
2. The schema's security scheme is named **`bearerAuth`** (`type: http`, `scheme: bearer`,
   `bearerFormat: JWT`).
3. The non-obvious endpoints (booking create + actions, admin refund, auth) carry
   `@extend_schema` summaries/descriptions; a richer top-level API description.

## 2. Current warnings (baseline — `spectacular --validate --fail-on-warn`)

**4 warnings (2 unique), both from `apps/booking/api/viewsets.py` `BookingViewSet`:**
- "Failed to obtain model through view's queryset … Exception: Field 'id' expected a number
  but got AnonymousUser." — schema generation calls `get_queryset()` with a fake
  `AnonymousUser`, and `Booking.objects.filter(user=AnonymousUser)` raises.
- "could not derive type of path parameter 'id' … Defaulting to 'string'." — a consequence
  of the queryset failure (no model → can't type `{id}`).

**No component-name collisions** — admin serializers have distinct class names
(`AdminActorSerializer` → `AdminActor`, etc.), so they get distinct components. The only
fix needed is the `BookingViewSet` queryset guard.

## 3. Scope boundary

**In scope:** the `swagger_fake_view` guard, the `bearerAuth` extension, the strict pytest
gate, targeted `@extend_schema` polish, a richer `SPECTACULAR_SETTINGS["DESCRIPTION"]`.

**Out of scope:** throttling + its tests → US-36; any new endpoints; exhaustive
`@extend_schema` on every CRUD op (auto-schema already covers them — confirmed by the
warning-clean baseline once the guard lands).

## 4. Fix the `BookingViewSet` schema warning

`apps/booking/api/viewsets.py` — add a guard at the top of `get_queryset`:
```python
def get_queryset(self):
    if getattr(self, "swagger_fake_view", False):
        return Booking.objects.none()
    user = cast("User", self.request.user)
    qs = Booking.objects.select_related("screening__movie", "screening__hall")
    if not user.is_staff:
        qs = qs.filter(user=user)
    return qs.order_by("-created_at")
```
`swagger_fake_view` is `True` only during drf-spectacular introspection. Returning
`Booking.objects.none()` lets spectacular derive the model (→ types the `{id}` path param,
clears both warnings) without touching `request.user`. (The cinema/admin viewsets don't
filter by `request.user`, so they don't need the guard.)

## 5. `bearerAuth` security scheme

`apps/accounts/api/schema.py` (new):
```python
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BearerJWTScheme(OpenApiAuthenticationExtension):
    target_class = "rest_framework_simplejwt.authentication.JWTAuthentication"
    name = "bearerAuth"
    priority = 1  # override drf-spectacular's built-in jwtAuth (priority 0) cleanly

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
```
The extension registers on import. `settings/api_urls.py` imports it so it's loaded when the
URLconf is walked during generation:
```python
import apps.accounts.api.schema  # noqa: F401  (registers the bearerAuth extension)
```
`priority = 1` is drf-spectacular's documented way to override an included extension — it
wins over the built-in `jwtAuth` without a duplicate-registration warning (verified by the
strict gate, which would fail if it warned).

## 6. Strict CI gate (pytest)

`tests/api/test_schema.py` (new):
```python
from io import StringIO

import pytest
from django.core.management import call_command


def test_schema_generates_without_warnings():
    # --fail-on-warn raises SchemaGenerationError on any warning; --validate checks the spec.
    call_command("spectacular", "--validate", "--fail-on-warn", stdout=StringIO())


@pytest.mark.django_db
def test_security_scheme_named_bearer_auth(api_client):
    schemes = api_client.get("/api/v1/schema/?format=json").json()["components"]["securitySchemes"]
    assert "bearerAuth" in schemes
    assert schemes["bearerAuth"]["scheme"] == "bearer"
```
This runs in the existing pytest/CI test job, so no `ci.yml` change is needed — FR-20 §525
("W CI: pytest weryfikuje … bez Warnings") is satisfied by the test itself.

The US-30 shape-based assertion (`test_schema_exposes_jwt_bearer_scheme`) still passes (the
scheme is still `type: http`/`scheme: bearer`); this US adds the name assertion.

## 7. Targeted `@extend_schema` polish

Most target endpoints already have `@extend_schema` (added in their US); enrich them with
`summary` + `description` (no behavioural change):
- `apps/booking/api/viewsets.py` — `create` ("Create a booking and start Stripe checkout"),
  `cancel`, `checkout`.
- `apps/booking/api/admin.py` — `refund` ("Manually refund a CONFIRMED booking (admin)").
- `apps/accounts/api/views.py` — `RegisterView` ("Register; sends activation email, no JWT"),
  `MeView` ("Current authenticated user").
- One `OpenApiExample` on the booking `create` response (the non-obvious `{booking,
  checkout_url}` shape).

Richer `SPECTACULAR_SETTINGS["DESCRIPTION"]` in `settings/base.py` — a short markdown
overview (auth flow, `/admin/` staff-only, throttling note). `VERSION` stays `"0.4.0"`
(matches the milestone tag; FR-20 §522's `1.0.0` is aspirational — noted, not adopted).

## 8. Testing

- `tests/api/test_schema.py` — strict generation (no warnings) + `bearerAuth` named scheme.
- Existing schema tests (US-29 `test_setup.py`, US-30 shape assertion, US-33 checkout-in-schema)
  stay green.
- No new behavioural tests (this US documents/validates; it doesn't change endpoint behaviour
  beyond the schema-only `swagger_fake_view` guard, which the strict gate + existing booking
  API tests cover).

## 9. Coverage / migration

`swagger_fake_view` guard + `bearerAuth` extension are small real code (covered indirectly by
the booking API tests + the strict gate). No migration.

## 10. Risks

1. **Extension override** — if `priority=1` doesn't cleanly override (duplicate-registration
   warning), the strict gate fails and we adjust (e.g. confirm import order). Verified by the
   gate itself.
2. **`call_command` strict test** — `--fail-on-warn` must raise on warnings (it does — that's
   how we found the baseline). The test asserts no raise.
3. **`swagger_fake_view` guard** — must return a real (empty) `Booking` queryset so the model
   is still derivable; `Booking.objects.none()` does this.

## 11. Build order (for the plan)

1. Strict-gate test (red — 4 warnings) → `swagger_fake_view` guard (green).
2. `bearerAuth` extension + register + name-assertion test.
3. Targeted `@extend_schema` summaries/descriptions + `DESCRIPTION` (gate stays green).
4. Quality gate (pytest cov ≥ 80%, ruff, mypy).

First branch commit folds in the `backlog.md` board update (US-34 → Done, US-35 → In Progress).
