from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus


class Command(BaseCommand):
    help = "Cancel PENDING bookings whose payment window (expires_at) has lapsed (FR-23)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cancelled without saving.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Booking.objects.filter(status=BookingStatus.PENDING, expires_at__lt=now)
        stats = expired.aggregate(count=Count("id"), seats=Sum("seats_count"))
        count = stats["count"]
        freed = stats["seats"] or 0

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {count} rezerwacji do anulowania (zwolniłoby {freed} miejsc)."
            )
            return

        updated = expired.update(status=BookingStatus.CANCELLED)
        self.stdout.write(
            self.style.SUCCESS(f"Anulowano {updated} rezerwacji (zwolniono {freed} miejsc).")
        )
