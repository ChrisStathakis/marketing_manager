"""Django settings for social-media-manager."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env before anything reads os.environ. Note: a directory is not
# a valid dotenv path, so it must point at the file itself.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    # local
    "campaigns",
    "channels",
    "content",
    "ads",
    "results",
    "plans",
    "suggestions",
    "integrations",
    "google_sync",
    "shop",
    "growth",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# Database: SQLite for dev. For Postgres set DATABASE_URL, e.g.
# DATABASE_URL=postgres://user:pass@localhost:5432/dbname
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES["default"] = dj_database_url.parse(
        os.environ["DATABASE_URL"], conn_max_age=600, conn_health_checks=True
    )

# Passwords are intentionally unrestricted: this is a small single-admin tool
# and the operator asked for simple passwords. Any non-empty value is accepted.
AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# The public site the growth tools read from. Read-only: this app never writes
# to catchandstats.com, it only shapes the public JSON and links back to it.
CATCHANDSTATS_SITE_URL = os.environ.get("CATCHANDSTATS_SITE_URL", "https://catchandstats.com")
CATCHANDSTATS_API_BASE = os.environ.get("CATCHANDSTATS_API_BASE", "https://catchandstats.com/api")

# Instagram audience research (comments on public posts). Off by default unless a
# sessionid is stored: it uses Instagram's private endpoints with a logged-in
# cookie, which is not official API usage. See docs/guides/… .
INSTAGRAM_SCRAPER_ENABLED = os.environ.get("INSTAGRAM_SCRAPER_ENABLED", "True").lower() in ("1", "true", "yes")
INSTAGRAM_API_BASE = os.environ.get("INSTAGRAM_API_BASE", "https://www.instagram.com")
INSTAGRAM_TIMEOUT = int(os.environ.get("INSTAGRAM_TIMEOUT", "20"))
INSTAGRAM_MAX_COMMENTS = int(os.environ.get("INSTAGRAM_MAX_COMMENTS", "500"))
INSTAGRAM_PROXY = os.environ.get("INSTAGRAM_PROXY") or None

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}

# CORS (dev default: allow all). For deploy set DJANGO_CORS_ALLOW_ALL=False
# and list origins in DJANGO_CORS_ORIGINS (comma-separated).
CORS_ALLOW_ALL_ORIGINS = os.environ.get("DJANGO_CORS_ALLOW_ALL", "True").lower() in ("1", "true", "yes")
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("DJANGO_CORS_ORIGINS", "").split(",") if o.strip()]

# Auth policy. Registration is open while the instance has no users yet (the
# first account becomes the admin); afterwards it is opt-in via
# DJANGO_ALLOW_REGISTRATION=True.
ALLOW_REGISTRATION = os.environ.get("DJANGO_ALLOW_REGISTRATION", "False").lower() in ("1", "true", "yes")

# SimpleJWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "7"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
}
