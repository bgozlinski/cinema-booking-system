import pytest
from django.contrib.auth import get_user_model
from django.core import mail

from apps.accounts.api.serializers import RegisterSerializer
from tests.accounts.factories import UserFactory

User = get_user_model()

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/v1/auth/register/"


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


class TestRegisterEndpoint:
    def test_register_creates_inactive_user_sends_email_no_jwt(self, api_client):
        resp = api_client.post(
            REGISTER_URL,
            {
                "email": "trinity@example.com",
                "password": "Str0ng-Passw0rd!",
                "first_name": "Trinity",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert "access" not in resp.data
        assert "refresh" not in resp.data
        assert resp.data["user"]["email"] == "trinity@example.com"
        assert resp.data["detail"]
        user = User.objects.get(email="trinity@example.com")
        assert user.is_active is False
        assert len(mail.outbox) == 1

    def test_duplicate_email_rejected(self, api_client):
        UserFactory(email="dup@example.com")
        resp = api_client.post(
            REGISTER_URL,
            {"email": "dup@example.com", "password": "Str0ng-Passw0rd!"},
            format="json",
        )
        assert resp.status_code == 400
        assert "email" in resp.data

    def test_weak_password_rejected(self, api_client):
        resp = api_client.post(
            REGISTER_URL,
            {"email": "weak@example.com", "password": "123"},
            format="json",
        )
        assert resp.status_code == 400
        assert "password" in resp.data

    def test_missing_fields_rejected(self, api_client):
        resp = api_client.post(REGISTER_URL, {}, format="json")
        assert resp.status_code == 400


TOKEN_URL = "/api/v1/auth/token/"
REFRESH_URL = "/api/v1/auth/token/refresh/"


class TestTokenEndpoint:
    def test_active_user_obtains_tokens(self, api_client):
        UserFactory(email="active@example.com", password="test1234")
        resp = api_client.post(
            TOKEN_URL,
            {"email": "active@example.com", "password": "test1234"},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_inactive_user_rejected(self, api_client):
        UserFactory(email="pending@example.com", password="test1234", inactive=True)
        resp = api_client.post(
            TOKEN_URL,
            {"email": "pending@example.com", "password": "test1234"},
            format="json",
        )
        assert resp.status_code == 401

    def test_wrong_password_rejected(self, api_client):
        UserFactory(email="active2@example.com", password="test1234")
        resp = api_client.post(
            TOKEN_URL,
            {"email": "active2@example.com", "password": "wrong"},
            format="json",
        )
        assert resp.status_code == 401

    def test_refresh_returns_new_access(self, api_client):
        UserFactory(email="refresh@example.com", password="test1234")
        tokens = api_client.post(
            TOKEN_URL,
            {"email": "refresh@example.com", "password": "test1234"},
            format="json",
        ).data
        resp = api_client.post(REFRESH_URL, {"refresh": tokens["refresh"]}, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data


ME_URL = "/api/v1/auth/me/"


class TestMeEndpoint:
    def test_authenticated_user_sees_own_data(self, auth_client):
        user = UserFactory(email="me@example.com", first_name="Me")
        resp = auth_client(user).get(ME_URL)
        assert resp.status_code == 200
        assert resp.data["email"] == "me@example.com"
        assert resp.data["first_name"] == "Me"
        assert resp.data["is_staff"] is False
        assert set(resp.data) == {"id", "email", "first_name", "last_name", "is_staff"}

    def test_anonymous_rejected(self, api_client):
        resp = api_client.get(ME_URL)
        assert resp.status_code == 401
