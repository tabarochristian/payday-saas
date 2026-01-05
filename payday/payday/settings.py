import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
import sentry_sdk
import logging

# 1. INITIALIZATION & HELPERS
# --------------------------------------------------------------------------
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

def env(key: str, default=None, cast=str):
    """Robust env helper with type casting, safe defaults, and logging for missing vars."""
    if key not in os.environ:
        if default is not None:
            logging.warning(f"Environment variable '{key}' not set. Falling back to default: {default}")
        else:
            logging.warning(f"Environment variable '{key}' not set and no default provided.")
    value = os.getenv(key, default)
    if value is None:
        return None
    if cast is bool:
        return str(value).lower().strip() in ("true", "1", "t", "y", "yes", "on")
    if cast is list:
        return [item.strip() for item in str(value).split(",") if item.strip()]
    try:
        return cast(value)
    except (ValueError, TypeError):
        return value

# 2. CORE SECURITY & INFRASTRUCTURE
# --------------------------------------------------------------------------
DEBUG = env("DEBUG", default=False, cast=bool)  # Safer default for production

# SECRET_KEY is required – no default fallback
SECRET_KEY = env("SECRET_KEY", default="django-insecure-06ypcmaqfpku2z89w08jpa0o%5uy9vwsq2@7i)ierd=!jf@+g")
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=list)

ROOT_URLCONF = "payday.urls"
WSGI_APPLICATION = "payday.wsgi.application"
ASGI_APPLICATION = "payday.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === ENV INPUT ===
REDIS_URL = env("REDIS_URL")  # single switch: production if set

# === CACHE (always in-memory) ===
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "payday-local-cache",
        "KEY_PREFIX": "payday_cache",
        "TIMEOUT": 300,
    }
}
DEFAULT_CACHE_ALIAS = "default"

# === CHANNELS ===
CHANNEL_LAYERS_BACKEND = "channels_redis.core.RedisChannelLayer" if REDIS_URL else "channels.layers.InMemoryChannelLayer"
CHANNEL_LAYERS = {
    "default": {
        "CONFIG": {"hosts": [REDIS_URL]} if REDIS_URL else {},
        "BACKEND": CHANNEL_LAYERS_BACKEND,
    }
}

# === CELERY ===
CELERY_RESULT_BACKEND = REDIS_URL or "django-db"
CELERY_BROKER_URL = REDIS_URL or "django"

# Local dev: eager mode (no worker)
CELERY_TASK_ALWAYS_EAGER = not bool(REDIS_URL)
CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER

# 4. APPS & MIDDLEWARE
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "daphne",  # ASGI server – must be first
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.gis",

    # Third-party
    "health_check",
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
    "dal",
    "dal_select2",
    "widget_tweaks",
    "tinymce",
    "storages",
    "mathfilters",
    "crispy_forms",
    "crispy_bootstrap5",
    "django_filters",
    "rest_framework",
    "django_json_widget",
    "mapwidgets",
    "djmoney",
    "django_ace",
    "corsheaders",
    "phonenumber_field",
    "django_extensions",
    "django_htmx",
    "djcelery_email",
    "notifications",

    # Project apps
    "api",
    "core",
    "device",
    "leave",
    "payroll",
    "employee",
]

MIDDLEWARE = [
    "core.middleware.TenantMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_currentuser.middleware.ThreadLocalUserMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "core.middleware.SubOrganizationMiddleware",
]

# Debug Toolbar – only in DEBUG mode
if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    try:
        idx = MIDDLEWARE.index("django.middleware.common.CommonMiddleware")
        MIDDLEWARE.insert(idx + 1, "debug_toolbar.middleware.DebugToolbarMiddleware")
    except ValueError:
        pass

# 5. DATABASE & STORAGE
# --------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL", "spatialite:///db.sqlite3"),
        # conn_max_age=env("CONN_MAX_AGE", default=600, cast=int),
    )
}
SPATIALITE_LIBRARY_PATH = env("SPATIALITE_LIBRARY_PATH", default="mod_spatialite")

