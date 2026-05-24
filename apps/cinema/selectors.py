from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.booking.models import BookingStatus


def annotate_booked_count(qs):
    """Annotate `_annotated_booked_count` on a Screening queryset.

    Sums seats from CONFIRMED + active-PENDING bookings so callers reading
    `Screening.available_seats_count()` / `is_available()` avoid an N+1 (the
    method short-circuits on the annotation). Shared by the web views and the API.
    Call per-request — it captures `timezone.now()`.
    """
    now = timezone.now()
    return qs.annotate(
        _annotated_booked_count=Coalesce(
            Sum(
                "bookings__seats_count",
                filter=(
                    Q(bookings__status=BookingStatus.CONFIRMED)
                    | Q(
                        bookings__status=BookingStatus.PENDING,
                        bookings__expires_at__gt=now,
                    )
                ),
            ),
            0,
        )
    )
