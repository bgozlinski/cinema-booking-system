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
