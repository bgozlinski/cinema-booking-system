# US-30 — Auth API (register / token / refresh / me) (design)

**Milestone:** M4 — REST API (`v0.4.0`)
**User story:** US-30 — Auth API: register/token/refresh/me + throttling
**Branch:** `feat/FR-16-auth-api`
**FR refs:** FR-16 (REST API auth), §4 (endpoint map), §8 (per-app `api/` structure)
**Date:** 2026-05-24
**Type:** mixed — stock simplejwt token views + reuse of M1 `accounts` activation; no business logic duplicated.
**Predecessor:** US-29 (DRF/JWT/spectacular infra) ✅ merged.

---

## 1. Goal

Expose JWT auth over the existing custom-`User` (email login) and M1 activation flow:
`register`, `token`, `token/refresh`, `me` under `/api/v1/auth/`. This is the first
per-app `api/` submodule (`apps/accounts/api/`); US-31+ follow the same layout.

**Definition of done (smoke):**
1. `POST /api/v1/auth/register/` → `201`, user created with `is_active=False`,
   activation email sent, **no JWT** in response, body `{user, detail}`.
2. `POST /api/v1/auth/token/` (active user, email + password) → `200 {access, refresh}`;
   inactive/just-registered user → `401`.
3. `POST /api/v1/auth/token/refresh/` (valid refresh) → `200 {access}`.
4. `GET /api/v1/auth/me/` (Bearer) → `200 {id, email, first_name, last_name, is_staff}`;
   anonymous → `401`.
5. Generated OpenAPI schema now exposes the JWT bearer security scheme
   (the assertion **deferred from US-29** — `MeView` puts `JWTAuthentication` into the schema).

## 2. Scope boundary

**In scope:** the four auth endpoints, the `apps/accounts/api/` submodule, the `auth`
throttle scope on register + token, `@extend_schema` for register/me, and tests.

**Out of scope (later / not needed):**
- Profile editing — `me` is **read-only** (FR-16 says "dane zalogowanego usera").
- Custom JWT claims — stock simplejwt payload (YAGNI).
- API re-implementation of activation — **reuse** M1 web activation; the email link
  points at the web `accounts:activate` view (FR-16 explicit).
- Throttle-trip (`429`) tests → US-36. `bearerAuth` rename → US-35.
- Domain resource viewsets (movies/screenings/bookings) → US-31+.

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Token views | **Stock** simplejwt `TokenObtainPairView` + `TokenRefreshView`. Email login works via `User.USERNAME_FIELD = "email"`. |
| `me` | **Read-only** `RetrieveAPIView`. |
| Throttle scope | `auth` (20/h) on **register + token only**; refresh + me keep global anon/user throttle. |
| Register response | `{user, detail}`, **201, no JWT** (activation gates login). |
| URL submodule | `apps/accounts/api/{serializers,views,urls}.py`; `app_name = "accounts_api"`; plain `path()` list (no router — these are APIViews, not a ViewSet). |

## 4. Components

### `apps/accounts/api/serializers.py`
- **`UserSerializer(serializers.ModelSerializer)`** — `Meta.fields = ("id", "email",
  "first_name", "last_name", "is_staff")`, all read-only. Used by `me` and embedded in
  the register response.
- **`RegisterSerializer(serializers.ModelSerializer)`** — `Meta.fields = ("email",
  "password", "first_name", "last_name")`; `password` is `write_only` (and
  `style={"input_type": "password"}`). `first_name`/`last_name` optional
  (`required=False`). Email uniqueness is enforced automatically by the model's
  `unique=True` (DRF adds a `UniqueValidator` → `400`). `validate_password(value)`
  runs `django.contrib.auth.password_validation.validate_password`. `create(validated)`
  → `User.objects.create_user(is_active=False, **validated)` (manager hashes the
  password and persists `first_name`/`last_name`/`is_active`).
- **`RegisterResponseSerializer(serializers.Serializer)`** — `user = UserSerializer()`,
  `detail = serializers.CharField()`. Documentation-only: gives drf-spectacular a clean
  response schema for the custom register body (keeps US-35 strict mode warning-free).

### `apps/accounts/api/views.py`
- **`RegisterView(generics.CreateAPIView)`** — `permission_classes = [AllowAny]`,
  `serializer_class = RegisterSerializer`, `throttle_classes = [ScopedRateThrottle]`,
  `throttle_scope = "auth"`. Overridden `create()`:
  ```
  serializer = self.get_serializer(data=request.data)
  serializer.is_valid(raise_exception=True)
  user = serializer.save()
  send_activation_email(user, request._request)
  data = {"user": UserSerializer(user).data, "detail": "Activation email sent."}
  return Response(data, status=201)
  ```
  Decorated with `@extend_schema(responses=RegisterResponseSerializer)`.
- **`AuthTokenObtainPairView(TokenObtainPairView)`** — subclass only to attach
  `throttle_classes = [ScopedRateThrottle]`, `throttle_scope = "auth"`.
