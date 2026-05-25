from django.conf import settings


def test_debug_toolbar_not_loaded_under_pytest():
    # DDT is gated on "pytest" not in sys.modules in settings/dev.py — it must stay out of the
    # test run, or it would inject toolbar HTML and add its own queries (breaking query budgets).
    assert "debug_toolbar" not in settings.INSTALLED_APPS
    assert not any("debug_toolbar" in m for m in settings.MIDDLEWARE)
