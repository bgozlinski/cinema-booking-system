from pathlib import Path

import environ

# ─── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Environment ────────────────────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    LANGUAGE_CODE=(str, "pl"),
    TIME_ZONE=(str, "Europe/Warsaw"),
    SEED_DB_DEFAULT_PASSWORD=(str, "test1234"),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
SEED_DB_DEFAULT_PASSWORD = env("SEED_DB_DEFAULT_PASSWORD")

# ─── Application definition ─────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.cinema",
    "apps.payments",
    "apps.booking",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "settings.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "settings.wsgi.application"

# ─── Auth ───────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ─── Database (default — overridden in dev/prod) ────────────────────────────
DATABASES = {"default": env.db("DATABASE_URL")}

# ─── Localization ───────────────────────────────────────────────────────────
LANGUAGE_CODE = env("LANGUAGE_CODE")
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

# ─── Static ─────────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Media (user uploads — Actor/Director photos, Movie posters) ────────────
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─── Auth URLs ──────────────────────────────────────────────────────────────
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"


# ─── Email ──────────────────────────────────────────────────────────────────
# Activation tokens reuse Django's PASSWORD_RESET_TIMEOUT (default 3 days = 259200s).
# Single timeout for all token-based auth flows — no separate setting.
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@kinomania.local")


# ─── Stripe ────────────────────────────────────────────────────────────────
STRIPE_API_KEY = env("STRIPE_API_KEY", default="")
BASE_URL = env("BASE_URL", default="http://localhost:8000")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
