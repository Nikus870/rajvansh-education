import os
import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured


# =========================================================
# BASE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# LOAD .ENV FILE
# =========================================================

env_file = BASE_DIR / ".env"

if env_file.is_file():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if (
                line
                and not line.startswith("#")
                and "=" in line
            ):
                k, v = line.split("=", 1)

                os.environ.setdefault(
                    k.strip(),
                    v.strip().strip("'\"")
                )


# =========================================================
# ENVIRONMENT HELPERS
# =========================================================

def boolean(name, default=False):
    return os.getenv(
        name,
        str(default)
    ).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def listenv(name, default=""):
    return [
        x.strip()
        for x in os.getenv(name, default).split(",")
        if x.strip()
    ]


# =========================================================
# DEBUG
# =========================================================

# Controlled through .env
#
# Development:
# DEBUG=True
#
# Production:
# DEBUG=False

DEBUG = boolean("DEBUG", True)


# =========================================================
# SECRET KEY
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-only-change-this"
)


# =========================================================
# TESTING
# =========================================================

TESTING = (
    "test" in sys.argv
    or "pytest" in sys.modules
)


# Do not allow an insecure SECRET_KEY in production
if not DEBUG and not TESTING:

    if not SECRET_KEY or SECRET_KEY in {
        "dev-only-change-this",
        "change-me-in-production",
    }:

        raise ImproperlyConfigured(
            "SECRET_KEY must be set to a secure, "
            "unique value when DEBUG is False in production."
        )


# =========================================================
# ALLOWED HOSTS
# =========================================================

ALLOWED_HOSTS = listenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost"
)


# =========================================================
# CSRF TRUSTED ORIGINS
# =========================================================

CSRF_TRUSTED_ORIGINS = listenv(
    "CSRF_TRUSTED_ORIGINS"
)


# =========================================================
# INSTALLED APPS
# =========================================================

INSTALLED_APPS = [

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Project Apps
    "apps.core",
    "apps.courses",
    "apps.universities",
    "apps.inquiries",
    "apps.franchise",
    "apps.content",
]


# =========================================================
# AUTHENTICATION
# =========================================================

AUTHENTICATION_BACKENDS = [

    "apps.franchise.backends.EmailOrUsernameBackend",

    "django.contrib.auth.backends.ModelBackend",
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [

    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URL CONFIGURATION
# =========================================================

ROOT_URLCONF = "config.urls"


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [

    {
        "BACKEND":
            "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates"
        ],

        "APP_DIRS": True,

        "OPTIONS": {

            "context_processors": [

                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",

                "apps.core.context_processors.site_context",
            ],
        },
    },
]


# =========================================================
# WSGI
# =========================================================

WSGI_APPLICATION = "config.wsgi.application"


# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    ""
)


if DATABASE_URL.startswith("postgres"):

    import urllib.parse

    u = urllib.parse.urlparse(
        DATABASE_URL
    )

    DATABASES = {

        "default": {

            "ENGINE":
                "django.db.backends.postgresql",

            "NAME":
                u.path.lstrip("/"),

            "USER":
                u.username,

            "PASSWORD":
                u.password,

            "HOST":
                u.hostname,

            "PORT":
                u.port or 5432,
        }
    }

else:

    DATABASES = {

        "default": {

            "ENGINE":
                "django.db.backends.sqlite3",

            "NAME":
                BASE_DIR / "db.sqlite3",
        }
    }


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [

    {
        "NAME":
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },

    {
        "NAME":
            "django.contrib.auth.password_validation.MinimumLengthValidator"
    },

    {
        "NAME":
            "django.contrib.auth.password_validation.CommonPasswordValidator"
    },

    {
        "NAME":
            "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# =========================================================
# STATIC FILES
# =========================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static"
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# =========================================================
# MEDIA FILES
# =========================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# STORAGE
# =========================================================

STORAGES = {

    "default": {
        "BACKEND":
            "django.core.files.storage.FileSystemStorage"
    },

    "staticfiles": {
        "BACKEND":
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)


# =========================================================
# LOGIN / LOGOUT
# =========================================================

LOGIN_URL = "franchise:login"

LOGIN_REDIRECT_URL = "franchise:dashboard"

LOGOUT_REDIRECT_URL = "core:home"


# =========================================================
# FILE UPLOAD LIMIT
# =========================================================

MAX_UPLOAD_SIZE_MB = int(
    os.getenv(
        "MAX_UPLOAD_SIZE_MB",
        "5"
    )
)


# =========================================================
# SECURITY SETTINGS
# =========================================================

SECURE_SSL_REDIRECT = boolean(
    "SECURE_SSL_REDIRECT",
    False
)

SESSION_COOKIE_SECURE = boolean(
    "SESSION_COOKIE_SECURE",
    False
)

CSRF_COOKIE_SECURE = boolean(
    "CSRF_COOKIE_SECURE",
    False
)


# =========================================================
# HSTS
# =========================================================

SECURE_HSTS_SECONDS = (
    31536000
    if not DEBUG
    else 0
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    not DEBUG
)

SECURE_HSTS_PRELOAD = (
    not DEBUG
)


# =========================================================
# SECURITY HEADERS
# =========================================================

SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"


# =========================================================
# EMAIL
# =========================================================

# Currently using console backend for development.
# Change this later when real Gmail SMTP is configured.

EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "no-reply@example.invalid"
)