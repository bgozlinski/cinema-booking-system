from django.contrib import admin

from apps.payments.models import StripeEvent


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    """StripeEvent is an audit log — all fields read-only."""

    list_display = ("event_id", "event_type", "received_at", "processed_at")
    list_filter = ("event_type",)
    search_fields = ("event_id",)
    readonly_fields = ("event_id", "event_type", "payload", "received_at", "processed_at")
