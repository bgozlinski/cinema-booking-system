"""Tests for the expire_pending_bookings command (US-26 / FR-23)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory

pytestmark = pytest.mark.django_db


def _expired_pending(**kwargs):
    return BookingFactory(expires_at=timezone.now() - timedelta(minutes=1), **kwargs)


def _run(*args):
    out = StringIO()
    call_command("expire_pending_bookings", *args, stdout=out)
    return out.getvalue()


class TestExpirePendingBookings:
    def test_cancels_expired_pending(self):
        booking = _expired_pending()
        _run()
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_keeps_expires_at_for_audit(self):
        booking = _expired_pending()
        original = booking.expires_at
        _run()
        booking.refresh_from_db()
        assert booking.expires_at == original  # NOT cleared (FR-23 audit)

    def test_leaves_active_pending(self):
        booking = BookingFactory()  # expires +15min (future)
        _run()
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING

    def test_leaves_confirmed(self):
        booking = ConfirmedBookingFactory()
        _run()
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_idempotent_second_run_changes_nothing(self):
        _expired_pending()
        _run()
        _run()  # second run must not error or re-process
        assert not Booking.objects.filter(
            status=BookingStatus.PENDING, expires_at__lt=timezone.now()
        ).exists()

    def test_dry_run_makes_no_changes(self):
        booking = _expired_pending()
        output = _run("--dry-run")
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING  # unchanged
        assert "dry-run" in output

    def test_reports_count_and_freed_seats(self):
        _expired_pending(seats_count=3)
        _expired_pending(seats_count=2)
        output = _run()
        assert "2" in output  # 2 bookings cancelled
        assert "5" in output  # 5 freed seats
