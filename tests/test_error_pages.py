from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import translation
from django.views.defaults import server_error

from tests.accounts.factories import UserFactory
from tests.booking.factories import BookingFactory


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
@pytest.mark.django_db
def test_404_renders_custom_template(client):
    resp = client.get("/no-such-url-xyz/")
    assert resp.status_code == 404
    content = resp.content.decode()
    assert "404" in content
    assert "Nie znaleziono strony" in content  # pl default (msgid fallback)


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
@pytest.mark.django_db
def test_403_renders_custom_template(client):
    booking = BookingFactory()  # owned by a fresh user
    client.force_login(UserFactory())  # a different, non-staff user
    resp = client.get(reverse("booking:detail", kwargs={"pk": booking.pk}))
    assert resp.status_code == 403
    assert "Brak dostępu" in resp.content.decode()


def test_500_renders_custom_template():
    # server_error renders 500.html with NO request/context — proves the standalone design.
    with translation.override("pl"):
        resp = server_error(RequestFactory().get("/"))
    assert resp.status_code == 500
    content = resp.content.decode()
    assert "500" in content
    assert "Coś poszło nie tak" in content


def test_error_flash_renders_danger_with_icon():
    # No DB: render base.html directly with an ERROR-level message.
    req = RequestFactory().get("/")
    req.user = AnonymousUser()
    req.resolver_match = SimpleNamespace(url_name="home")
    msg = Message(message_constants.ERROR, "Coś się nie powiodło")
    html = render_to_string("base.html", {"messages": [msg]}, request=req)
    assert "alert-danger" in html  # MESSAGE_TAGS maps ERROR -> danger
    assert "alert-error" not in html  # the old broken class is gone
    assert "✗" in html  # per-level icon
