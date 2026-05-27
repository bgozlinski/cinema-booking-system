"""US-42: regression guard for production security hardening (settings.prod)."""

import importlib


def test_prod_settings_are_hardened():
    prod = importlib.import_module("settings.prod")

    assert prod.DEBUG is False
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS >= 31536000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_PRELOAD is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.X_FRAME_OPTIONS == "DENY"
    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_prod_has_static_root_for_collectstatic():
    prod = importlib.import_module("settings.prod")

    assert hasattr(prod, "STATIC_ROOT"), "STATIC_ROOT missing — collectstatic will fail"
    assert prod.STATIC_ROOT.name == "staticfiles"
    # STATIC_ROOT (collect target) must differ from the source dirs
    assert prod.STATIC_ROOT not in prod.STATICFILES_DIRS
