import re

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_navbar_repertuar_links_to_home(client):
    response = client.get("/")
    content = response.content.decode()

    match = re.search(r"<a[^>]*>\s*Repertuar\s*</a>", content)
    assert match is not None, "Repertuar nav anchor not found"
    anchor = match.group(0)
    assert 'href="/"' in anchor, f"Repertuar should link to /, got: {anchor}"
    assert "disabled" not in anchor, f"Repertuar should not be disabled, got: {anchor}"
