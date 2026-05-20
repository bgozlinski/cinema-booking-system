from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.cinema.models import Genre

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
