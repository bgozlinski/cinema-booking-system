# US-32 — Booking API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose owner-scoped booking list/create/retrieve + cancel/checkout under `/api/v1/bookings/`, reusing the M3 booking services (no business logic duplicated).

**Architecture:** New `apps/booking/api/{serializers,permissions,viewsets,urls}.py`. A mixin `GenericViewSet` (List/Retrieve/Create — no update/destroy) with `cancel`/`checkout` `@action`s calls `create_booking`/`cancel_booking`/`start_checkout`; typed `BookingError` subclasses map to 409/400/502. Owner-scoped queryset (staff sees all) → non-owner gets 404.

**Tech Stack:** DRF 3.17 (mixins, `@action`, `SimpleRouter`), drf-spectacular; pytest / pytest-django; Stripe mocked via existing conftest fixtures.

---

## Role division

- **User** writes all app files (`apps/booking/api/*.py`, `settings/api_urls.py`) and runs all `git`/`pytest`. Claude proposes exact content.
- **Claude** writes all test code (`tests/**`).

Steps tagged **[User]** / **[Claude]**. Files that grow across tasks are shown **complete** each time (paste-safe).

## Spec

`docs/superpowers/specs/2026-05-24-us32-booking-api-design.md`

## File structure

| File | Action | Responsibility | Author |
|------|--------|----------------|--------|
| `apps/booking/api/__init__.py` | create | package marker | User |
| `apps/booking/api/serializers.py` | create (grows) | Booking + create/response serializers | User |
| `apps/booking/api/permissions.py` | create | `IsBookingOwnerOrStaff` | User |
| `apps/booking/api/viewsets.py` | create (grows) | `BookingViewSet` | User |
| `apps/booking/api/urls.py` | create | `SimpleRouter` registration | User |
| `settings/api_urls.py` | modify | mount booking API | User |
| `tests/booking/test_api.py` | create (grows) | endpoint tests | Claude |

## TDD strategy

Capability slices: read (Task 1) → create (Task 2) → actions (Task 3). The viewset grows by adding mixins/actions, so create tests get `405` and action tests get `404` until wired (clean reds). Commit on green per task; the first commit folds in the `backlog.md` board update.

---

### Task 1: Read side (list + retrieve)

**Files:**
- Create: `apps/booking/api/__init__.py`, `apps/booking/api/serializers.py`, `apps/booking/api/permissions.py`, `apps/booking/api/viewsets.py`, `apps/booking/api/urls.py`
- Modify: `settings/api_urls.py`
- Test: `tests/booking/test_api.py`

- [ ] **Step 1 [Claude]: Write the failing list/retrieve tests**

Create `tests/booking/test_api.py`:
```python
import pytest

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory

pytestmark = pytest.mark.django_db

BOOKINGS_URL = "/api/v1/bookings/"


class TestBookingList:
    def test_owner_sees_only_own(self, auth_client):
        owner = UserFactory()
        BookingFactory(user=owner)
        BookingFactory()  # someone else's
        resp = auth_client(owner).get(BOOKINGS_URL)
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_staff_sees_all(self, auth_client):
        BookingFactory()
        BookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).get(BOOKINGS_URL)
        assert resp.data["count"] == 2

    def test_anon_unauthorized(self, api_client):
        assert api_client.get(BOOKINGS_URL).status_code == 401


class TestBookingRetrieve:
    def test_owner_can_retrieve(self, auth_client):
        owner = UserFactory()
        booking = BookingFactory(user=owner)
        resp = auth_client(owner).get(f"{BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 200
        assert resp.data["id"] == booking.id
        assert resp.data["screening"]["movie"]["title"] == booking.screening.movie.title
        assert "total_price" in resp.data

    def test_non_owner_gets_404(self, auth_client):
        booking = BookingFactory()
        resp = auth_client(UserFactory()).get(f"{BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 404

    def test_staff_can_retrieve(self, auth_client):
        booking = BookingFactory()
        resp = auth_client(UserFactory(is_staff=True)).get(f"{BOOKINGS_URL}{booking.id}/")
        assert resp.status_code == 200
```

- [ ] **Step 2 [User]: Run to confirm FAIL**

Run: `poetry run pytest tests/booking/test_api.py -q --no-cov`
Expected: FAIL — `404` (no `/api/v1/bookings/`).

