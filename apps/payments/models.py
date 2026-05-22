from django.db import models
from django.utils.translation import gettext_lazy as _


class StripeEvent(models.Model):
    """Idempotency log for Stripe webhook events.

    Stripe retries webhooks on 5xx responses. This table guarantees that the same
    event_id never triggers a domain state change twice. Webhook handler (US-25)
    uses get_or_create(event_id=...) — duplicates return 200 OK without processing.
    """

    event_id = models.CharField(
        _("Stripe event ID"),
        max_length=255,
        unique=True,
    )
    event_type = models.CharField(_("event type"), max_length=100)
    payload = models.JSONField(_("payload"))
    received_at = models.DateTimeField(_("received at"), auto_now_add=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Stripe event")
        verbose_name_plural = _("Stripe events")
        ordering = ("-received_at",)

    def __str__(self) -> str:
        return f"{self.event_type} ({self.event_id})"
