"""Tests for MovieListView (US-11 / FR-01)."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

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

    def test_card_shows_all_genre_badges(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        movie.genres.add(GenreFactory(name="Drama"), GenreFactory(name="Sci-Fi"))

        response = client.get("/")
        content = response.content.decode()

        assert "Drama" in content
        assert "Sci-Fi" in content
        assert content.count('class="badge bg-secondary"') >= 2

    def test_card_shows_next_screening_date(self, client):
        movie = MovieFactory()
        future = timezone.now().replace(hour=18, minute=30) + timedelta(days=2)
        ScreeningFactory(movie=movie, start_time=future)

        response = client.get("/")

        # Django's |date filter converts UTC → active TZ (Europe/Warsaw); mirror that
        # locally so the comparison string matches the rendered HTML.
        local_future = timezone.localtime(future)
        assert local_future.strftime("%d.%m.%Y %H:%M") in response.content.decode()

    def test_card_links_details_button_to_movie_detail(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))

        response = client.get("/")
        content = response.content.decode()

        assert "Szczegóły" in content
        assert f'href="/movies/{movie.pk}/"' in content
        # The disabled stub from US-11 is gone now.
        assert "btn-primary btn-sm mt-auto disabled" not in content

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
        keeps it tight."""
        now = timezone.now()
        for i in range(12):
            movie = MovieFactory()
            movie.genres.add(GenreFactory(), GenreFactory())
            ScreeningFactory(movie=movie, start_time=now + timedelta(days=i + 1))

        # Budget: 1 paginator.count + 1 movies + 1 prefetched genres = 3 baseline.
        # Cap at 4 to absorb any test-harness query (session etc.) without flaking.
        with django_assert_max_num_queries(4):
            client.get("/")