- [ ] **Step 3 [User]: Create `apps/booking/api/__init__.py`** (empty).

- [ ] **Step 4 [User]: Create `apps/booking/api/serializers.py`**

```python
from rest_framework import serializers

from apps.booking.models import Booking
from apps.cinema.api.serializers import HallSerializer, MovieMiniSerializer
from apps.cinema.models import Screening


class BookingScreeningSerializer(serializers.ModelSerializer):
    movie = MovieMiniSerializer(read_only=True)
    hall = HallSerializer(read_only=True)

    class Meta:
        model = Screening
        fields = ("id", "movie", "hall", "start_time", "price")


class BookingSerializer(serializers.ModelSerializer):
    screening = BookingScreeningSerializer(read_only=True)
    total_price = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "screening",
            "seats_count",
            "status",
            "total_price",
            "created_at",
            "expires_at",
        )
        read_only_fields = fields
```

- [ ] **Step 5 [User]: Create `apps/booking/api/permissions.py`**

```python
from rest_framework.permissions import BasePermission


class IsBookingOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        return obj.user == request.user or request.user.is_staff
```

- [ ] **Step 6 [User]: Create `apps/booking/api/viewsets.py` (read side)**

```python
from typing import TYPE_CHECKING, cast

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.booking.api.permissions import IsBookingOwnerOrStaff
from apps.booking.api.serializers import BookingSerializer
from apps.booking.models import Booking

if TYPE_CHECKING:
    from apps.accounts.models import User


class BookingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsBookingOwnerOrStaff]  # noqa: RUF012
    serializer_class = BookingSerializer

    def get_queryset(self):
        user = cast("User", self.request.user)
        qs = Booking.objects.select_related("screening__movie", "screening__hall")
        if not user.is_staff:
            qs = qs.filter(user=user)
        return qs.order_by("-created_at")
```

- [ ] **Step 7 [User]: Create `apps/booking/api/urls.py`**

```python
from rest_framework.routers import SimpleRouter

from apps.booking.api.viewsets import BookingViewSet

router = SimpleRouter()
router.register("bookings", BookingViewSet, basename="booking")

urlpatterns = router.urls
```

- [ ] **Step 8 [User]: Mount in `settings/api_urls.py`**

Add the booking include after the cinema one:
```python
    path("", include("apps.booking.api.urls")),
```
Full file:
```python
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("auth/", include("apps.accounts.api.urls")),
    path("", include("apps.cinema.api.urls")),
    path("", include("apps.booking.api.urls")),
]
```

- [ ] **Step 9 [User]: Run to confirm PASS**

Run: `poetry run pytest tests/booking/test_api.py -q --no-cov`
Expected: PASS (list + retrieve).

- [ ] **Step 10 [User]: Commit (folds in the backlog board update)**

```bash
git add apps/booking/api/ settings/api_urls.py tests/booking/test_api.py .Claude/backlog.md
git commit -m "feat(FR-18): booking API list + retrieve (owner-scoped) (US-32)"
```

---

### Task 2: Create (POST /bookings/)

**Files:**
- Modify: `apps/booking/api/serializers.py`, `apps/booking/api/viewsets.py`
- Test: `tests/booking/test_api.py`

- [ ] **Step 1 [Claude]: Append the create tests**

