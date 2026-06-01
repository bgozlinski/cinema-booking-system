"""Prometheus metrics endpoint + middleware wiring (django-prometheus)."""

import pytest
from django.conf import settings


@pytest.mark.django_db
def test_metrics_endpoint_returns_prometheus_exposition(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response["Content-Type"]
    body = response.content.decode()
    # Default process/python collectors are always present in the exposition.
    assert "python_info" in body


@pytest.mark.django_db
def test_metrics_endpoint_records_django_http_metrics(client):
    # Hitting a view should register django-prometheus HTTP middleware metrics.
    client.get("/healthz")
    body = client.get("/metrics").content.decode()

    assert "django_http_requests_total_by_method_total" in body


def test_prometheus_middleware_is_first_and_last():
    assert settings.MIDDLEWARE[0].endswith("PrometheusBeforeMiddleware")
    assert settings.MIDDLEWARE[-1].endswith("PrometheusAfterMiddleware")
