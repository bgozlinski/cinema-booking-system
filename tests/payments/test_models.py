"""Tests for apps.payments.StripeEvent model."""

import pytest
from django.db import IntegrityError

from apps.payments.models import StripeEvent
from tests.payments.factories import StripeEventFactory

pytestmark = pytest.mark.django_db


class TestStripeEventCreation:
    def test_creation_with_required_fields(self):
        event = StripeEvent.objects.create(
            event_id="evt_unit_1",
            event_type="checkout.session.completed",
            payload={"id": "evt_unit_1", "type": "checkout.session.completed"},
        )
        assert event.pk is not None
        assert event.event_id == "evt_unit_1"
        assert event.event_type == "checkout.session.completed"
        assert event.payload["id"] == "evt_unit_1"

    def test_received_at_auto_set(self):
        event = StripeEventFactory()
        assert event.received_at is not None

    def test_processed_at_defaults_none(self):
        event = StripeEventFactory()
        assert event.processed_at is None

    def test_payload_round_trips_dict(self):
        payload = {"nested": {"key": [1, 2, 3]}, "flag": True}
        event = StripeEventFactory(payload=payload)
        event.refresh_from_db()
        assert event.payload == payload


class TestStripeEventConstraints:
    def test_event_id_unique_constraint_raises_integrity_error(self):
        StripeEventFactory(event_id="evt_dup")
        with pytest.raises(IntegrityError):
            StripeEventFactory(event_id="evt_dup")


class TestStripeEventMeta:
    def test_str_includes_type_and_id(self):
        event = StripeEventFactory(event_id="evt_str_test", event_type="checkout.session.completed")
        assert str(event) == "checkout.session.completed (evt_str_test)"

    def test_default_ordering_newest_first(self):
        first = StripeEventFactory()
        second = StripeEventFactory()
        events = list(StripeEvent.objects.all())
        assert events[0] == second
        assert events[1] == first