Add to `tests/booking/test_api.py` (extend the imports at the top to):
```python
from datetime import timedelta

import pytest
import stripe
from django.utils import timezone

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import HallFactory, ScreeningFactory
```
and append:
```python
FAKE_CHECKOUT_URL = "https://checkout.stripe.test/c/cs_test_123"


class TestBookingCreate:
    @pytest.mark.stripe
    def test_create_valid(self, auth_client, mock_checkout_session):
        screening = ScreeningFactory()
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 2}, format="json"
        )
        assert resp.status_code == 201
        assert resp.data["booking"]["status"] == "PENDING"
        assert resp.data["booking"]["seats_count"] == 2
        assert resp.data["checkout_url"] == FAKE_CHECKOUT_URL

    def test_seats_out_of_range(self, auth_client):
        screening = ScreeningFactory()
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 11}, format="json"
        )
        assert resp.status_code == 400
        assert "seats_count" in resp.data

    @pytest.mark.stripe
    def test_sold_out_conflict(self, auth_client, mock_checkout_session):
        hall = HallFactory(capacity=2)
        screening = ScreeningFactory(hall=hall)
        ConfirmedBookingFactory(screening=screening, seats_count=2)  # fills the hall
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 1}, format="json"
        )
        assert resp.status_code == 409

    @pytest.mark.stripe
    def test_past_screening_400(self, auth_client, mock_checkout_session):
        screening = ScreeningFactory(start_time=timezone.now() - timedelta(hours=1))
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 1}, format="json"
        )
        assert resp.status_code == 400

    @pytest.mark.stripe
    def test_stripe_down_returns_201_null_checkout(self, auth_client, mock_checkout_session):
        mock_checkout_session.side_effect = stripe.APIConnectionError("boom")
        screening = ScreeningFactory()
        resp = auth_client(UserFactory()).post(
            BOOKINGS_URL, {"screening_id": screening.id, "seats_count": 1}, format="json"
        )
        assert resp.status_code == 201
        assert resp.data["checkout_url"] is None
        assert "detail" in resp.data
```

- [ ] **Step 2 [User]: Run create tests to confirm FAIL**

Run: `poetry run pytest tests/booking/test_api.py::TestBookingCreate -q --no-cov`
Expected: FAIL — `405` (no create handler yet) for most; `test_seats_out_of_range` may also be 405.

- [ ] **Step 3 [User]: Replace `apps/booking/api/serializers.py` (adds create + response serializers)**

```python
from rest_framework import serializers

from apps.booking.models import Booking
from apps.cinema.api.serializers import HallSerializer, MovieMiniSerializer
from apps.cinema.models import Screening


class BookingScreeningSerializer(serializers.ModelSerializer):
    movie = MovieMiniSerializer(read_only=True)
    hall = HallSerializer(read_only=True)

    class Meta:
        model = Screening
        fields = ("id", "movie", "hall", "start_time", "price")


class BookingSerializer(serializers.ModelSerializer):
    screening = BookingScreeningSerializer(read_only=True)
    total_price = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "screening",
            "seats_count",
            "status",
            "total_price",
            "created_at",
            "expires_at",
        )
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    screening_id = serializers.PrimaryKeyRelatedField(
        queryset=Screening.objects.all(), source="screening"
    )
    seats_count = serializers.IntegerField(min_value=1, max_value=10)


class BookingCreateResponseSerializer(serializers.Serializer):
    booking = BookingSerializer()
    checkout_url = serializers.CharField(allow_null=True)
    detail = serializers.CharField(required=False)
```

- [ ] **Step 4 [User]: Replace `apps/booking/api/viewsets.py` (adds Create + error mapping)**

```python
from typing import TYPE_CHECKING, Any, cast

import stripe
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.booking.api.permissions import IsBookingOwnerOrStaff
from apps.booking.api.serializers import (
    BookingCreateResponseSerializer,
    BookingCreateSerializer,
    BookingSerializer,
)
from apps.booking.models import Booking
from apps.booking.services import (
    NotEnoughSeatsError,
    ScreeningInPastError,
    create_booking,
    start_checkout,
)

if TYPE_CHECKING:
    from apps.accounts.models import User


class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsBookingOwnerOrStaff]  # noqa: RUF012

    def get_queryset(self):
        user = cast("User", self.request.user)
        qs = Booking.objects.select_related("screening__movie", "screening__hall")
        if not user.is_staff:
            qs = qs.filter(user=user)
        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        return BookingSerializer

    @extend_schema(responses=BookingCreateResponseSerializer)
    def create(self, request, *args, **kwargs):
        in_ser = BookingCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        try:
            booking = create_booking(
                user=request.user,
                screening=in_ser.validated_data["screening"],
                seats_count=in_ser.validated_data["seats_count"],
            )
        except NotEnoughSeatsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ScreeningInPastError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data: dict[str, Any] = {"booking": BookingSerializer(booking).data, "checkout_url": None}
        try:
            data["checkout_url"] = start_checkout(booking=booking)
        except stripe.StripeError:
            data["detail"] = "Payment temporarily unavailable; retry via the checkout action."
        return Response(data, status=status.HTTP_201_CREATED)
```

