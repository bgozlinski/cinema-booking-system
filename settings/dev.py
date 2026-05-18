from settings.base import *

# Force DEBUG on regardless of .env (dev profile invariant)
DEBUG = True

# Allow localhost variants
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Emails print to runserver's stdout — copy the activation link from terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
