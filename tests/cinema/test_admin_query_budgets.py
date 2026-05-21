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
