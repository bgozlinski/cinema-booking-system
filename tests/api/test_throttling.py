import pytest
from rest_framework.throttling import SimpleRateThrottle

from tests.accounts.factories import UserFactory

pytestmark = pytest.mark.django_db

MOVIES_URL = "/api/v1/movies/"
TOKEN_URL = "/api/v1/auth/token/"


@pytest.fixture
def shrink_rates(monkeypatch):
    # NOTE: override_settings(REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": ...}) does NOT work
    # here — SimpleRateThrottle.THROTTLE_RATES is a class attribute bound when the throttling
    # module is first imported, so the override never reaches it (and isolated vs full-suite
    # runs differ by import timing). Patch the class attribute the throttles actually read;
    # monkeypatch restores it after the test.
    monkeypatch.setattr(
        SimpleRateThrottle,
        "THROTTLE_RATES",
        {"anon": "2/min", "user": "2/min", "auth": "2/min"},
    )


def test_anon_throttled(api_client, shrink_rates):
    assert api_client.get(MOVIES_URL).status_code == 200
    assert api_client.get(MOVIES_URL).status_code == 200
    assert api_client.get(MOVIES_URL).status_code == 429  # AnonRateThrottle (IP-keyed)


def test_user_throttled(auth_client, shrink_rates):
    client = auth_client(UserFactory())
    assert client.get(MOVIES_URL).status_code == 200
    assert client.get(MOVIES_URL).status_code == 200
    assert client.get(MOVIES_URL).status_code == 429  # UserRateThrottle (user-keyed)


def test_auth_scope_throttled(api_client, shrink_rates):
    # Throttling runs in initial() before auth, so bad-credential posts still count.
    payload = {"email": "nobody@example.com", "password": "wrong"}
    assert api_client.post(TOKEN_URL, payload, format="json").status_code in (200, 401)
    api_client.post(TOKEN_URL, payload, format="json")
    assert api_client.post(TOKEN_URL, payload, format="json").status_code == 429


def test_within_limit_not_throttled(api_client):
    # Real rates (anon 100/h) — a single request is not throttled.
    assert api_client.get(MOVIES_URL).status_code == 200