- **`MeView(generics.RetrieveAPIView)`** — `permission_classes = [IsAuthenticated]`,
  `serializer_class = UserSerializer`, `get_object(self)` → `self.request.user`.
  Decorated with `@extend_schema(responses=UserSerializer)`.

### `apps/accounts/api/urls.py`
```python
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api.views import AuthTokenObtainPairView, MeView, RegisterView

app_name = "accounts_api"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", AuthTokenObtainPairView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
]
```

### `settings/api_urls.py`
Replace the US-30 placeholder comment with:
```python
    path("auth/", include("apps.accounts.api.urls")),
```
(`include` must be added to the imports.) Final auth URLs:
`/api/v1/auth/register/`, `/token/`, `/token/refresh/`, `/me/`.

## 5. Activation reuse (no duplication)

`send_activation_email(user, request)` from `apps/accounts/emails.py` is reused unchanged.
It reverses the **web** `accounts:activate` URL and emails the absolute link. Flow:

```
POST /api/v1/auth/register/  →  User(is_active=False) + activation email
        user clicks web link  →  accounts:activate sets is_active=True
POST /api/v1/auth/token/      →  now succeeds (200 {access, refresh})
```

`request._request` (the underlying `HttpRequest`) is passed to `send_activation_email`
so `build_absolute_uri` works and the type matches the helper's `HttpRequest` hint.

## 6. Throttling

The `auth` scope rate (20/h) was defined in US-29's `DEFAULT_THROTTLE_RATES`. Attaching
`throttle_classes = [ScopedRateThrottle]` + `throttle_scope = "auth"` to `RegisterView`
and `AuthTokenObtainPairView` **replaces** the global anon/user throttle on those two
views with the stricter 20/h scope (keyed by IP for anonymous callers). `token/refresh`
and `me` retain the global throttle. Throttle-trip behaviour is tested in US-36.

## 7. OpenAPI

`MeView` uses the default `JWTAuthentication`, so it appears in the schema as a
JWT-protected operation — which makes drf-spectacular emit the `jwtAuth` (http/bearer)
security scheme. The schema assertion deferred from US-29 is added here. `@extend_schema`
documents the register response and the `me` response; simplejwt's token views are
auto-documented by drf-spectacular's bundled extension. The `bearerAuth` rename remains
US-35.

## 8. Testing (Claude writes)

**`tests/accounts/test_api_auth.py`** (uses `api_client` / `auth_client` fixtures + `UserFactory`):
- **register** — valid POST → `201`; user persisted with `is_active=False`; response has
  no `access`/`refresh`; body matches `{user: {email, first_name, last_name, ...}, detail}`;
  `len(mail.outbox) == 1`. Duplicate email → `400` (email field error). Password failing
  validators → `400` (password field error). Missing email/password → `400`.
- **token** — active user with correct password → `200 {access, refresh}`; a freshly
  registered (inactive) user → `401`; wrong password → `401`.
- **token/refresh** — valid refresh token → `200 {access}`.
- **me** — `auth_client(user)` → `200` with `{id, email, first_name, last_name, is_staff}`;
  anonymous `api_client` → `401`.

**`tests/api/test_setup.py`** (addition): `GET /api/v1/schema/?format=json` →
`components.securitySchemes` contains a scheme with `type == "http"` and
`scheme == "bearer"` (now present because of `MeView`).

## 9. Coverage / migration

US-30 adds real `apps/accounts/api/` code, so it counts toward coverage — the tests above
keep it ≥ 80%. No model changes → no migration.

## 10. Risks

1. **simplejwt + email login.** `TokenObtainPairView` authenticates by `USERNAME_FIELD`
   (`email`) — the obtain payload key is `email`. Verified by the token happy-path test.
2. **Inactive-user login.** Django's `ModelBackend` rejects `is_active=False`, so simplejwt
   returns `401` for just-registered users — asserted directly (it's the activation gate).
3. **DRF Request vs HttpRequest.** Pass `request._request` to `send_activation_email`
   (drf-stubs types `_request` as `HttpRequest`) — avoids a mypy `[arg-type]` error.
4. **Throttle replaces global classes.** Setting `throttle_classes` on a view overrides
   the global list; that's intended (auth 20/h is stricter than anon 100/h).
5. **Strict schema (US-35 prep).** Custom register response documented via
   `RegisterResponseSerializer` + `@extend_schema` so no drf-spectacular warning is
   introduced now.

## 11. Build order (for the plan)

1. `serializers.py` (UserSerializer, RegisterSerializer, RegisterResponseSerializer) + tests.
2. `views.py` (RegisterView, AuthTokenObtainPairView, MeView) + tests.
3. `urls.py` + mount in `settings/api_urls.py`; run endpoint tests green.
4. Schema security-scheme assertion in `tests/api/test_setup.py`.
5. Quality gate: pytest (cov ≥ 80%), ruff, mypy.

The first branch commit folds in the `backlog.md` board update (US-29 → Done, US-30 → In
Progress) made when this US started.
