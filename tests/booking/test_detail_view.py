"""Tests for BookingDetailView (US-21 / FR-08)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory, ConfirmedBookingFactory
from tests.cinema.factories import MovieFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _detail_url(booking):
    return reverse("booking:detail", kwargs={"pk": booking.pk})


class TestBookingDetailAccess:
    def test_anonymous_redirected_to_login(self, client):
        booking = BookingFactory()
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert "next=" in resp.url

    def test_owner_gets_200(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 200
        assert resp.context["booking"] == booking

    def test_staff_non_owner_gets_200(self, client):
        booking = BookingFactory()
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 200

    def test_other_user_forbidden(self, client):
        booking = BookingFactory()
        other = UserFactory()
        client.force_login(other)
        resp = client.get(_detail_url(booking))
        assert resp.status_code == 403

    def test_404_for_missing_booking(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse("booking:detail", kwargs={"pk": 999999}))
        assert resp.status_code == 404


class TestBookingDetailContent:
    def test_renders_booking_fields(self, client):
        screening = ScreeningFactory(movie=MovieFactory(title="Diuna"), price=Decimal("25.00"))
        booking = ConfirmedBookingFactory(screening=screening, seats_count=3)
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking))
        content = resp.content.decode()
        assert "Diuna" in content
        assert "75" in content  # total_price 3x25, locale-agnostic integer part
        assert "Potwierdzona" in content  # CONFIRMED display

    def test_template_used(self, client):
        booking = BookingFactory()
        client.force_login(booking.user)
        resp = client.get(_detail_url(booking))
        assert "booking/booking_detail.html" in [t.name for t in resp.templates]


class TestBookingDetailBudget:
    def test_query_budget(self, client, django_assert_max_num_queries):
        booking = BookingFactory()
        client.force_login(booking.user)
        with django_assert_max_num_queries(5):
            client.get(_detail_url(booking))
