from typing import TYPE_CHECKING, Any, cast

import stripe
from drf_spectacular.utils import OpenApiExample, extend_schema
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
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        user = cast("User", self.request.user)
        qs = Booking.objects.select_related("screening__movie", "screening__hall")
        if not user.is_staff:
            qs = qs.filter(user=user)
        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        return BookingSerializer

    @extend_schema(
        summary="Create a booking and start Stripe checkout",
        responses=BookingCreateResponseSerializer,
        examples=[
            OpenApiExample(
                "Created",
                value={
                    "booking": {"id": 1, "status": "PENDING", "seats_count": 2},
                    "checkout_url": "https://checkout.stripe.com/c/cs_test_123",
                },
                response_only=True,
            )
        ],
    )
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

    @extend_schema(
        summary="Cancel a booking (refunds if CONFIRMED)", request=None, responses=BookingSerializer
    )
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

    @extend_schema(
        summary="Create a fresh Stripe checkout session for a PENDING booking",
        request=None,
        responses=CheckoutResponseSerializer,
    )
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
