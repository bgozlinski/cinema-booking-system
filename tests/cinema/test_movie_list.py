"""Tests for MovieListView (US-11 / FR-01)."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.cinema.forms import MovieFilterForm
from tests.cinema.factories import GenreFactory, MovieFactory, ScreeningFactory

pytestmark = pytest.mark.django_db


# Smallest valid PNG (1x1) — reused from tests/cinema/test_admin.py
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc"
    b"\xff\xff?\x03\x00\x06\x00\x02\x00\x01\xa5\xc8\x7f\xb1\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)


class TestRouting:
    def test_root_url_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_movies_url_returns_200(self, client):
        response = client.get("/movies/")
        assert response.status_code == 200

    def test_cinema_home_reverses_to_root(self):
        assert reverse("cinema:home") == "/"

    def test_cinema_movie_list_reverses_to_movies(self):
        assert reverse("cinema:movie_list") == "/movies/"

    def test_root_uses_movie_list_template(self, client):
        response = client.get("/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_list.html" in template_names

    def test_movies_uses_movie_list_template(self, client):
        response = client.get("/movies/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_list.html" in template_names

    def test_anonymous_user_gets_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_authenticated_user_gets_200(self, client, django_user_model):
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get("/")
        assert response.status_code == 200


class TestQueryset:
    def test_movie_with_future_screening_is_visible(self, client):
        movie = MovieFactory(title="Future Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")

        assert movie in response.context["movies"]

    def test_movie_with_only_past_screening_is_hidden(self, client):
        movie = MovieFactory(title="Past Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))

        response = client.get("/")

        assert movie not in response.context["movies"]

    def test_movie_with_no_screenings_is_hidden(self, client):
        movie = MovieFactory(title="Orphan Movie")

        response = client.get("/")

        assert movie not in response.context["movies"]

    def test_movie_with_past_and_future_screenings_uses_future_as_next(self, client):
        """Regression: Min() must include filter=Q(start_time>=now), otherwise
        next_screening_at picks up the past screening's date."""
        movie = MovieFactory(title="Mixed Movie")
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=3))
        future = timezone.now() + timedelta(days=2)
        ScreeningFactory(movie=movie, start_time=future)

        response = client.get("/")

        listed = list(response.context["movies"])
        assert movie in listed
        # The annotation rounds to microseconds; allow 1-second tolerance.
        rendered = next(m for m in listed if m.pk == movie.pk)
        assert abs((rendered.next_screening_at - future).total_seconds()) < 1

    def test_movies_are_sorted_by_next_screening_ascending(self, client):
        now = timezone.now()
        movie_late = MovieFactory(title="Late")
        movie_early = MovieFactory(title="Early")
        movie_mid = MovieFactory(title="Mid")
        ScreeningFactory(movie=movie_late, start_time=now + timedelta(days=3))
        ScreeningFactory(movie=movie_early, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=movie_mid, start_time=now + timedelta(days=2))

        response = client.get("/")

        titles = [m.title for m in response.context["movies"]]
        assert titles == ["Early", "Mid", "Late"]


