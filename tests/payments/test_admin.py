"""Tests for apps.payments admin registration."""

import pytest
from django.contrib import admin

from apps.payments.models import StripeEvent

pytestmark = pytest.mark.django_db


class TestStripeEventAdminRegistration:
    def test_stripe_event_is_registered(self):
        assert admin.site.is_registered(StripeEvent)

    def test_stripe_event_admin_list_display_columns(self):
        ma = admin.site._registry[StripeEvent]
        assert ma.list_display == ("event_id", "event_type", "received_at", "processed_at")

    def test_stripe_event_admin_all_fields_readonly(self):
        ma = admin.site._registry[StripeEvent]
        # StripeEvent is an audit log — all fields read-only via admin.
        assert set(ma.readonly_fields) == {
            "event_id",
            "event_type",
            "payload",
            "received_at",
            "processed_at",
        }
