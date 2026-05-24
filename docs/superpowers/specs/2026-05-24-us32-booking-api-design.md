# US-32 — Booking API (design)

**Milestone:** M4 — REST API (`v0.4.0`)
**User story:** US-32 — Booking API: list/create/retrieve/cancel/checkout
**Branch:** `feat/FR-18-booking-api`
**FR refs:** FR-18 (REST bookings), §4 (endpoint map), §8 (per-app `api/` structure)
**Date:** 2026-05-24
**Type:** plan-directly (L) — thin serializer + permission layer over the M3 booking services; no business logic duplicated.
**Predecessor:** US-29/30/31 ✅ merged.

---

## 1. Goal

Expose owner-scoped booking management under `/api/v1/bookings/`, reusing the
HTTP-agnostic M3 services (`create_booking`, `cancel_booking`, `start_checkout`).
The API is a serializer + permission + error-mapping layer; the booking/refund/lock
logic already exists.

**Definition of done (smoke):**
1. `GET /api/v1/bookings/` (Bearer) → caller's bookings only (staff: all), `-created_at`.
2. `POST /api/v1/bookings/` `{screening_id, seats_count}` → `201 {booking, checkout_url}`
   (PENDING booking + Stripe session).
3. `GET /api/v1/bookings/<id>/` → owner/staff `200`; non-owner `404`.
4. `POST /api/v1/bookings/<id>/cancel/` → `200` CANCELLED (refund if CONFIRMED).
5. `POST /api/v1/bookings/<id>/checkout/` → `200 {checkout_url, session_id}` (retry).

## 2. Scope boundary

**In scope:** the booking viewset (list/create/retrieve + cancel/checkout actions),
serializers, `IsBookingOwnerOrStaff`, owner-scoping, and the BookingError→HTTP mapping.

**Out of scope (later US):**
- Checkout/webhook formalization → US-33 (the webhook stays the single web
  `/webhooks/stripe/`; the API only *starts* sessions).
- Admin/staff write API → US-34.
- `bearerAuth` rename + strict CI gate → US-35; throttle-trip tests → US-36.
- No `update`/`destroy` on bookings (mixin viewset, not full `ModelViewSet`).

## 3. Cross-cutting decisions (confirmed)

| Decision | Choice |
|----------|--------|
| ViewSet | `CreateModelMixin + ListModelMixin + RetrieveModelMixin + GenericViewSet` (no PUT/PATCH/DELETE) + `cancel`/`checkout` `@action`s. |
| Error → status | `NotEnoughSeatsError` + `BookingNotCancellableError` → **409**; `ScreeningInPastError` + invalid `seats_count` → **400**; `stripe.StripeError`/`RefundError` → **502**. |
| Create + Stripe down | Booking persisted (PENDING) → **201** `{booking, checkout_url: null, detail}`; client retries via `checkout/`. |
| Non-owner access | **404** everywhere (owner-scoped queryset hides existence) — standardized across the API, simpler/more private than the web's detail-403. |
| Webhook | **Not** duplicated — confirmation flows through the existing web `/webhooks/stripe/` (US-25). |

## 4. Components

### `apps/booking/api/serializers.py`
- **`BookingScreeningSerializer(ModelSerializer)`** — nested screening summary:
  `("id", "movie", "hall", "start_time", "price")`; `movie = MovieMiniSerializer`,
  `hall = HallSerializer` (imported from `apps.cinema.api.serializers`). **No**
  `available_seats_count` → keeps the booking list N+1-free.
- **`BookingSerializer(ModelSerializer)`** — read representation:
  `("id", "screening", "seats_count", "status", "total_price", "created_at",
  "expires_at")`; `screening = BookingScreeningSerializer(read_only=True)`;
  `total_price = serializers.DecimalField(max_digits=8, decimal_places=2,
  read_only=True)` (reads the model property). All read-only.
