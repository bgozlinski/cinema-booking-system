"""Tests for MyBookingsView (US-22 / FR-09)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory
from tests.cinema.factories import ScreeningFactory

pytestmark = pytest.mark.django_db


def _url():
    return reverse("booking:my_bookings")


def _past_screening():
    return ScreeningFactory(start_time=timezone.now() - timedelta(days=1))


class TestMyBookingsAccess:
    def test_anonymous_redirected_to_login(self, client):
        resp = client.get(_url())
        assert resp.status_code == 302
        assert reverse("accounts:login") in resp.url
        assert "next=" in resp.url


class TestMyBookingsScoping:
    def test_shows_only_own_bookings(self, client):
        me = UserFactory()
        BookingFactory(user=me)  # future (factory default +7d)
        BookingFactory()  # another user
        client.force_login(me)
        resp = client.get(_url())
        bookings = list(resp.context["bookings"])
        assert len(bookings) == 1
        assert bookings[0].user == me


class TestMyBookingsTabs:
    def test_upcoming_is_default(self, client):
        me = UserFactory()
        future = BookingFactory(user=me)
        BookingFactory(user=me, screening=_past_screening())
        client.force_login(me)
        resp = client.get(_url())
        assert resp.context["active_tab"] == "upcoming"
        ids = {b.id for b in resp.context["bookings"]}
        assert ids == {future.id}

    def test_history_tab_shows_past(self, client):
        me = UserFactory()
        BookingFactory(user=me)  # future
        past = BookingFactory(user=me, screening=_past_screening())
        client.force_login(me)
        resp = client.get(_url(), {"tab": "history"})
        assert resp.context["active_tab"] == "history"
        ids = {b.id for b in resp.context["bookings"]}
        assert ids == {past.id}

    def test_unknown_tab_falls_back_to_upcoming(self, client):
        client.force_login(UserFactory())
        resp = client.get(_url(), {"tab": "garbage"})
        assert resp.context["active_tab"] == "upcoming"


class TestMyBookingsOrdering:
    def test_newest_first(self, client):
        me = UserFactory()
        first = BookingFactory(user=me)
        second = BookingFactory(user=me)
        client.force_login(me)
        resp = client.get(_url())
        bookings = list(resp.context["bookings"])
        assert bookings[0] == second  # later created_at first
        assert bookings[1] == first


class TestMyBookingsContent:
    def test_empty_state(self, client):
        client.force_login(UserFactory())
        resp = client.get(_url())
        assert resp.status_code == 200
        assert list(resp.context["bookings"]) == []

    def test_links_to_detail(self, client):
        me = UserFactory()
        booking = BookingFactory(user=me)
        client.force_login(me)
        resp = client.get(_url())
        assert reverse("booking:detail", kwargs={"pk": booking.pk}) in resp.content.decode()

    def test_template_used(self, client):
        client.force_login(UserFactory())
        resp = client.get(_url())
        assert "booking/my_bookings.html" in [t.name for t in resp.templates]

    def test_cancel_button_wired_to_cancel_endpoint(self, client):
        # US-23 wired the US-22 placeholder into a real POST form for cancellable
        # (PENDING + >1h) bookings.
        me = UserFactory()
        booking = BookingFactory(user=me)  # PENDING, future → cancellable
        client.force_login(me)
        content = client.get(_url()).content.decode()
        assert "Anuluj" in content
        assert reverse("booking:cancel", kwargs={"pk": booking.pk}) in content


class TestMyBookingsBudget:
    def test_query_budget(self, client, django_assert_max_num_queries):
        me = UserFactory()
        for _ in range(3):
            BookingFactory(user=me)
        client.force_login(me)
        with django_assert_max_num_queries(6):
            client.get(_url())