class TestCardRendering:
    def test_card_shows_title(self, client):
        movie = MovieFactory(title="Unique Card Title")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")

        assert "Unique Card Title" in response.content.decode()

    def test_card_shows_all_genres_in_meta(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        movie.genres.add(GenreFactory(name="Drama"), GenreFactory(name="Sci-Fi"))

        response = client.get("/")
        content = response.content.decode()

        assert "Drama" in content
        assert "Sci-Fi" in content
        # New design renders genres as plain text inside .movie-card__meta separated by " · ",
        # no Bootstrap badge classes.
        assert 'class="movie-card__meta"' in content
        assert "Drama · Sci-Fi" in content or "Sci-Fi · Drama" in content

    def test_card_does_not_show_next_screening_date(self, client):
        """Wariant C movie-card: poster + title overlay only. next_screening_at stays
        in queryset for sorting but is no longer rendered on the card."""
        movie = MovieFactory()
        future = timezone.now().replace(hour=18, minute=30) + timedelta(days=2)
        ScreeningFactory(movie=movie, start_time=future)

        response = client.get("/")
        content = response.content.decode()

        local_future = timezone.localtime(future)
        assert local_future.strftime("%d.%m.%Y %H:%M") not in content
        # Sorting still works — annotation present in queryset
        assert movie.title in content

    def test_card_links_whole_poster_to_movie_detail(self, client):
        """Wariant C: cały plakat jest klikalnym linkiem (.movie-card),
        bez osobnego przycisku 'Szczegóły'."""
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert f'href="/movies/{movie.pk}/"' in content
        assert 'class="movie-card' in content
        # The disabled stub from US-11 is gone now; new design has no "Szczegóły" button.
        assert "btn-primary btn-sm mt-auto disabled" not in content
        assert "Szczegóły" not in content

    def test_card_uses_emoji_placeholder_when_poster_blank(self, client):
        movie = MovieFactory(poster="")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert "🎬" in content
        # No broken <img src="">
        assert 'src=""' not in content

    def test_card_uses_real_poster_when_set(self, client):
        movie = MovieFactory()
        movie.poster = SimpleUploadedFile("p.png", PNG_1X1, content_type="image/png")
        movie.save()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert movie.poster.url in content
        assert "<img" in content


class TestPagination:
    def test_page_one_shows_12_cards_when_13_movies(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/")

        assert len(response.context["movies"]) == 12

    def test_page_two_shows_remaining_card_when_13_movies(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/?page=2")

        assert len(response.context["movies"]) == 1

    def test_page_out_of_range_returns_404(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/?page=3")

        assert response.status_code == 404

    def test_pagination_nav_hidden_when_one_page(self, client):
        # 12 movies → exactly one page → no nav.
        now = timezone.now()
        for i in range(12):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/")
        content = response.content.decode()

        assert 'class="pagination' not in content

    def test_pagination_nav_visible_when_multiple_pages(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory()
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/")
        content = response.content.decode()

        assert 'class="pagination' in content


class TestEmptyState:
    def test_empty_state_shown_when_no_future_screenings(self, client):
        # No movies at all.
        response = client.get("/")
        content = response.content.decode()

        assert "Aktualnie brak filmów" in content
        assert "row-cols-" not in content

    def test_empty_state_shown_when_only_past_screenings(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert "Aktualnie brak filmów" in content


class TestQueryBudget:
    def test_full_page_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """12 movies, each with 2 genres → without prefetch this would be 1 + 12 = 13 queries
        for genres alone, blowing past the budget. The annotated queryset's prefetch_related
        keeps it tight.

        US-12 adds 1 query for the Genre filter dropdown (queryset eval in form rendering),
        so the cap bumps from 4 → 5.
        """
        now = timezone.now()
        for i in range(12):
            movie = MovieFactory()
            movie.genres.add(GenreFactory(), GenreFactory())
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        # Budget: 1 paginator.count + 1 movies + 1 prefetched genres + 1 form genre dropdown = 4.
        # Cap at 5 to absorb any test-harness query without flaking.
        with django_assert_max_num_queries(5):
            client.get("/")


class TestFilters:
    def test_q_filter_matches_icontains(self, client):
        now = timezone.now()
        wanted = MovieFactory(title="The Matrix")
        other = MovieFactory(title="Other Movie")
        ScreeningFactory(movie=wanted, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=other, start_time=now + timedelta(days=1))

        response = client.get("/?q=matrix")

        listed = list(response.context["movies"])
        assert wanted in listed
        assert other not in listed

    def test_q_filter_is_case_insensitive(self, client):
        movie = MovieFactory(title="Inception")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/?q=INCEPTION")

        assert movie in list(response.context["movies"])

    def test_q_filter_empty_string_returns_all(self, client):
        now = timezone.now()
        m1 = MovieFactory()
        m2 = MovieFactory()
        ScreeningFactory(movie=m1, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=m2, start_time=now + timedelta(days=1))

        response = client.get("/?q=")

        listed = list(response.context["movies"])
        assert m1 in listed
        assert m2 in listed

    def test_genre_filter_narrows_results(self, client):
        now = timezone.now()
        drama = GenreFactory(name="Drama")
        action = GenreFactory(name="Action")
        movie_drama = MovieFactory()
        movie_action = MovieFactory()
        movie_drama.genres.add(drama)
        movie_action.genres.add(action)
        ScreeningFactory(movie=movie_drama, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=movie_action, start_time=now + timedelta(days=1))

        response = client.get(f"/?genre={drama.pk}")

        listed = list(response.context["movies"])
        assert movie_drama in listed
        assert movie_action not in listed

    def test_genre_filter_invalid_pk_returns_all(self, client):
        now = timezone.now()
        m1 = MovieFactory()
        m2 = MovieFactory()
        ScreeningFactory(movie=m1, start_time=now + timedelta(days=1))
        ScreeningFactory(movie=m2, start_time=now + timedelta(days=1))

        response = client.get("/?genre=99999")

        listed = list(response.context["movies"])
        assert m1 in listed
        assert m2 in listed

    def test_date_filter_matches_screening_on_that_day(self, client):
        now = timezone.now()
        tomorrow = (now + timedelta(days=1)).date()
        movie_match = MovieFactory()
        movie_other = MovieFactory()
        ScreeningFactory(
            movie=movie_match,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )
        ScreeningFactory(
            movie=movie_other,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=2),
        )

        response = client.get(f"/?date={tomorrow.isoformat()}")

        listed = list(response.context["movies"])
        assert movie_match in listed
        assert movie_other not in listed

    def test_date_filter_boundary_inclusive_at_midnight(self, client):
        import datetime as dt

        target_date = (timezone.now() + timedelta(days=1)).date()
        midnight_local = timezone.make_aware(dt.datetime.combine(target_date, dt.time(0, 0)))
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=midnight_local)

        response = client.get(f"/?date={target_date.isoformat()}")

        assert movie in list(response.context["movies"])

    def test_date_filter_boundary_inclusive_at_end_of_day(self, client):
        import datetime as dt

        target_date = (timezone.now() + timedelta(days=1)).date()
        almost_midnight = timezone.make_aware(dt.datetime.combine(target_date, dt.time(23, 59, 59)))
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=almost_midnight)

        response = client.get(f"/?date={target_date.isoformat()}")

        assert movie in list(response.context["movies"])

    def test_date_filter_excludes_next_day(self, client):
        import datetime as dt

        target_date = (timezone.now() + timedelta(days=1)).date()
        next_day_midnight = timezone.make_aware(
            dt.datetime.combine(target_date + timedelta(days=1), dt.time(0, 0))
        )
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=next_day_midnight)

        response = client.get(f"/?date={target_date.isoformat()}")

        assert movie not in list(response.context["movies"])

    def test_combined_filters_intersect(self, client):
        now = timezone.now()
        drama = GenreFactory(name="Drama")
        target_date = (now + timedelta(days=1)).date()

        match = MovieFactory(title="Star Drama")
        match.genres.add(drama)
        ScreeningFactory(
            movie=match,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )

        wrong_title = MovieFactory(title="Other")
        wrong_title.genres.add(drama)
        ScreeningFactory(
            movie=wrong_title,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )

        action = GenreFactory(name="Action")
        wrong_genre = MovieFactory(title="Star Action")
        wrong_genre.genres.add(action)
        ScreeningFactory(
            movie=wrong_genre,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=1),
        )

        wrong_date = MovieFactory(title="Star Future")
        wrong_date.genres.add(drama)
        ScreeningFactory(
            movie=wrong_date,
            start_time=now.replace(hour=18, minute=0) + timedelta(days=5),
        )

        response = client.get(f"/?q=star&genre={drama.pk}&date={target_date.isoformat()}")

        listed = list(response.context["movies"])
        assert match in listed
        assert wrong_title not in listed
        assert wrong_genre not in listed
        assert wrong_date not in listed

    def test_filter_form_in_context(self, client):
        response = client.get("/")
        assert isinstance(response.context["filter_form"], MovieFilterForm)


class TestFilterFormRendering:
    def test_filter_form_q_field_renders(self, client):
        response = client.get("/")
        content = response.content.decode()
        assert 'name="q"' in content
        assert 'placeholder="Tytuł filmu..."' in content

    def test_filter_form_genre_dropdown_includes_empty_label(self, client):
        GenreFactory(name="Drama")
        response = client.get("/")
        content = response.content.decode()
        assert "Wszystkie gatunki" in content
        assert 'name="genre"' in content

    def test_filter_form_date_input_uses_html5_type(self, client):
        response = client.get("/")
        content = response.content.decode()
        assert 'type="date"' in content
        assert 'name="date"' in content

    def test_filter_form_preserves_submitted_values(self, client):
        response = client.get("/?q=star&date=2026-05-23")
        content = response.content.decode()
        assert 'value="star"' in content
        assert 'value="2026-05-23"' in content


class TestResetLink:
    def test_reset_link_hidden_when_no_filters_active(self, client):
        response = client.get("/")
        content = response.content.decode()
        assert "Wyczyść filtry" not in content
        assert 'title="Wyczyść filtry"' not in content

    def test_reset_link_visible_when_filters_active(self, client):
        response = client.get("/?q=xyz")
        content = response.content.decode()
        assert 'title="Wyczyść filtry"' in content
        assert 'href="/movies/"' in content


class TestEmptyStateVariants:
    def test_filter_empty_state_when_no_match(self, client):
        movie = MovieFactory(title="Inception")
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/?q=zzzzzz")
        content = response.content.decode()

        assert "Brak filmów pasujących" in content
        assert "Wyczyść filtry" in content
        # The "no future screenings anywhere" copy must NOT appear here.
        assert "Wróć wkrótce" not in content

    def test_no_screenings_empty_state_copy_when_no_filters_no_movies(self, client):
        response = client.get("/")
        content = response.content.decode()

        assert "Aktualnie brak filmów" in content
        assert "Wróć wkrótce" in content
        # Filter-empty copy must NOT appear here.
        assert "Brak filmów pasujących" not in content


class TestPaginationFilterPreservation:
    def test_filter_pagination_preserves_query_params(self, client):
        now = timezone.now()
        for i in range(13):
            movie = MovieFactory(title=f"Common Movie {i}")
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        response = client.get("/?q=Common")
        content = response.content.decode()

        # Pagination block must contain both q=Common and page=2.
        assert "q=Common" in content
        assert "page=2" in content