- **`BookingCreateSerializer(serializers.Serializer)`** — input only:
  - `screening_id = serializers.PrimaryKeyRelatedField(queryset=Screening.objects.all(),
    source="screening")`.
  - `seats_count = serializers.IntegerField(min_value=1, max_value=10)`.
  Not a `ModelSerializer` and no `create()` — the viewset calls the `create_booking`
  service with `validated_data["screening"]` + `validated_data["seats_count"]`.
- **`BookingCreateResponseSerializer(Serializer)`** — `booking = BookingSerializer()`,
  `checkout_url = serializers.CharField(allow_null=True)`, `detail =
  serializers.CharField(required=False)`. Doc-only (clean schema for the 201 body).
- **`CheckoutResponseSerializer(Serializer)`** — `checkout_url = CharField`,
  `session_id = CharField`. Doc-only for the checkout action.

### `apps/booking/api/permissions.py`
```python
class IsBookingOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        return obj.user == request.user or request.user.is_staff
```
`has_permission` defaults to `True` so it doesn't block list/create; object-level check
guards retrieve/cancel/checkout. (Belt-and-suspenders with the owner-scoped queryset.)

### `apps/booking/api/viewsets.py`
`BookingViewSet(CreateModelMixin, ListModelMixin, RetrieveModelMixin, GenericViewSet)`:
- `permission_classes = [IsAuthenticated, IsBookingOwnerOrStaff]`.
- `get_queryset()`:
  ```python
  user = cast("User", self.request.user)
  qs = Booking.objects.select_related("screening__movie", "screening__hall")
  if not user.is_staff:
      qs = qs.filter(user=user)
  return qs.order_by("-created_at")
  ```
  (`cast` per dev pitfall #12; `TYPE_CHECKING` import of `User`.)
- `get_serializer_class()` → `BookingCreateSerializer` if `self.action == "create"`,
  else `BookingSerializer`.
- **`create(self, request)`** (`@extend_schema(responses=BookingCreateResponseSerializer)`):
  ```
  in_ser = BookingCreateSerializer(data=request.data); in_ser.is_valid(raise_exception=True)
  try:
      booking = create_booking(user=request.user,
                               screening=in_ser.validated_data["screening"],
                               seats_count=in_ser.validated_data["seats_count"])
  except NotEnoughSeatsError as exc:
      return Response({"detail": str(exc)}, status=409)
  except ScreeningInPastError as exc:
      return Response({"detail": str(exc)}, status=400)
  data = {"booking": BookingSerializer(booking).data, "checkout_url": None}
  try:
      data["checkout_url"] = start_checkout(booking=booking)
  except stripe.StripeError:
      data["detail"] = "Payment temporarily unavailable; retry via the checkout action."
  return Response(data, status=201)
  ```
- **`cancel`** (`@action(detail=True, methods=["post"])`,
  `@extend_schema(responses=BookingSerializer)`): `booking = self.get_object()` →
  `cancel_booking(booking=booking)`; `BookingNotCancellableError` → 409;
  `RefundError`/`stripe.StripeError` → 502; success → `Response(BookingSerializer(updated).data)`.
- **`checkout`** (`@action(detail=True, methods=["post"])`,
  `@extend_schema(responses=CheckoutResponseSerializer)`): `booking = self.get_object()`;
  if `booking.status != PENDING` → 409 `{detail}`; else `start_checkout`
  (`stripe.StripeError` → 502) → `Response({"checkout_url": url, "session_id":
  booking.stripe_session_id})`.

`self.get_object()` uses the owner-scoped queryset, so a non-owner hits `404` before the
service runs.

### `apps/booking/api/urls.py` + `settings/api_urls.py`
```python
from rest_framework.routers import SimpleRouter
from apps.booking.api.viewsets import BookingViewSet

router = SimpleRouter()
router.register("bookings", BookingViewSet, basename="booking")
urlpatterns = router.urls
```
`settings/api_urls.py`: add `path("", include("apps.booking.api.urls"))` (alongside the
cinema include). Endpoints: `/api/v1/bookings/`, `/bookings/<id>/`, `/bookings/<id>/cancel/`,
`/bookings/<id>/checkout/`.

## 5. Reuse (no duplication)

| Service | Used by | Errors mapped |
|---------|---------|---------------|
| `create_booking(*, user, screening, seats_count)` | create | `NotEnoughSeatsError`→409, `ScreeningInPastError`→400 |
| `start_checkout(*, booking)` | create, checkout | `stripe.StripeError`→ (create: 201+null) / (checkout: 502) |
| `cancel_booking(*, booking)` | cancel | `BookingNotCancellableError`→409, `RefundError`→502 |

`seats_count` range [1,10] is the serializer's job (`create_booking` docstring: "caller
owns seats_count range"); availability + past are re-checked authoritatively under the
service's `select_for_update` lock.

## 6. OpenAPI

`@extend_schema` on `create`/`cancel`/`checkout` documents the custom response bodies
(`BookingCreateResponseSerializer`, `BookingSerializer`, `CheckoutResponseSerializer`),
keeping drf-spectacular warning-free (US-35 enforces strict).

## 7. Testing (`tests/booking/test_api.py`)

`api_client`/`auth_client` + `mock_checkout_session`/`mock_refund` (conftest) + factories.
`@pytest.mark.stripe` on Stripe-touching tests.
- **list**: owner sees only own; staff sees all; anon → 401; `-created_at` order.
- **create**: valid → 201 `{booking PENDING, checkout_url}`; `seats_count` 0/11 → 400;
  sold-out → 409 (book the hall to capacity first); past screening → 400; Stripe down
  (`mock_checkout_session.side_effect = stripe.APIConnectionError(...)`) → 201 +
  `checkout_url is None` + `detail`.
- **retrieve**: owner 200 / non-owner 404 / staff 200 / anon 401.
- **cancel**: owner PENDING → 200 CANCELLED; not cancellable → 409; CONFIRMED with
  payment intent → refund (`mock_refund`) → 200 + `refund_id` set; non-owner 404.
- **checkout**: PENDING → 200 `{checkout_url, session_id}`; non-PENDING (e.g. CANCELLED)
  → 409; Stripe down → 502.

## 8. Coverage / migration

New `apps/booking/api/` is real code → covered by §7 tests; threshold ≥ 80% maintained.
**No migration** (no model changes).

## 9. Risks

1. **`request.user` typing** — `cast("User", self.request.user)` in `get_queryset`
   (dev pitfall #12); `TYPE_CHECKING` import avoids a runtime/circular import.
2. **Owner-scoping vs object permission** — owner-scoped queryset already yields 404 for
   non-owners; `IsBookingOwnerOrStaff` is defense-in-depth and enables the staff path
   (staff queryset = all, object perm passes via `is_staff`).
3. **Error mapping completeness** — every `BookingError` subclass has an explicit branch;
   `RefundError` is a `BookingError` subclass, so order the `except` clauses so it maps to
   502 (catch `RefundError`/`stripe.StripeError` before a bare `BookingError`, or map each
   type explicitly).
4. **Create is non-atomic with checkout (by design)** — `create_booking` commits before
   `start_checkout`; a Stripe failure leaves a retryable PENDING booking (201 + null url),
   matching the web. Tested.
5. **Stripe mocking path** — `start_checkout` → `create_checkout_session` →
   `stripe.checkout.Session.create`; the existing `mock_checkout_session` fixture patches
   `apps.payments.services.stripe.checkout.Session.create`, so it covers the API path too.

## 10. Build order (for the plan)

1. Serializers + permission.
2. ViewSet (create + error mapping) + `urls.py` + mount; list/create/retrieve tests.
3. `cancel` + `checkout` actions + their tests.
4. Quality gate: pytest (cov ≥ 80%), ruff, mypy.

The first branch commit folds in the `backlog.md` board update (US-31 → Done, US-32 → In
Progress) made at US-32 start.
