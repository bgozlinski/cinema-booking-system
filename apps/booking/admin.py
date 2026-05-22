from django.contrib import admin

from apps.booking.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Minimal registration. Full refactor (annotate, status badges, screening inline)
    deferred to US-28."""

    list_display = ("id", "user", "screening", "seats_count", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "screening__movie__title")
    readonly_fields = ("created_at",)