# Static & Media
STATIC_URL = env("STATIC_URL", default="/static/")
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"

# Unified storage backends
STORAGES = {
    "default": {
        "BACKEND": env(
            "DEFAULT_FILE_STORAGE", default="django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": env(
            "DEFAULT_FILE_STORAGE", default="whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
}

# S3-related settings (only used if storage backend is S3)
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN")
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = None  # Recommended for security

# 6. SECURITY SETTINGS (Fully Hybrid)
# --------------------------------------------------------------------------
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=31536000 if not DEBUG else 0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG, cast=bool)
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD", default=not DEBUG, cast=bool)

SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", default=not DEBUG, cast=bool)
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=False, cast=bool)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# 7. TEMPLATES & INTERNATIONALIZATION
# --------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context.base",
            ],
        },
    },
]

AUTH_USER_MODEL = "core.user"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "login"
AUTHENTICATION_BACKENDS = ["payday.backends.auth.AuthBackend"]

TIME_ZONE = env("TIME_ZONE", "Africa/Kinshasa")
LANGUAGE_CODE = env("LANGUAGE_CODE", "fr")
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGES = [("fr", "French")]

# 8. THIRD-PARTY CONFIGURATIONS
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

INTERNAL_IPS = ["127.0.0.1", "localhost"]

MAPBOX_ACCESS_TOKEN = env(
    "MAPBOX_ACCESS_TOKEN", 
    "pk.eyJ1Ijoia2FkaXRhaiIsImEiOiJjbHFxbXVqaDYzbTBqMmlvMDZ0dWI5MDdiIn0.n2g5LRYLwomy54PExogsBQ"
)

MAP_WIDGETS = {
    "Mapbox": {
        "accessToken": MAPBOX_ACCESS_TOKEN,
        "PointField": {
            "interactive": {
                "mapOptions": {
                    "zoom": 6,
                    "center": (-4.0383, 21.7587),  # Center of DRC
                },
                "markerFitZoom": 12,
                "GooglePlaceAutocompleteOptions": {
                    "componentRestrictions": {"country": "cd"}
                },
            }
        },
    }
}

# 9. LOGGING
# --------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = env("LOG_LEVEL", default="DEBUG" if DEBUG else "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} [{name}] {module}:{lineno} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple" if DEBUG else "verbose",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",  # Avoid noisy SQL in prod; override with LOG_LEVEL=DEBUG
            "propagate": False,
        },
        "api": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "core": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "payroll": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "device": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "leave": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "employee": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "WARNING",
    },
}

# 10. SENTRY (Error Monitoring)
# --------------------------------------------------------------------------
SENTRY_DSN = env(
    "SENTRY_DSN", 
    "https://39d3aad6a7485437f9f31735eb120682@o4505861077204992.ingest.us.sentry.io/4510658349694976"
)
sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=True)


# 11. Lago API
LAGO_API_KEY = "23e0a6aa-a0a7-4dc9-bec6-e225bf65ec05"
LAGO_API_KEY = os.getenv("LAGO_API_KEY", LAGO_API_KEY)

LAGO_API_URL = "http://lago:3000"
LAGO_API_URL = os.getenv("LAGO_API_URL", LAGO_API_URL)

# ----------------------------------------------------------------------
# Crispy Forms Template Pack
# ----------------------------------------------------------------------
# Place this after the third-party apps or in section 8 (THIRD-PARTY CONFIGURATIONS)
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"  # Optional, for extra safety

# ----------------------------------------------------------------------
# Email backend configuration (Console in dev, SMTP in prod)
# ----------------------------------------------------------------------
# Add this in a new section or after section 8
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
EMAIL_BACKEND = env("EMAIL_BACKEND", EMAIL_BACKEND)

EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="webmaster@localhost")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="webmaster@localhost")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = env("EMAIL_USE_SSL", default=False, cast=bool)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)