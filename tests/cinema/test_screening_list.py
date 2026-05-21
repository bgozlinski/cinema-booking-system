"""Tests for ScreeningListView (US-14 / FR-04)."""

import datetime as dt
from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from tests.cinema.factories import MovieFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


def _make_local_dt(date, hour=18, minute=0, second=0):
    return timezone.make_aware(dt.datetime.combine(date, dt.time(hour, minute, second)))


class TestRouting:
    def test_url_returns_200_anon(self, client):
        response = client.get("/screenings/")
        assert response.status_code == 200

    def test_url_returns_200_authenticated(self, client, django_user_model):
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get("/screenings/")
        assert response.status_code == 200

    def test_url_name_reverses(self):
        assert reverse("cinema:screening_list") == "/screenings/"

    def test_uses_screening_list_template(self, client):
        response = client.get("/screenings/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/screening_list.html" in template_names


class TestResolveDate:
    def test_no_date_param_defaults_to_today(self, client):
        response = client.get("/screenings/")
        assert response.context["effective_date"] == timezone.localdate()
        assert len(list(get_messages(response.wsgi_request))) == 0

    def test_explicit_today_renders_today(self, client):
        today = timezone.localdate()
        response = client.get(f"/screenings/?date={today.isoformat()}")
        assert response.context["effective_date"] == today
        assert len(list(get_messages(response.wsgi_request))) == 0

    def test_future_within_30_days_passes_through(self, client):
        target = timezone.localdate() + timedelta(days=15)
        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert response.context["effective_date"] == target
        assert len(list(get_messages(response.wsgi_request))) == 0

    def test_past_date_clamps_to_today(self, client):
        past = timezone.localdate() - timedelta(days=5)
        response = client.get(f"/screenings/?date={past.isoformat()}")
        assert response.context["effective_date"] == timezone.localdate()
        msgs = list(get_messages(response.wsgi_request))
        assert len(msgs) == 1
        assert "poza zakresem" in str(msgs[0])

    def test_far_future_clamps_to_today_plus_30(self, client):
        far = timezone.localdate() + timedelta(days=90)
        response = client.get(f"/screenings/?date={far.isoformat()}")
        assert response.context["effective_date"] == timezone.localdate() + timedelta(days=30)
        msgs = list(get_messages(response.wsgi_request))
        assert len(msgs) == 1
        assert "poza zakresem" in str(msgs[0])

    def test_malformed_date_clamps_to_today(self, client):
        response = client.get("/screenings/?date=not-a-date")
        assert response.context["effective_date"] == timezone.localdate()
        msgs = list(get_messages(response.wsgi_request))
        assert len(msgs) == 1

    def test_empty_date_string_defaults_to_today_no_warning(self, client):
        response = client.get("/screenings/?date=")
        assert response.context["effective_date"] == timezone.localdate()
        assert len(list(get_messages(response.wsgi_request))) == 0


class TestGroupingAndOrdering:
    def test_screenings_grouped_by_movie(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie_a = MovieFactory(title="A")
        movie_b = MovieFactory(title="B")
        ScreeningFactory(movie=movie_a, start_time=_make_local_dt(tomorrow, 14))
        ScreeningFactory(movie=movie_a, start_time=_make_local_dt(tomorrow, 18))
        ScreeningFactory(movie=movie_b, start_time=_make_local_dt(tomorrow, 16))
        ScreeningFactory(movie=movie_b, start_time=_make_local_dt(tomorrow, 20))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        groups = response.context["movie_groups"]

        assert len(groups) == 2
        movies_in_groups = {g[0] for g in groups}
        assert movies_in_groups == {movie_a, movie_b}
        for _, screenings in groups:
            assert len(screenings) == 2

    def test_movies_ordered_by_earliest_screening(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie_late = MovieFactory(title="Late")
        movie_early = MovieFactory(title="Early")
        ScreeningFactory(movie=movie_late, start_time=_make_local_dt(tomorrow, 21))
        ScreeningFactory(movie=movie_early, start_time=_make_local_dt(tomorrow, 14))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        groups = response.context["movie_groups"]

        assert groups[0][0] == movie_early
        assert groups[1][0] == movie_late

    def test_screenings_within_group_sorted_by_start_time(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 21))
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 14))
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 18))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        screenings = response.context["movie_groups"][0][1]

        hours = [s.start_time.astimezone(timezone.get_current_timezone()).hour for s in screenings]
        assert hours == [14, 18, 21]

    def test_past_screenings_for_today_still_included(self, client):
        # A screening at 06:00 local today — even if it's past now, the day filter still includes it.
        today = timezone.localdate()
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(today, 6))

        response = client.get(f"/screenings/?date={today.isoformat()}")
        groups = response.context["movie_groups"]

        assert any(g[0] == movie for g in groups)


class TestDayWindowBoundary:
    def test_boundary_inclusive_at_midnight(self, client):
        target = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(target, 0, 0, 0))

        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert any(g[0] == movie for g in response.context["movie_groups"])

    def test_boundary_inclusive_at_end_of_day(self, client):
        target = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(target, 23, 59, 59))

        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert any(g[0] == movie for g in response.context["movie_groups"])

    def test_boundary_excludes_next_day_midnight(self, client):
        target = timezone.localdate() + timedelta(days=1)
        next_day = target + timedelta(days=1)
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=_make_local_dt(next_day, 0, 0, 0))

        response = client.get(f"/screenings/?date={target.isoformat()}")
        assert not any(g[0] == movie for g in response.context["movie_groups"])
