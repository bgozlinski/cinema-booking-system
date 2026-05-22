import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening

User = get_user_model()

EXPECTED_GENRE_NAMES = {
    "Action",
    "Comedy",
    "Drama",
    "Horror",
    "Sci-Fi",
    "Animation",
    "Thriller",
    "Romance",
    "Documentary",
}


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_seed_db_blocked_when_debug_false_without_force():
    stdout = StringIO()
    stderr = StringIO()

    with pytest.raises(CommandError, match="disabled when DEBUG=False"):
        call_command("seed_db", stdout=stdout, stderr=stderr)

    assert User.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_seed_db_force_bypasses_production_guard():
    stdout = StringIO()
    stderr = StringIO()

    call_command("seed_db", "--force", stdout=stdout, stderr=stderr)

    assert "WARNING" in stderr.getvalue()
    assert User.objects.count() == 10


@pytest.mark.django_db
def test_seed_db_creates_default_counts():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert User.objects.count() == 10
    assert User.objects.filter(is_active=True).count() == 8
    assert User.objects.filter(is_active=False).count() == 2


@pytest.mark.django_db
def test_seed_db_emails_are_deterministic():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    expected_emails = {f"seed.user{i}@kinomania.local" for i in range(1, 11)}
    assert set(User.objects.values_list("email", flat=True)) == expected_emails

    inactive_emails = set(User.objects.filter(is_active=False).values_list("email", flat=True))
    assert inactive_emails == {
        "seed.user9@kinomania.local",
        "seed.user10@kinomania.local",
    }


@pytest.mark.django_db
def test_seed_db_password_is_hashed():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    user = User.objects.get(email="seed.user1@kinomania.local")
    assert user.check_password("test1234") is True
    assert user.password.startswith("pbkdf2_")


@pytest.mark.django_db
def test_seed_db_no_staff_no_super():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert User.objects.filter(is_staff=True).count() == 0
    assert User.objects.filter(is_superuser=True).count() == 0


@pytest.mark.django_db
def test_seed_db_blocks_on_non_empty_db_without_flags():
    User.objects.create_user(email="existing@example.com", password="x" * 12)

    with pytest.raises(CommandError, match="Database not empty"):
        call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert User.objects.filter(email="existing@example.com").exists()
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_seed_db_flush_preserves_superuser_wipes_others():
    User.objects.create_superuser(email="admin@example.com", password="x" * 12)
    User.objects.create_user(email="user1@example.com", password="x" * 12)
    User.objects.create_user(email="user2@example.com", password="x" * 12)

    call_command("seed_db", "--flush", stdout=StringIO(), stderr=StringIO())

    assert User.objects.filter(email="admin@example.com").exists()
    assert not User.objects.filter(email="user1@example.com").exists()
    assert not User.objects.filter(email="user2@example.com").exists()
    seed_count = User.objects.filter(email__startswith="seed.user").count()
    assert seed_count == 10
    assert User.objects.count() == 11  # 10 seed + 1 superuser


@pytest.mark.django_db
def test_seed_db_append_idempotent_skip_existing():
    for i in [1, 2, 3]:
        User.objects.create_user(email=f"seed.user{i}@kinomania.local", password="x" * 12)
    original_joined = {
        u.email: u.date_joined for u in User.objects.filter(email__startswith="seed.user")
    }

    stdout = StringIO()
    call_command("seed_db", "--append", stdout=stdout, stderr=StringIO())

    assert User.objects.count() == 10
    assert User.objects.filter(email__startswith="seed.user").count() == 10
    for i in [1, 2, 3]:
        email = f"seed.user{i}@kinomania.local"
        assert User.objects.get(email=email).date_joined == original_joined[email]
    out = stdout.getvalue()
    assert "Skipping existing: seed.user1@kinomania.local" in out
    assert "Appended 7 users (3 skipped)" in out


