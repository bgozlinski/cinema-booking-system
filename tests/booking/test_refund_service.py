import pytest
import stripe

from apps.booking.models import BookingStatus
from apps.booking.services import BookingNotRefundableError, RefundError, refund_booking
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory

pytestmark = pytest.mark.django_db


class TestRefundBooking:
    @pytest.mark.stripe
    def test_confirmed_booking_refunded(self, mock_refund):
        booking = ConfirmedBookingFactory()
        result = refund_booking(booking=booking)
        assert result.status == BookingStatus.CANCELLED
        assert result.refund_id == "re_test_123"
        assert result.refunded_at is not None

    def test_pending_booking_not_refundable(self):
        booking = BookingFactory()  # PENDING, no payment intent
        with pytest.raises(BookingNotRefundableError):
            refund_booking(booking=booking)

    @pytest.mark.stripe
    def test_stripe_failure_rolls_back(self, mock_refund):
        mock_refund.side_effect = stripe.APIConnectionError("boom")
        booking = ConfirmedBookingFactory()
        with pytest.raises(RefundError):
            refund_booking(booking=booking)
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED  # rolled back
        assert booking.refund_id == ""
