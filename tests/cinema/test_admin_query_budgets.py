"""Per-admin changelist query budget tests (US-17 / FR-perf).

Each ModelAdmin in apps/cinema/admin.py is hit through its changelist URL with
a populated DB and budgeted via django_assert_max_num_queries. Caps are
data-driven: started loose during US-17 implementation, tightened after measuring
the actual query count post-refactor.

The N+1 risk lives in custom display helpers (movies_count, screenings_count,
genres_list). Without get_queryset override these helpers spawn a query per row.
After refactor (annotate(Count(...)) + prefetch_related where needed) the count
is loaded once at the queryset level.
"""

import pytest
from django.urls import reverse

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory
from tests.cinema.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    HallFactory,
    MovieFactory,
    ScreeningFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    """Logged-in superuser. Local to this module — central conftest deferred
    until a second test file needs admin_client (US-28 booking admin most likely)."""
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    return client


class TestGenreAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 genres x ~3 movies each. Without get_queryset override, movies_count
        helper triggers 1 query per row (12 N+1). After refactor: 1 annotate query
        absorbed into the changelist's main fetch."""
        for _ in range(12):
            genre = GenreFactory()
            for _ in range(3):
                movie = MovieFactory()
                movie.genres.add(genre)

        url = reverse("admin:cinema_genre_changelist")

        # Cap 12 — post-refactor educated guess (admin baseline ~10 + 1 annotate + 1 buffer).
        # Tighten after measurement.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200


class TestHallAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 halls x ~2 screenings each. Without get_queryset override,
        screenings_count helper triggers 1 query per row (12 N+1)."""
        for _ in range(12):
            hall = HallFactory()
            ScreeningFactory.create_batch(2, hall=hall)

        url = reverse("admin:cinema_hall_changelist")
        # Cap 12 — admin baseline + 1 annotate + 1 buffer. Tighten after measurement.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200


class TestActorAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 actors x ~2 movies each. movies_count helper is N+1 per row."""
        for _ in range(12):
            actor = ActorFactory()
            for _ in range(2):
                movie = MovieFactory()
                movie.actors.add(actor)

        url = reverse("admin:cinema_actor_changelist")
        # Cap 12 — admin baseline + 1 annotate + 1 buffer. Tighten after measurement.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200


class TestDirectorAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 directors x ~2 movies each. movies_count helper is N+1 per row."""
        for _ in range(12):
            director = DirectorFactory()
            for _ in range(2):
                movie = MovieFactory()
                movie.directors.add(director)

        url = reverse("admin:cinema_director_changelist")
        # Cap 12 — admin baseline + 1 annotate + 1 buffer. Tighten after measurement.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200


class TestMovieAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 movies x ~3 genres x ~2 screenings. Two N+1 helpers (screenings_count
        + genres_list) without get_queryset = 24 extra queries on top of admin
        baseline. After refactor: 1 annotate + 1 prefetch + admin baseline."""
        for _ in range(12):
            movie = MovieFactory()
            for _ in range(3):
                movie.genres.add(GenreFactory())
            ScreeningFactory.create_batch(2, movie=movie)

        url = reverse("admin:cinema_movie_changelist")
        # Cap 15: admin baseline (~10) + 1 annotate + 1 prefetch + 1 list_filter dropdown
        # + 2 buffer. Tighten after measurement.
        with django_assert_max_num_queries(15):
            response = admin_client.get(url)
            assert response.status_code == 200


class TestScreeningAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 screenings x 2 active-PENDING bookings. available/booked_seats_display
        call booked_seats_count() — without get_queryset annotate that's a query per
        row. After annotate + select_related(movie, hall): one main fetch."""
        for _ in range(12):
            screening = ScreeningFactory()
            BookingFactory.create_batch(2, screening=screening)

        url = reverse("admin:cinema_screening_changelist")
        # Cap 12: admin baseline + 1 annotate + select_related joins + buffer.
        # Tighten after measurement.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200


class TestBookingAdminQueryBudget:
    def test_changelist_uses_bounded_queries(self, admin_client, django_assert_max_num_queries):
        """12 bookings. __str__ (movie title) + user + total_price (screening.price)
        are N+1 without select_related("user", "screening__movie")."""
        for _ in range(12):
            BookingFactory()

        url = reverse("admin:booking_booking_changelist")
        # Cap 12: admin baseline + select_related joins + buffer. Tighten after measurement.
        with django_assert_max_num_queries(12):
            response = admin_client.get(url)
            assert response.status_code == 200
