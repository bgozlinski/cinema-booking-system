import environ

from settings.base import *

env = environ.Env()

DEBUG = False

# SMTP — placeholder, configured per environment via .env.
# Not exercised in M1; real deployment work happens post-M5.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

# --- Security hardening (US-42). Active only under settings.prod. ---
# HTTPS enforcement. Behind a TLS-terminating proxy (Heroku/Render/nginx),
# Django sees plain HTTP, so trust the proxy's X-Forwarded-Proto header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

# Cookies only over HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS — 1 year, include subdomains, allow preload-list submission.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Defense-in-depth headers (explicit even where Django already defaults).
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Django 6 requires the deployment origin to be trusted for CSRF when POSTing
# from forms/admin behind a proxy; without this, every POST 403s. Comma-separated
# in .env (e.g. "https://kinomaniak.bnbg.pl").
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["https://kinomaniak.bnbg.pl"])
