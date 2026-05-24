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
