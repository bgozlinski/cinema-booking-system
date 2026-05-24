"""Tests for process_webhook_event dispatch + idempotency (US-25 / FR-22)."""

import pytest

from apps.booking.models import BookingStatus
from apps.payments.models import StripeEvent
from apps.payments.services import process_webhook_event
from tests.booking.factories import (
    BookingFactory,
    CancelledBookingFactory,
    ConfirmedBookingFactory,
)

pytestmark = pytest.mark.django_db


def _event(event_type, *, client_reference_id, payment_intent="pi_test_1", event_id="evt_test_1"):
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "client_reference_id": str(client_reference_id),
                "payment_intent": payment_intent,
            }
        },
    }


class TestProcessWebhookEvent:
    def test_completed_confirms_pending_booking(self):
        booking = BookingFactory()  # PENDING
        result = process_webhook_event(
            _event("checkout.session.completed", client_reference_id=booking.id)
        )
        assert result is True
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.stripe_payment_intent_id == "pi_test_1"
        assert booking.expires_at is None

    def test_expired_cancels_pending_booking(self):
        booking = BookingFactory()
        process_webhook_event(
            _event("checkout.session.expired", client_reference_id=booking.id, event_id="evt_e1")
        )
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_duplicate_event_is_noop(self):
        booking = BookingFactory()
        event = _event("checkout.session.completed", client_reference_id=booking.id)
        assert process_webhook_event(event) is True
        assert process_webhook_event(event) is False  # same event_id
        assert StripeEvent.objects.filter(event_id="evt_test_1").count() == 1
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_completed_on_confirmed_booking_no_change(self):
        booking = ConfirmedBookingFactory()
        original_pi = booking.stripe_payment_intent_id
        process_webhook_event(
            _event(
                "checkout.session.completed",
                client_reference_id=booking.id,
                payment_intent="pi_other",
                event_id="evt_c1",
            )
        )
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.stripe_payment_intent_id == original_pi  # not overwritten

    def test_completed_on_cancelled_booking_no_change(self):
        booking = CancelledBookingFactory()
        process_webhook_event(
            _event("checkout.session.completed", client_reference_id=booking.id, event_id="evt_x1")
        )
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED

    def test_unknown_event_type_logged_only(self):
        booking = BookingFactory()
        result = process_webhook_event(
            _event(
                "payment_intent.payment_failed",
                client_reference_id=booking.id,
                event_id="evt_u1",
            )
        )
        assert result is True
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING
        assert StripeEvent.objects.filter(event_id="evt_u1").exists()

    def test_missing_booking_does_not_crash(self):
        result = process_webhook_event(
            _event("checkout.session.completed", client_reference_id=999999, event_id="evt_m1")
        )
        assert result is True
        assert StripeEvent.objects.filter(event_id="evt_m1").exists()

    def test_invalid_client_reference_id_does_not_crash(self):
        result = process_webhook_event(
            _event("checkout.session.completed", client_reference_id="abc", event_id="evt_i1")
        )
        assert result is True

    def test_processed_at_set_on_success(self):
        booking = BookingFactory()
        process_webhook_event(
            _event("checkout.session.completed", client_reference_id=booking.id, event_id="evt_p1")
        )
        assert StripeEvent.objects.get(event_id="evt_p1").processed_at is not None
