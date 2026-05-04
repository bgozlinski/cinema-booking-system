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
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ─── Application definition ─────────────────────────────────────────────────
INSTALLED_APPS = [
  "django.contrib.admin",
  "django.contrib.auth",
  "django.contrib.contenttypes",
  "django.contrib.sessions",
  "django.contrib.messages",
  "django.contrib.staticfiles",
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
      "DIRS": [],
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

# ─── Database (default — overridden in dev/prod) ────────────────────────────
DATABASES = {"default": env.db("DATABASE_URL")}

# ─── Localization ───────────────────────────────────────────────────────────
LANGUAGE_CODE = env("LANGUAGE_CODE")
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

# ─── Static / Media (placeholder — wypełnimy w US-09 i FR-15) ───────────────
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
