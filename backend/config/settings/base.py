import os
from importlib.util import find_spec
from pathlib import Path

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BASE_DIR.parent


def env_list(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name, "1" if default else "0").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return int(default)


def env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return float(default)

SECRET_KEY = "unsafe-default-secret-key"
DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

HAS_DAPHNE = find_spec("daphne") is not None
HAS_CHANNELS = find_spec("channels") is not None
HAS_CHANNELS_REDIS = find_spec("channels_redis") is not None

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "apps.core.apps.CoreConfig",
    "apps.users.apps.UsersConfig",
    "apps.catalog.apps.CatalogConfig",
    "apps.vehicles.apps.VehiclesConfig",
    "apps.autocatalog.apps.AutocatalogConfig",
    "apps.compatibility.apps.CompatibilityConfig",
    "apps.marketing.apps.MarketingConfig",
    "apps.seo.apps.SeoConfig",
    "apps.search.apps.SearchConfig",
    "apps.pricing.apps.PricingConfig",
    "apps.supplier_imports.apps.SupplierImportsConfig",
    "apps.backoffice.apps.BackofficeConfig",
    "apps.commerce.apps.CommerceConfig",
    "apps.support.apps.SupportConfig",
]

# Celery workers do not require ASGI dependencies, so avoid failing on
# settings import when the worker environment is built without them.
if HAS_DAPHNE:
    INSTALLED_APPS.insert(0, "daphne")
if HAS_CHANNELS:
    INSTALLED_APPS.insert(7, "channels")

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.RequestTimingMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "svom"),
        "USER": os.getenv("POSTGRES_USER", "svom"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "svom"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1")
REDIS_CHANNEL_LAYER_URL = os.getenv("REDIS_CHANNEL_LAYER_URL", REDIS_CACHE_URL)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
    }
}

if HAS_CHANNELS and HAS_CHANNELS_REDIS:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_CHANNEL_LAYER_URL],
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("uk", "Ukrainian"),
    ("ru", "Russian"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

REQUEST_TIMING_LOG_ENABLED = env_bool("REQUEST_TIMING_LOG_ENABLED", False)
REQUEST_TIMING_LOG_MIN_MS = env_float("REQUEST_TIMING_LOG_MIN_MS", 0.0)
REQUEST_TIMING_SLOW_SQL_MS = env_float("REQUEST_TIMING_SLOW_SQL_MS", 100.0)
REQUEST_TIMING_SQL_SNIPPET_LENGTH = env_int("REQUEST_TIMING_SQL_SNIPPET_LENGTH", 240)
REQUEST_TIMING_LOG_PATH_PREFIXES = tuple(env_list("REQUEST_TIMING_LOG_PATH_PREFIXES", "/api/"))

CELERY_BROKER_URL = os.getenv("REDIS_CELERY_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 30
CELERY_BEAT_SCHEDULE = {
    "supplier-imports-scheduled-dispatch": {
        "task": "supplier_imports.run_scheduled_imports",
        "schedule": crontab(minute="*"),
    },
    "commerce-sync-nova-poshta-waybills": {
        "task": "commerce.sync_nova_poshta_waybill_statuses",
        "schedule": crontab(minute="*/20"),
    },
    "support-reconcile-presence": {
        "task": "support.reconcile_presence",
        "schedule": crontab(minute="*"),
    },
    "support-rebuild-wallboard-snapshots": {
        "task": "support.rebuild_wallboard_snapshots",
        "schedule": crontab(minute="*/5"),
    },
    "pricing-sync-products-activity-by-price-freshness": {
        "task": "pricing.sync_products_activity_by_price_freshness",
        "schedule": crontab(minute="*/15"),
    },
}

ELASTICSEARCH = {
    "hosts": env_list("ELASTICSEARCH_HOSTS", "http://127.0.0.1:9200"),
    "index_prefix": "svom",
}
SEARCH_BACKEND = "db"

# UTR safety defaults: conservative to reduce supplier-ban risk.
UTR_ENABLED = env_bool("UTR_ENABLED", True)
UTR_RATE_LIMIT_PER_MINUTE = max(env_int("UTR_RATE_LIMIT_PER_MINUTE", 6), 1)
UTR_CONCURRENCY = max(1, min(env_int("UTR_CONCURRENCY", 1), 2))
UTR_MAX_RETRIES = max(env_int("UTR_MAX_RETRIES", 3), 1)
UTR_BACKOFF_BASE_SECONDS = max(env_float("UTR_BACKOFF_BASE_SECONDS", 2.0), 0.5)
UTR_CIRCUIT_BREAKER_THRESHOLD = max(env_int("UTR_CIRCUIT_BREAKER_THRESHOLD", 5), 1)
UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS = max(env_int("UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS", 300), 30)
UTR_APPLICABILITY_ENABLED = env_bool("UTR_APPLICABILITY_ENABLED", True)
UTR_CHARACTERISTICS_ENABLED = env_bool("UTR_CHARACTERISTICS_ENABLED", False)
UTR_FORCE_REFRESH = env_bool("UTR_FORCE_REFRESH", False)
UTR_UNSAFE_ALLOW_FORCE_REFRESH = env_bool("UTR_UNSAFE_ALLOW_FORCE_REFRESH", False)
UTR_BATCH_SIZE = max(env_int("UTR_BATCH_SIZE", 25), 1)
UTR_RESOLVE_BATCH_SIZE = max(env_int("UTR_RESOLVE_BATCH_SIZE", 10), 1)
_utr_resolve_stage_order = os.getenv("UTR_RESOLVE_STAGE_ORDER", "branded_first").strip().lower()
if _utr_resolve_stage_order not in {"brandless_first", "branded_first"}:
    _utr_resolve_stage_order = "branded_first"
UTR_RESOLVE_STAGE_ORDER = _utr_resolve_stage_order
UTR_CACHE_TTL_SECONDS = max(env_int("UTR_CACHE_TTL_SECONDS", 60 * 60 * 24 * 30), 60)
UTR_SINGLE_RUN_LOCK_KEY = env_int("UTR_SINGLE_RUN_LOCK_KEY", 804721451)
UTR_SINGLE_RUN_LOCK_TTL_SECONDS = max(env_int("UTR_SINGLE_RUN_LOCK_TTL_SECONDS", 60 * 60), 60)
