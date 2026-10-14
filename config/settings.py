import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

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

            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(
                    key.strip(),
                    value.strip().strip("'\""),
                )


# =========================================================
# ENVIRONMENT HELPERS
# =========================================================

def boolean(name, default=False):
    return os.getenv(name, str(default)).lower() in {
        "1", "true", "yes", "on"
    }


def listenv(name, default=""):
    return [
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    ]


# =========================================================
# TESTING
# =========================================================

TESTING = "test" in sys.argv or "pytest" in sys.modules


# =========================================================
# DEBUG
# =========================================================

DEBUG = boolean("DEBUG", TESTING)


# =========================================================
# SECRET KEY
# =========================================================

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this")

if not DEBUG and not TESTING:
    if not SECRET_KEY or SECRET_KEY in {
        "dev-only-change-this",
        "change-me-in-production",
    }:
        raise ImproperlyConfigured(
            "SECRET_KEY must be set to a secure, unique value in production."
        )


# =========================================================
# ALLOWED HOSTS
# =========================================================

ALLOWED_HOSTS = listenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost",
)

if not DEBUG and not TESTING and not os.getenv("ALLOWED_HOSTS"):
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must be configured in production."
    )


# =========================================================
# CSRF TRUSTED ORIGINS
# =========================================================

CSRF_TRUSTED_ORIGINS = listenv("CSRF_TRUSTED_ORIGINS")


# =========================================================
# INSTALLED APPS
# =========================================================

INSTALLED_APPS = [
    "apps.core.admin_config.SuperuserOnlyAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "apps.core",
    "apps.courses",
    "apps.universities",
    "apps.inquiries",
    "apps.franchise",
    "apps.content",
    "apps.students",
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
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DEBUG and not TESTING and not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL must point to the production PostgreSQL database."
    )

if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    parsed_database_url = urlparse(DATABASE_URL)

    if not parsed_database_url.hostname or not parsed_database_url.path.strip("/"):
        raise ImproperlyConfigured(
            "DATABASE_URL must include a host and database name."
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_database_url.path.lstrip("/")),
            "USER": unquote(parsed_database_url.username or ""),
            "PASSWORD": unquote(parsed_database_url.password or ""),
            "HOST": parsed_database_url.hostname,
            "PORT": parsed_database_url.port or 5432,
            "OPTIONS": {
                key: values[-1]
                for key, values in __import__("urllib.parse", fromlist=["parse_qs"])
                .parse_qs(parsed_database_url.query).items()
                if key in {
                    "sslmode",
                    "connect_timeout",
                    "application_name",
                }
            },
        }
    }

elif DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL must use the PostgreSQL postgres:// or postgresql:// scheme."
    )

else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

PASSWORD_RESET_TIMEOUT = 60 * 60


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
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# =========================================================
# MEDIA FILES
# =========================================================

MEDIA_URL = "/media/"

MEDIA_ROOT_ENV = os.getenv("MEDIA_ROOT", "").strip()

if DEBUG or TESTING:
    MEDIA_ROOT = (
        Path(MEDIA_ROOT_ENV)
        if MEDIA_ROOT_ENV
        else BASE_DIR / "media"
    )
else:
    MEDIA_ROOT = (
        Path(MEDIA_ROOT_ENV)
        if MEDIA_ROOT_ENV
        else Path("/tmp/rajvans-media")
    )

    if not MEDIA_ROOT.is_absolute():
        raise ImproperlyConfigured(
            "MEDIA_ROOT must be an absolute directory path."
        )


# =========================================================
# STORAGE
# =========================================================

MEDIA_STORAGE_BACKEND = os.getenv(
    "MEDIA_STORAGE_BACKEND",
    "django.core.files.storage.FileSystemStorage",
)

try:
    MEDIA_STORAGE_OPTIONS = json.loads(
        os.getenv("MEDIA_STORAGE_OPTIONS", "{}")
    )
except json.JSONDecodeError as exc:
    raise ImproperlyConfigured(
        "MEDIA_STORAGE_OPTIONS must be valid JSON."
    ) from exc

if not isinstance(MEDIA_STORAGE_OPTIONS, dict):
    raise ImproperlyConfigured(
        "MEDIA_STORAGE_OPTIONS must be a JSON object."
    )

if (
    not DEBUG
    and not TESTING
    and MEDIA_STORAGE_BACKEND
    == "django.core.files.storage.FileSystemStorage"
):
    storage_location = MEDIA_STORAGE_OPTIONS.get("location")

    if storage_location is not None:
        if (
            not isinstance(storage_location, str)
            or Path(storage_location).resolve()
            != MEDIA_ROOT.resolve()
        ):
            raise ImproperlyConfigured(
                "MEDIA_STORAGE_OPTIONS.location must match MEDIA_ROOT."
            )

STORAGES = {
    "default": {
        "BACKEND": MEDIA_STORAGE_BACKEND,
        "OPTIONS": MEDIA_STORAGE_OPTIONS,
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


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
    os.getenv("MAX_UPLOAD_SIZE_MB", "5")
)


# =========================================================
# SECURITY SETTINGS
# =========================================================

SECURE_SSL_REDIRECT = boolean(
    "SECURE_SSL_REDIRECT",
    not DEBUG,
)

SESSION_COOKIE_SECURE = boolean(
    "SESSION_COOKIE_SECURE",
    not DEBUG,
)

CSRF_COOKIE_SECURE = boolean(
    "CSRF_COOKIE_SECURE",
    not DEBUG,
)

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if boolean("USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )


# =========================================================
# HSTS
# =========================================================

SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG


# =========================================================
# SECURITY HEADERS
# =========================================================

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"


# =========================================================
# EMAIL
# =========================================================

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

EMAIL_USE_TLS = boolean("EMAIL_USE_TLS", not DEBUG)
EMAIL_USE_SSL = boolean("EMAIL_USE_SSL", False)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "no-reply@example.invalid",
)

# SMTP details are validated when an SMTP host is configured.
# If no host is configured, deployment can start, but SMTP email
# sending will not work until valid provider settings are added.
if EMAIL_HOST:
    if EMAIL_BACKEND.endswith("smtp.EmailBackend"):
        if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
            if not DEBUG and not TESTING:
                raise ImproperlyConfigured(
                    "Configure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD "
                    "for SMTP authentication."
                )

        if (
            not DEBUG
            and not TESTING
            and DEFAULT_FROM_EMAIL.endswith("@example.invalid")
        ):
            raise ImproperlyConfigured(
                "Configure DEFAULT_FROM_EMAIL with a verified sender address."
            )

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        "EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled."
    )
