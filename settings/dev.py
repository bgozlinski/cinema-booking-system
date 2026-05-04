"""Development profile — DEBUG=True, lokalna baza, wyższa verbosity."""

from settings.base import *  # noqa: F401, F403

# Force DEBUG on regardless of .env (dev profile invariant)
DEBUG = True

# Allow localhost variants
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
