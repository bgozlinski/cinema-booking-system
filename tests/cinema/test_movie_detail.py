"""Tests for MovieDetailView (US-13 / FR-03)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    HallFactory,
    MovieFactory,
    ScreeningFactory,
)

pytestmark = pytest.mark.django_db


# Smallest valid PNG (1x1) — reused from tests/cinema/test_movie_list.py
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc"
    b"\xff\xff?\x03\x00\x06\x00\x02\x00\x01\xa5\xc8\x7f\xb1\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)


class TestRouting:
    def test_detail_url_returns_200(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200

    def test_missing_pk_returns_404(self, client):
        response = client.get("/movies/99999/")
        assert response.status_code == 404

    def test_movie_detail_reverses_correctly(self):
        movie = MovieFactory()
        assert reverse("cinema:movie_detail", kwargs={"pk": movie.pk}) == f"/movies/{movie.pk}/"

    def test_detail_uses_movie_detail_template(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        template_names = [t.name for t in response.templates if t.name]
        assert "cinema/movie_detail.html" in template_names

    def test_anonymous_user_gets_200(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200

    def test_authenticated_user_gets_200(self, client, django_user_model):
        movie = MovieFactory()
        user = django_user_model.objects.create_user(email="u@example.com", password="x" * 12)
        client.force_login(user)
        response = client.get(f"/movies/{movie.pk}/")
        assert response.status_code == 200


class TestMovieGetAbsoluteUrl:
    def test_returns_detail_path(self):
        movie = MovieFactory()
        assert movie.get_absolute_url() == f"/movies/{movie.pk}/"


class TestContext:
    def test_trailer_embed_url_for_youtube(self, client):
        movie = MovieFactory(trailer_url="https://youtu.be/dQw4w9WgXcQ")
        response = client.get(f"/movies/{movie.pk}/")
        assert (
            response.context["trailer_embed_url"]
            == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
        )

    def test_trailer_embed_url_is_none_for_non_youtube(self, client):
        movie = MovieFactory(trailer_url="https://example.com/clip.mp4")
        response = client.get(f"/movies/{movie.pk}/")
        assert response.context["trailer_embed_url"] is None

    def test_trailer_embed_url_is_none_for_blank_trailer(self, client):
        movie = MovieFactory(trailer_url="")
        response = client.get(f"/movies/{movie.pk}/")
        assert response.context["trailer_embed_url"] is None

    def test_upcoming_screenings_includes_future(self, client):
        movie = MovieFactory()
        future = ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        response = client.get(f"/movies/{movie.pk}/")
        assert future in list(response.context["upcoming_screenings"])

    def test_upcoming_screenings_excludes_past(self, client):
        movie = MovieFactory()
        past = ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))
        response = client.get(f"/movies/{movie.pk}/")
        assert past not in list(response.context["upcoming_screenings"])

    def test_upcoming_screenings_sorted_ascending(self, client):
        movie = MovieFactory()
        now = timezone.now()
        s_late = ScreeningFactory(movie=movie, start_time=now + timedelta(days=3))
        s_early = ScreeningFactory(movie=movie, start_time=now + timedelta(days=1))
        s_mid = ScreeningFactory(movie=movie, start_time=now + timedelta(days=2))

        response = client.get(f"/movies/{movie.pk}/")

        listed = list(response.context["upcoming_screenings"])
        assert listed == [s_early, s_mid, s_late]

    def test_upcoming_screenings_empty_for_orphan(self, client):
        movie = MovieFactory()  # no screenings
        response = client.get(f"/movies/{movie.pk}/")
        assert list(response.context["upcoming_screenings"]) == []


class TestHeroAndTrailer:
    def test_hero_shows_title(self, client):
        movie = MovieFactory(title="Unique Hero Title")
        response = client.get(f"/movies/{movie.pk}/")
        assert "Unique Hero Title" in response.content.decode()

    def test_hero_shows_release_date_and_duration(self, client):
        movie = MovieFactory(duration_minutes=137)
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "137" in content
        assert "min" in content
        assert movie.release_date.strftime("%d.%m.%Y") in content

    def test_hero_shows_description(self, client):
        movie = MovieFactory(description="A peculiar plot about cinema.")
        response = client.get(f"/movies/{movie.pk}/")
        assert "A peculiar plot about cinema." in response.content.decode()

    def test_hero_shows_genre_badges(self, client):
        movie = MovieFactory()
        movie.genres.add(GenreFactory(name="Sci-Fi"), GenreFactory(name="Drama"))
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Sci-Fi" in content
        assert "Drama" in content
        # Redesign: badges use the .movie-hero__genre-badge component class,
        # not Bootstrap's badge bg-secondary.
        assert content.count('class="movie-hero__genre-badge"') >= 2

    def test_hero_uses_emoji_placeholder_when_poster_blank(self, client):
        movie = MovieFactory(poster="")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "🎬" in content
        assert 'src=""' not in content

    def test_hero_uses_real_poster_when_set(self, client):
        movie = MovieFactory()
        movie.poster = SimpleUploadedFile("p.png", PNG_1X1, content_type="image/png")
        movie.save()
        response = client.get(f"/movies/{movie.pk}/")
        assert movie.poster.url in response.content.decode()

    def test_trailer_iframe_for_youtube_url(self, client):
        movie = MovieFactory(trailer_url="https://youtu.be/dQw4w9WgXcQ")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "<iframe" in content
        assert "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" in content
        assert 'sandbox="allow-scripts allow-same-origin allow-presentation"' in content

    def test_trailer_fallback_link_for_non_youtube(self, client):
        movie = MovieFactory(trailer_url="https://example.com/clip.mp4")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "<iframe" not in content
        assert 'href="https://example.com/clip.mp4"' in content
        assert 'rel="noopener noreferrer"' in content

    def test_trailer_section_hidden_when_url_blank(self, client):
        movie = MovieFactory(trailer_url="")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        # No iframe, no "Zwiastun" heading.
        assert "<iframe" not in content
        assert "Zwiastun" not in content


class TestDirectors:
    def test_directors_section_shows_names(self, client):
        movie = MovieFactory()
        d1 = DirectorFactory(full_name="Director One")
        d2 = DirectorFactory(full_name="Director Two")
        movie.directors.add(d1, d2)
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Director One" in content
        assert "Director Two" in content

    def test_directors_section_hidden_when_empty(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert "Reżyseria" not in response.content.decode()

    def test_director_photo_placeholder_when_blank(self, client):
        movie = MovieFactory()
        movie.directors.add(DirectorFactory(full_name="No-Photo Director", photo=""))
        response = client.get(f"/movies/{movie.pk}/")
        assert "👤" in response.content.decode()


class TestActorsCarousel:
    def test_actors_carousel_renders_data_attribute(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(), ActorFactory())
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert 'data-bs-ride="false"' in content

    def test_actors_carousel_has_one_item_per_actor(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(), ActorFactory(), ActorFactory())
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert content.count('class="carousel-item') == 3

    def test_actors_carousel_has_exactly_one_active_item(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(), ActorFactory(), ActorFactory())
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        # Bootstrap requires exactly one `.active` slide on load.
        assert content.count("carousel-item active") == 1

    def test_actors_section_hidden_when_empty(self, client):
        movie = MovieFactory()
        response = client.get(f"/movies/{movie.pk}/")
        assert "Obsada" not in response.content.decode()

    def test_actor_photo_placeholder_when_blank(self, client):
        movie = MovieFactory()
        movie.actors.add(ActorFactory(full_name="No-Photo Actor", photo=""))
        response = client.get(f"/movies/{movie.pk}/")
        assert "👤" in response.content.decode()


class TestUpcomingScreenings:
    def test_screening_pill_shows_hour_and_hall(self, client):
        """Redesign: seanse jako .time-pill z godziną pod labelem sali.
        Cena, dostępne miejsca i Zarezerwuj wycofane na przyszły screening_detail (US-21)."""
        hall = HallFactory(name="Sala A", capacity=100)
        movie = MovieFactory()
        future = timezone.now() + timedelta(days=1)
        ScreeningFactory(
            movie=movie,
            hall=hall,
            start_time=future,
            price=Decimal("42.50"),
        )
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        # Hall name appears as label above its pills group
        assert "Sala A" in content
        assert 'class="time-pill-hall-label"' in content
        # Pill itself uses .time-pill
        assert 'class="time-pill' in content
        # Hour rendered inside the pill (HH:MM format)
        assert timezone.localtime(future).strftime("%H:%M") in content
        # Out-of-scope info no longer rendered here
        assert "42,50" not in content
        assert "42.50" not in content
        assert "zł" not in content
        assert "Zarezerwuj" not in content

    def test_screening_empty_state_when_no_future(self, client):
        movie = MovieFactory()
        ScreeningFactory(movie=movie, start_time=timezone.now() - timedelta(days=1))
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert "Brak zaplanowanych seansów" in content
        assert "<table" not in content

    def test_orphan_movie_renders_with_only_hero_and_empty_alert(self, client):
        movie = MovieFactory(trailer_url="")
        response = client.get(f"/movies/{movie.pk}/")
        content = response.content.decode()
        assert response.status_code == 200
        assert movie.title in content
        assert "Brak zaplanowanych seansów" in content
        # No optional sections.
        assert "Reżyseria" not in content
        assert "Obsada" not in content
        assert "Zwiastun" not in content


class TestQueryBudget:
    def test_full_page_uses_bounded_queries(self, client, django_assert_max_num_queries):
        """Populated detail page: movie + 3 M2M prefetches + screenings + hall select_related.
        Budget cap 6 absorbs harness overhead; regression triggers when prefetch_related drops
        a relation or someone adds an unprefetched iterator in the template."""
        movie = MovieFactory()
        movie.genres.add(GenreFactory(), GenreFactory())
        movie.actors.add(ActorFactory(), ActorFactory(), ActorFactory())
        movie.directors.add(DirectorFactory(), DirectorFactory())
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=1))
        ScreeningFactory(movie=movie, start_time=timezone.now() + timedelta(days=2))

        with django_assert_max_num_queries(6):
            client.get(f"/movies/{movie.pk}/")
