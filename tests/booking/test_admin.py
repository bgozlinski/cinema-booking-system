"""Tests for apps.booking admin registration."""

import pytest
from django.contrib import admin

from apps.booking.models import Booking
from tests.booking.factories import BookingFactory

pytestmark = pytest.mark.django_db


class TestBookingAdminRegistration:
    def test_booking_is_registered(self):
        assert admin.site.is_registered(Booking)

    def test_booking_admin_list_display_columns(self):
        ma = admin.site._registry[Booking]
        assert ma.list_display == (
            "id",
            "user",
            "screening",
            "seats_count",
            "status",
            "total_price_display",
            "created_at",
        )

    def test_booking_admin_search_fields(self):
        ma = admin.site._registry[Booking]
        assert ma.search_fields == ("user__email", "screening__movie__title")

    def test_booking_admin_list_filter(self):
        ma = admin.site._registry[Booking]
        assert ma.list_filter == ("status", "screening__movie", "created_at")

    def test_booking_admin_status_list_editable(self):
        ma = admin.site._registry[Booking]
        assert ma.list_editable == ("status",)

    def test_booking_admin_created_at_readonly(self):
        ma = admin.site._registry[Booking]
        assert "created_at" in ma.readonly_fields

    def test_total_price_display_returns_total_price(self):
        booking = BookingFactory(seats_count=2)
        ma = admin.site._registry[Booking]
        assert ma.total_price_display(booking) == booking.total_price