- [ ] **Step 5 [User]: Run create tests to confirm PASS**

Run: `poetry run pytest tests/booking/test_api.py -q --no-cov`
Expected: PASS (read + create).

- [ ] **Step 6 [User]: Commit**

```bash
git add apps/booking/api/ tests/booking/test_api.py
git commit -m "feat(FR-18): booking API create (+ Stripe checkout, error mapping) (US-32)"
```

---

### Task 3: Actions (cancel + checkout)

**Files:**
- Modify: `apps/booking/api/serializers.py`, `apps/booking/api/viewsets.py`
- Test: `tests/booking/test_api.py`

- [ ] **Step 1 [Claude]: Append the cancel + checkout tests**

Add to `tests/booking/test_api.py` (extend the booking-models import + append classes):
```python
from apps.booking.models import BookingStatus


class TestBookingCancel:
    def test_owner_cancels_pending(self, auth_client):
        owner = UserFactory()
        booking = BookingFactory(user=owner)  # PENDING, future screening
        resp = auth_client(owner).post(f"{BOOKINGS_URL}{booking.id}/cancel/")
        assert resp.status_code == 200
        assert resp.data["status"] == "CANCELLED"

    def test_not_cancellable_conflict(self, auth_client):
        owner = UserFactory()
        booking = BookingFactory(user=owner, status=BookingStatus.CANCELLED, expires_at=None)
        resp = auth_client(owner).post(f"{BOOKINGS_URL}{booking.id}/cancel/")
        assert resp.status_code == 409

    def test_non_owner_404(self, auth_client):
        booking = BookingFactory()
        resp = auth_client(UserFactory()).post(f"{BOOKINGS_URL}{booking.id}/cancel/")
        assert resp.status_code == 404

    @pytest.mark.stripe
    def test_confirmed_cancel_refunds(self, auth_client, mock_refund):
        owner = UserFactory()
        booking = ConfirmedBookingFactory(user=owner)  # CONFIRMED + payment intent
        resp = auth_client(owner).post(f"{BOOKINGS_URL}{booking.id}/cancel/")
        assert resp.status_code == 200
        assert resp.data["status"] == "CANCELLED"
        booking.refresh_from_db()
        assert booking.refund_id == "re_test_123"


class TestBookingCheckout:
    @pytest.mark.stripe
    def test_pending_checkout(self, auth_client, mock_checkout_session):
        owner = UserFactory()
        booking = BookingFactory(user=owner)  # PENDING
        resp = auth_client(owner).post(f"{BOOKINGS_URL}{booking.id}/checkout/")
        assert resp.status_code == 200
        assert resp.data["checkout_url"] == FAKE_CHECKOUT_URL
        assert resp.data["session_id"] == "cs_test_123"

    def test_non_pending_conflict(self, auth_client):
        owner = UserFactory()
        booking = BookingFactory(user=owner, status=BookingStatus.CANCELLED, expires_at=None)
        resp = auth_client(owner).post(f"{BOOKINGS_URL}{booking.id}/checkout/")
        assert resp.status_code == 409

    @pytest.mark.stripe
    def test_stripe_down_502(self, auth_client, mock_checkout_session):
        mock_checkout_session.side_effect = stripe.APIConnectionError("boom")
        owner = UserFactory()
        booking = BookingFactory(user=owner)
        resp = auth_client(owner).post(f"{BOOKINGS_URL}{booking.id}/checkout/")
        assert resp.status_code == 502
```

- [ ] **Step 2 [User]: Run action tests to confirm FAIL**

Run: `poetry run pytest tests/booking/test_api.py::TestBookingCancel tests/booking/test_api.py::TestBookingCheckout -q --no-cov`
Expected: FAIL — `404` (no `cancel`/`checkout` routes yet).

- [ ] **Step 3 [User]: Replace `apps/booking/api/serializers.py` (adds CheckoutResponseSerializer)**

Append this class to the end of the file (after `BookingCreateResponseSerializer`):
```python


class CheckoutResponseSerializer(serializers.Serializer):
    checkout_url = serializers.CharField()
    session_id = serializers.CharField()
```

- [ ] **Step 4 [User]: Replace `apps/booking/api/viewsets.py` (adds cancel + checkout actions)**