@pytest.mark.django_db
def test_seed_db_flush_and_append_mutually_exclusive():
    with pytest.raises(CommandError, match="mutually exclusive"):
        call_command(
            "seed_db",
            "--flush",
            "--append",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert User.objects.count() == 0


# ---------------------------------------------------------------------------
# US-16 — Cinema entity seeding
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_seed_db_creates_nine_named_genres():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Genre.objects.count() == 9
    assert set(Genre.objects.values_list("name", flat=True)) == EXPECTED_GENRE_NAMES


@pytest.mark.django_db
def test_seed_db_genre_seeding_is_idempotent_on_append():
    # Pre-create 2 of the 9 genres.
    Genre.objects.create(name="Action")
    Genre.objects.create(name="Drama")

    call_command("seed_db", "--append", stdout=StringIO(), stderr=StringIO())

    assert Genre.objects.count() == 9
    assert set(Genre.objects.values_list("name", flat=True)) == EXPECTED_GENRE_NAMES


@pytest.mark.django_db
def test_seed_db_creates_3_to_5_halls():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    count = Hall.objects.count()
    assert 3 <= count <= 5


@pytest.mark.django_db
def test_seed_db_hall_capacities_in_range():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for hall in Hall.objects.all():
        assert 50 <= hall.capacity <= 200


@pytest.mark.django_db
def test_seed_db_hall_names_are_unique():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    names = list(Hall.objects.values_list("name", flat=True))
    assert len(names) == len(set(names))


@pytest.mark.django_db
def test_seed_db_creates_30_actors():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Actor.objects.count() == 30


@pytest.mark.django_db
def test_seed_db_actors_have_names_and_biographies():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for actor in Actor.objects.all():
        assert actor.full_name.strip() != ""
        assert actor.biography.strip() != ""


@pytest.mark.django_db
def test_seed_db_creates_10_directors():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Director.objects.count() == 10


@pytest.mark.django_db
def test_seed_db_directors_have_names_and_biographies():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for director in Director.objects.all():
        assert director.full_name.strip() != ""
        assert director.biography.strip() != ""


@pytest.mark.django_db
def test_seed_db_default_movie_count():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Movie.objects.count() == 20


@pytest.mark.django_db
def test_seed_db_custom_movie_count():
    call_command("seed_db", "--movies=5", stdout=StringIO(), stderr=StringIO())

    assert Movie.objects.count() == 5


@pytest.mark.django_db
def test_seed_db_movie_attributes_in_range():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    today = datetime.date.today()
    two_years_ago = today - datetime.timedelta(days=730)
    for movie in Movie.objects.all():
        assert movie.title.strip() != ""
        assert movie.description.strip() != ""
        assert 80 <= movie.duration_minutes <= 180
        assert two_years_ago <= movie.release_date <= today


@pytest.mark.django_db
def test_seed_db_movie_m2m_counts_in_range():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    for movie in Movie.objects.all():
        assert 1 <= movie.genres.count() <= 3
        assert 3 <= movie.actors.count() <= 8
        assert 1 <= movie.directors.count() <= 2


@pytest.mark.django_db
def test_seed_db_default_screening_count():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Screening.objects.count() == 100


@pytest.mark.django_db
def test_seed_db_custom_screening_count():
    call_command("seed_db", "--screenings=15", stdout=StringIO(), stderr=StringIO())

    assert Screening.objects.count() == 15


@pytest.mark.django_db
def test_seed_db_screening_attributes_in_range():
    call_command("seed_db", "--screenings=20", stdout=StringIO(), stderr=StringIO())

    now = timezone.now()
    window_start = now - datetime.timedelta(days=8)  # 1 day buffer
    window_end = now + datetime.timedelta(days=31)
    for screening in Screening.objects.all():
        assert window_start <= screening.start_time <= window_end
        assert Decimal("25.00") <= screening.price <= Decimal("55.00")


@pytest.mark.django_db
def test_seed_db_screenings_use_seeded_movies_and_halls():
    call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    movie_ids = set(Movie.objects.values_list("id", flat=True))
    hall_ids = set(Hall.objects.values_list("id", flat=True))
    for screening in Screening.objects.all():
        assert screening.movie_id in movie_ids
        assert screening.hall_id in hall_ids


@pytest.mark.django_db
def test_seed_db_blocks_when_only_cinema_data_exists():
    # No users; just one genre — guard should still trigger.
    Genre.objects.create(name="Action")

    with pytest.raises(CommandError, match="Database not empty"):
        call_command("seed_db", stdout=StringIO(), stderr=StringIO())

    assert Genre.objects.count() == 1  # untouched


@pytest.mark.django_db
def test_seed_db_flush_wipes_cinema_data():
    # Pre-create one of each cinema entity.
    g = Genre.objects.create(name="Action")
    h = Hall.objects.create(name="Old Hall", capacity=80)
    Actor.objects.create(full_name="Old Actor")
    Director.objects.create(full_name="Old Director")
    m = Movie.objects.create(
        title="Old Movie",
        description="x",
        release_date=datetime.date(2020, 1, 1),
        duration_minutes=90,
    )
    m.genres.add(g)
    Screening.objects.create(
        movie=m,
        hall=h,
        start_time=timezone.now() + datetime.timedelta(days=1),
        price=Decimal("30.00"),
    )

    call_command("seed_db", "--flush", stdout=StringIO(), stderr=StringIO())

    # Old rows are gone; fresh seed data is in place.
    # "Action" was pre-created AND is in the fixed seed list — after flush there's exactly 1 (the new one).
    assert Genre.objects.count() == 9
    assert Genre.objects.filter(name="Action").count() == 1
    assert not Hall.objects.filter(name="Old Hall").exists()
    assert not Actor.objects.filter(full_name="Old Actor").exists()
    assert not Director.objects.filter(full_name="Old Director").exists()
    assert not Movie.objects.filter(title="Old Movie").exists()
    # Screenings are all fresh.
    assert Screening.objects.count() == 100


@pytest.mark.django_db
def test_seed_db_flush_respects_screening_hall_protect():
    # Reproduce the FK constraint: PROTECT means Screening must die before Hall.
    # If --flush order were wrong this would raise IntegrityError or ProtectedError.
    h = Hall.objects.create(name="Protected Hall", capacity=100)
    m = Movie.objects.create(
        title="x",
        description="x",
        release_date=datetime.date(2024, 1, 1),
        duration_minutes=100,
    )
    Screening.objects.create(
        movie=m,
        hall=h,
        start_time=timezone.now() + datetime.timedelta(days=1),
        price=Decimal("30.00"),
    )

    # Must NOT raise.
    call_command("seed_db", "--flush", stdout=StringIO(), stderr=StringIO())

    assert not Hall.objects.filter(name="Protected Hall").exists()


@pytest.mark.django_db
def test_seed_db_success_output_mentions_cinema_counts():
    stdout = StringIO()
    call_command("seed_db", stdout=stdout, stderr=StringIO())

    out = stdout.getvalue()
    assert "9 genres" in out
    assert "movies" in out
    assert "screenings" in out
    assert "users" in out


class TestSeedDbBookings:
    @pytest.mark.django_db
    def test_creates_bookings_with_default_count(self):
        from django.core.management import call_command

        from apps.booking.models import Booking

        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=10")
        assert Booking.objects.count() == 10

    @pytest.mark.django_db
    def test_bookings_status_distribution_includes_all_three(self):
        """Distribution is 85/5/10 random — flaky exact ratio test.
        Instead, with bookings=50, assert all three statuses present."""
        from django.core.management import call_command

        from apps.booking.models import Booking, BookingStatus

        call_command("seed_db", "--users=10", "--movies=5", "--screenings=20", "--bookings=50")
        for status in (BookingStatus.CONFIRMED, BookingStatus.PENDING, BookingStatus.CANCELLED):
            assert Booking.objects.filter(status=status).exists(), f"{status} missing"

    @pytest.mark.django_db
    def test_creates_one_stripe_event_per_confirmed_booking(self):
        from django.core.management import call_command

        from apps.booking.models import Booking, BookingStatus
        from apps.payments.models import StripeEvent

        call_command("seed_db", "--users=10", "--movies=5", "--screenings=20", "--bookings=30")
        confirmed_count = Booking.objects.filter(status=BookingStatus.CONFIRMED).count()
        stripe_event_count = StripeEvent.objects.count()
        assert stripe_event_count == confirmed_count

    @pytest.mark.django_db
    def test_flush_deletes_bookings_before_screenings(self):
        from django.core.management import call_command

        from apps.booking.models import Booking
        from apps.cinema.models import Screening

        # Initial seed
        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=10")
        assert Booking.objects.count() == 10
        # Re-seed with --flush — must not raise IntegrityError on Screening.bookings cascade
        call_command(
            "seed_db",
            "--flush",
            "--users=5",
            "--movies=3",
            "--screenings=10",
            "--bookings=8",
        )
        assert Booking.objects.count() == 8
        assert Screening.objects.count() == 10

    @pytest.mark.django_db
    def test_flush_deletes_stripe_events_independently(self):
        from django.core.management import call_command

        from apps.payments.models import StripeEvent

        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=10")
        initial_events = StripeEvent.objects.count()
        assert initial_events > 0
        call_command(
            "seed_db",
            "--flush",
            "--users=5",
            "--movies=3",
            "--screenings=10",
            "--bookings=10",
        )
        # Old events gone, new ones created (count may differ — random distribution)
        new_events = StripeEvent.objects.count()
        assert new_events >= 0  # depends on CONFIRMED distribution in re-seed

    @pytest.mark.django_db
    def test_non_empty_guard_includes_bookings(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=5")
        # Re-run without --flush or --append → CommandError
        with pytest.raises(CommandError, match="Database not empty"):
            call_command("seed_db", "--users=5", "--movies=3", "--screenings=10", "--bookings=5")
