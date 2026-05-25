import pytest
from django.conf import settings
from django.test import override_settings

from tests.accounts.factories import UserFactory

pytestmark = pytest.mark.django_db

MOVIES_URL = "/api/v1/movies/"
TOKEN_URL = "/api/v1/auth/token/"

# Shrink every rate but keep the rest of the REST_FRAMEWORK config intact.
THROTTLED = {
    **settings.REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"anon": "2/min", "user": "2/min", "auth": "2/min"},
}


@override_settings(REST_FRAMEWORK=THROTTLED)
def test_anon_throttled(api_client):
    assert api_client.get(MOVIES_URL).status_code == 200
    assert api_client.get(MOVIES_URL).status_code == 200
    assert api_client.get(MOVIES_URL).status_code == 429  # AnonRateThrottle (IP-keyed)


@override_settings(REST_FRAMEWORK=THROTTLED)
def test_user_throttled(auth_client):
    client = auth_client(UserFactory())
    assert client.get(MOVIES_URL).status_code == 200
    assert client.get(MOVIES_URL).status_code == 200
    assert client.get(MOVIES_URL).status_code == 429  # UserRateThrottle (user-keyed)


@override_settings(REST_FRAMEWORK=THROTTLED)
def test_auth_scope_throttled(api_client):
    # Throttling runs in initial() before auth, so bad-credential posts still count.
    payload = {"email": "nobody@example.com", "password": "wrong"}
    assert api_client.post(TOKEN_URL, payload, format="json").status_code in (200, 401)
    api_client.post(TOKEN_URL, payload, format="json")
    assert api_client.post(TOKEN_URL, payload, format="json").status_code == 429


def test_within_limit_not_throttled(api_client):
    # Real rates (anon 100/h) — a single request is not throttled.
    assert api_client.get(MOVIES_URL).status_code == 200
