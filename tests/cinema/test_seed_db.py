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


@pytest.mark.xfail(reason="seed loop implemented in Task 6", strict=True)
@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_seed_db_force_bypasses_production_guard():
    stdout = StringIO()
    stderr = StringIO()

    call_command("seed_db", "--force", stdout=stdout, stderr=stderr)

    assert "WARNING" in stderr.getvalue()
    assert User.objects.count() == 10