```python
from typing import TYPE_CHECKING, Any, cast

import stripe
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.booking.api.permissions import IsBookingOwnerOrStaff
from apps.booking.api.serializers import (
    BookingCreateResponseSerializer,
    BookingCreateSerializer,
    BookingSerializer,
    CheckoutResponseSerializer,
)
from apps.booking.models import Booking, BookingStatus
from apps.booking.services import (
    BookingNotCancellableError,
    NotEnoughSeatsError,
    RefundError,
    ScreeningInPastError,
    cancel_booking,
    create_booking,
    start_checkout,
)

if TYPE_CHECKING:
    from apps.accounts.models import User


class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsBookingOwnerOrStaff]  # noqa: RUF012

    def get_queryset(self):
        user = cast("User", self.request.user)
        qs = Booking.objects.select_related("screening__movie", "screening__hall")
        if not user.is_staff:
            qs = qs.filter(user=user)
        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        return BookingSerializer

    @extend_schema(responses=BookingCreateResponseSerializer)
    def create(self, request, *args, **kwargs):
        in_ser = BookingCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        try:
            booking = create_booking(
                user=request.user,
                screening=in_ser.validated_data["screening"],
                seats_count=in_ser.validated_data["seats_count"],
            )
        except NotEnoughSeatsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ScreeningInPastError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data: dict[str, Any] = {"booking": BookingSerializer(booking).data, "checkout_url": None}
        try:
            data["checkout_url"] = start_checkout(booking=booking)
        except stripe.StripeError:
            data["detail"] = "Payment temporarily unavailable; retry via the checkout action."
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=BookingSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        try:
            updated = cancel_booking(booking=booking)
        except BookingNotCancellableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except (RefundError, stripe.StripeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(BookingSerializer(updated).data)

    @extend_schema(request=None, responses=CheckoutResponseSerializer)
    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        booking = self.get_object()
        if booking.status != BookingStatus.PENDING:
            return Response(
                {"detail": "This booking can no longer be paid."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            checkout_url = start_checkout(booking=booking)
        except stripe.StripeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"checkout_url": checkout_url, "session_id": booking.stripe_session_id})
```

- [ ] **Step 5 [User]: Run the full booking API file to confirm PASS**

Run: `poetry run pytest tests/booking/test_api.py -q --no-cov`
Expected: PASS (read + create + cancel + checkout).

- [ ] **Step 6 [User]: Commit**

```bash
git add apps/booking/api/ tests/booking/test_api.py
git commit -m "feat(FR-18): booking API cancel + checkout actions (US-32)"
```

---

### Task 4: Quality gate

- [ ] **Step 1 [User]: Full suite with coverage**

Run: `poetry run pytest`
Expected: PASS, coverage ≥ 80%.

- [ ] **Step 2 [User]: Lint + format**

Run: `poetry run ruff check . && poetry run ruff format --check .`
Expected: clean (if format flags any api file, run `poetry run ruff format .` then re-check).

- [ ] **Step 3 [User]: Type-check**

Run: `poetry run mypy .`
Expected: clean. Watch: `cast("User", ...)` in `get_queryset`; `create`/`cancel`/`checkout` return `Response`; `data: dict[str, Any]`.

- [ ] **Step 4 [User]: Manual smoke (optional)**

`runserver`, then `POST /api/v1/auth/token/` → bearer → `POST /api/v1/bookings/ {screening_id, seats_count}` → 201 with `checkout_url`; `POST /api/v1/bookings/<id>/cancel/` → CANCELLED.

---

## Out of scope

Checkout/webhook formalization (US-33) · admin write API (US-34) · `bearerAuth` rename + strict CI (US-35) · throttle 429 tests (US-36).

## Test plan summary

- `tests/booking/test_api.py`: list (owner/staff/anon), retrieve (owner/non-owner-404/staff), create (valid 201 + checkout_url, seats range 400, sold-out 409, past 400, Stripe-down 201+null), cancel (PENDING 200, not-cancellable 409, non-owner 404, CONFIRMED refund 200), checkout (PENDING 200, non-PENDING 409, Stripe-down 502).
- Stripe mocked via `mock_checkout_session`/`mock_refund`; `@pytest.mark.stripe` on those tests.
- Coverage ≥ 80%; no migration.
