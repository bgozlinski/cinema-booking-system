"""Tests for ScreeningListView (US-14 / FR-04)."""

import datetime as dt
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from tests.cinema.factories import GenreFactory, HallFactory, MovieFactory, ScreeningFactory

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


class TestRendering:
    def test_movie_title_links_to_detail_page(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory(title="Linked Movie")
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 18))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert "Linked Movie" in content
        assert f'href="/movies/{movie.pk}/"' in content

    def test_screening_pill_shows_hour_grouped_by_hall(self, client):
        """UI-handoff redesign: hour pill + hall label, with the per-seat price shown as a
        subline on the pill (.time-pill__price). The pill itself is the link to the booking
        page, so there is no separate 'Zarezerwuj' button text on the list."""
        tomorrow = timezone.localdate() + timedelta(days=1)
        hall = HallFactory(name="Sala A", capacity=100)
        movie = MovieFactory()
        ScreeningFactory(
            movie=movie,
            hall=hall,
            start_time=_make_local_dt(tomorrow, 18),
            price=Decimal("42.50"),
        )

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert "18:00" in content
        # Hall name appears as a label above its pills group
        assert "Sala A" in content
        assert 'class="time-pill-hall-label"' in content
        # The hour is rendered inside a .time-pill anchor
        assert 'class="time-pill' in content
        # Price subline is now shown on the pill (handoff redesign re-adds it).
        assert 'class="time-pill__price"' in content
        assert "zł" in content
        # No standalone "Zarezerwuj" button text — the pill is the link.
        assert "Zarezerwuj" not in content

    def test_genres_render_on_screening_card_meta(self, client):
        """Redesign: gatunki jako plain text w .screening-card__meta,
        bez Bootstrap badge classes."""
        tomorrow = timezone.localdate() + timedelta(days=1)
        movie = MovieFactory()
        movie.genres.add(GenreFactory(name="Drama"), GenreFactory(name="Sci-Fi"))
        ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, 18))

        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert "Drama" in content
        assert "Sci-Fi" in content
        assert 'class="screening-card__meta"' in content
        assert "Drama · Sci-Fi" in content or "Sci-Fi · Drama" in content

    def test_empty_state_when_no_screenings_for_day(self, client):
        # No screenings anywhere → empty state for today.
        response = client.get("/screenings/")
        content = response.content.decode()

        assert "Brak seansów na dzień" in content
        assert "<table" not in content

    def test_dzisiaj_link_visible_when_date_param_present(self, client):
        tomorrow = timezone.localdate() + timedelta(days=1)
        response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
        content = response.content.decode()

        assert ">Dzisiaj<" in content
        assert 'href="/screenings/"' in content

    def test_dzisiaj_link_hidden_without_date_param(self, client):
        response = client.get("/screenings/")
        content = response.content.decode()

        assert ">Dzisiaj<" not in content

    def test_clamp_warning_shows_in_messages_block(self, client):
        past = (timezone.localdate() - timedelta(days=5)).isoformat()
        response = client.get(f"/screenings/?date={past}", follow=True)
        content = response.content.decode()
        assert "Data poza zakresem" in content

    def test_date_input_min_max_set_for_browser_picker(self, client):
        response = client.get("/screenings/")
        content = response.content.decode()
        today_iso = timezone.localdate().isoformat()
        max_iso = (timezone.localdate() + timedelta(days=30)).isoformat()
        assert f'min="{today_iso}"' in content
        assert f'max="{max_iso}"' in content


class TestQueryBudget:
    def test_full_day_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """5 movies x 3 screenings each = 15 rows. select_related("movie", "hall")
        joins on the screenings query; prefetch_related("movie__genres") loads genres
        in a single batched query. Budget cap 3 absorbs harness overhead."""
        tomorrow = timezone.localdate() + timedelta(days=1)
        for _ in range(5):
            movie = MovieFactory()
            movie.genres.add(GenreFactory(), GenreFactory())
            for hour in (12, 16, 20):
                ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, hour))

        with django_assert_max_num_queries(3):
            client.get(f"/screenings/?date={tomorrow.isoformat()}")

    def test_empty_day_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Empty day = 0 screenings. Brak prefetch needed (empty queryset),
        tylko Screening fetch + (optional) messages/session baseline."""
        # Tworzę screening DZIŚ, ale pytam o tomorrow (empty result for tomorrow).
        today = timezone.localdate()
        tomorrow = (today + timedelta(days=1)).isoformat()
        ScreeningFactory(start_time=_make_local_dt(today, hour=12))

        # Budget: 1 screenings fetch (zwraca 0) + ewentualne messages/session = 2.
        with django_assert_max_num_queries(2):
            response = client.get(f"/screenings/?date={tomorrow}")
            assert response.status_code == 200

    def test_big_dataset_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """20 movies x 5 screenings = 100 rows. Prefetch nie skaluje się z N —
        budget pozostaje stały."""
        tomorrow = timezone.localdate() + timedelta(days=1)
        for _ in range(20):
            movie = MovieFactory()
            for hour in (10, 13, 16, 19, 22):
                ScreeningFactory(movie=movie, start_time=_make_local_dt(tomorrow, hour))

        # Budget: 1 screenings (z select_related + prefetch) + ewentualne messages = 2-3.
        # Cap 3 (zgodnie z base buffer).
        with django_assert_max_num_queries(3):
            response = client.get(f"/screenings/?date={tomorrow.isoformat()}")
            assert response.status_code == 200
