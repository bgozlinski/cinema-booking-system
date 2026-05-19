from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

User = get_user_model()


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
