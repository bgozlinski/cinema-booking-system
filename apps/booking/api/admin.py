import stripe
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.booking.models import Booking
from apps.booking.services import BookingNotRefundableError, RefundError, refund_booking


class AdminBookingSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "user",
            "screening",
            "seats_count",
            "status",
            "total_price",
            "created_at",
            "expires_at",
            "refund_id",
            "refunded_at",
        )
        read_only_fields = (
            "id",
            "user",
            "screening",
            "seats_count",
            "total_price",
            "created_at",
            "expires_at",
            "refund_id",
            "refunded_at",
        )


class AdminBookingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAdminUser]  # noqa: RUF012
    queryset = Booking.objects.select_related("user", "screening__movie")
    serializer_class = AdminBookingSerializer

    @extend_schema(request=None, responses=AdminBookingSerializer)
    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        booking = self.get_object()
        try:
            updated = refund_booking(booking=booking)
        except BookingNotRefundableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except (RefundError, stripe.StripeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(AdminBookingSerializer(updated).data)
