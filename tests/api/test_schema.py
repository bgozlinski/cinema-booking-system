from io import StringIO

from django.core.management import call_command


def test_schema_generates_without_warnings():
    # --fail-on-warn raises SchemaGenerationError on any warning; --validate checks the spec.
    call_command("spectacular", "--validate", "--fail-on-warn", stdout=StringIO())
