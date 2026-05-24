from django.contrib import admin

from apps.booking.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "screening",
        "seats_count",
        "status",
        "total_price_display",
        "created_at",
    )
    list_filter = ("status", "screening__movie", "created_at")
    list_editable = ("status",)
    search_fields = ("user__email", "screening__movie__title")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "screening__movie")

    @admin.display(description="total price")
    def total_price_display(self, obj):
        return obj.total_price
