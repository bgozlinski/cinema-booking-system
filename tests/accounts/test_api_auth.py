import pytest

from apps.accounts.api.serializers import RegisterSerializer

pytestmark = pytest.mark.django_db


class TestRegisterSerializer:
    def test_create_makes_inactive_user_with_hashed_password(self):
        s = RegisterSerializer(
            data={
                "email": "neo@example.com",
                "password": "Str0ng-Passw0rd!",
                "first_name": "Neo",
            }
        )
        assert s.is_valid(), s.errors
        user = s.save()
        assert user.is_active is False
        assert user.email == "neo@example.com"
        assert user.first_name == "Neo"
        assert user.check_password("Str0ng-Passw0rd!")
        assert user.password != "Str0ng-Passw0rd!"

    def test_weak_password_rejected(self):
        s = RegisterSerializer(data={"email": "x@example.com", "password": "123"})
        assert not s.is_valid()
        assert "password" in s.errors

    def test_email_required(self):
        s = RegisterSerializer(data={"password": "Str0ng-Passw0rd!"})
        assert not s.is_valid()
        assert "email" in s.errors
