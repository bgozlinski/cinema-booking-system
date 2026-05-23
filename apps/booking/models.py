from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class BookingStatus(models.TextChoices):
    PENDING = "PENDING", _("Oczekująca")
    CONFIRMED = "CONFIRMED", _("Potwierdzona")
    CANCELLED = "CANCELLED", _("Anulowana")


class Booking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name=_("user"),
    )
    screening = models.ForeignKey(
        "cinema.Screening",
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name=_("screening"),
    )
    seats_count = models.PositiveIntegerField(
        _("seats count"),
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    status = models.CharField(
        _("status"),
        max_length=12,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    stripe_session_id = models.CharField(
        _("Stripe session ID"), max_length=255, blank=True, default=""
    )
    stripe_payment_intent_id = models.CharField(
        _("Stripe payment intent ID"), max_length=255, blank=True, default=""
    )
    refund_id = models.CharField(_("refund ID"), max_length=255, blank=True, default="")
    refunded_at = models.DateTimeField(_("refunded at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("booking")
        verbose_name_plural = _("bookings")
        ordering = ("-created_at",)
        indexes = [  # noqa: RUF012
            models.Index(fields=["status", "expires_at"], name="booking_status_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"Booking #{self.pk} — {self.screening.movie.title}"

    @property
    def total_price(self) -> Decimal:
        return self.seats_count * self.screening.price

    def can_be_cancelled(self) -> bool:
        """True when this booking may still be cancelled by its owner (FR-10).

        US-23 scope: PENDING bookings up to 1h before the screening. US-27 will
        broaden this to CONFIRMED (which additionally requires a Stripe refund).
        """
        return (
            self.status == BookingStatus.PENDING
            and self.screening.start_time > timezone.now() + timedelta(hours=1)
        )
