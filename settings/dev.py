import sys

from settings.base import *

# Force DEBUG on regardless of .env (dev profile invariant)
DEBUG = True

# Allow localhost variants
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Emails print to runserver's stdout — copy the activation link from terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if "pytest" not in sys.modules:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware"),
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    INTERNAL_IPS = ["127.0.0.1"]
