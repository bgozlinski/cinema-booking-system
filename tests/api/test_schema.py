from io import StringIO

from django.core.management import call_command


def test_schema_generates_without_warnings():
    # --fail-on-warn raises SchemaGenerationError on any warning; --validate checks the spec.
    call_command("spectacular", "--validate", "--fail-on-warn", stdout=StringIO())


def test_security_scheme_named_bearer_auth(api_client):
    schemes = api_client.get("/api/v1/schema/?format=json").json()["components"]["securitySchemes"]
    assert "bearerAuth" in schemes
    assert schemes["bearerAuth"]["type"] == "http"
    assert schemes["bearerAuth"]["scheme"] == "bearer"
