"""Unit test for the Stripe checkout stub (US-20 / FR-21 placeholder)."""

import pytest
from django.urls import reverse

from apps.payments.services import create_checkout_session
from tests.booking.factories import BookingFactory

pytestmark = pytest.mark.django_db


def test_create_checkout_session_returns_movie_detail_url_and_empty_session():
    booking = BookingFactory()
    url, session_id = create_checkout_session(booking)
    assert url == reverse("cinema:movie_detail", kwargs={"pk": booking.screening.movie_id})
    assert session_id == ""
