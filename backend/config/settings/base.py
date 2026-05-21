import os
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

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


def parse_database_url(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql", "pgsql"}:
        raise ValueError(f"Unsupported database URL scheme: {parsed.scheme}")

    query = parse_qs(parsed.query, keep_blank_values=True)
    options = {key: values[-1] for key, values in query.items() if values}
    config: dict[str, object] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote((parsed.path or "").lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }
    if options:
        config["OPTIONS"] = options
    return config

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
    # Kept for historical migration graph compatibility. Runtime API/routes are disabled.
    "apps.vehicles.apps.VehiclesConfig",
    "apps.autocatalog.apps.AutocatalogConfig",
    "apps.autodb.apps.AutoDbConfig",
    "apps.compatibility.apps.CompatibilityConfig",
    "apps.marketing.apps.MarketingConfig",
    "apps.seo.apps.SeoConfig",
    "apps.search.apps.SearchConfig",
    "apps.security.apps.SecurityConfig",
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
    "apps.security.middleware.SecurityBlockEnforcementMiddleware",
    "apps.security.middleware.SecurityEventCaptureMiddleware",
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

AUTODB_PRO_LOCAL_DATABASE_URL = os.getenv("AUTODB_PRO_LOCAL_DATABASE_URL", "").strip()
AUTODB_PRO_LOCAL_DATABASE_NAME = os.getenv("AUTODB_PRO_LOCAL_DATABASE_NAME", "Auto_DB_Pro").strip() or "Auto_DB_Pro"
_legacy_autodb_db_name = os.getenv("AUTODB_POSTGRES_DB", "").strip()
_fallback_autodb_db_name = (
    "Auto_DB_Pro"
    if _legacy_autodb_db_name in {"", "svom_autodb"}
    else _legacy_autodb_db_name
)

if AUTODB_PRO_LOCAL_DATABASE_URL:
    _auto_db_pro_config = parse_database_url(AUTODB_PRO_LOCAL_DATABASE_URL)
else:
    _auto_db_pro_config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("AUTODB_PRO_LOCAL_DATABASE_NAME", _fallback_autodb_db_name),
        "USER": os.getenv("AUTODB_PRO_LOCAL_DATABASE_USER", os.getenv("AUTODB_POSTGRES_USER", "svom")),
        "PASSWORD": os.getenv("AUTODB_PRO_LOCAL_DATABASE_PASSWORD", os.getenv("AUTODB_POSTGRES_PASSWORD", "svom")),
        "HOST": os.getenv("AUTODB_PRO_LOCAL_DATABASE_HOST", os.getenv("AUTODB_POSTGRES_HOST", "127.0.0.1")),
        "PORT": os.getenv("AUTODB_PRO_LOCAL_DATABASE_PORT", os.getenv("AUTODB_POSTGRES_PORT", "5434")),
    }

DATABASES["auto_db_pro"] = _auto_db_pro_config
DATABASE_ROUTERS = ["apps.autodb.db_router.AutoDbRouter"]

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

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "").strip().rstrip("/")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "webmaster@localhost")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)
PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS = max(env_int("PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS", 60), 1)

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
SUPPLIER_IMPORT_SCHEDULED_PIPELINE_SOFT_TIME_LIMIT = max(
    env_int("SUPPLIER_IMPORT_SCHEDULED_PIPELINE_SOFT_TIME_LIMIT", 60 * 120),
    60,
)
SUPPLIER_IMPORT_SCHEDULED_PIPELINE_TIME_LIMIT = max(
    env_int("SUPPLIER_IMPORT_SCHEDULED_PIPELINE_TIME_LIMIT", 60 * 150),
    SUPPLIER_IMPORT_SCHEDULED_PIPELINE_SOFT_TIME_LIMIT + 60,
)
SUPPLIER_PRICE_LIST_FILE_RETENTION_HOURS = max(env_int("SUPPLIER_PRICE_LIST_FILE_RETENTION_HOURS", 48), 1)
SUPPLIER_IMPORT_CURRENT_OFFER_SOURCES = tuple(env_list("SUPPLIER_IMPORT_CURRENT_OFFER_SOURCES", "gpl"))
SUPPLIER_IMPORT_ROW_ERROR_RETENTION_RUNS = max(env_int("SUPPLIER_IMPORT_ROW_ERROR_RETENTION_RUNS", 5), 0)
SUPPLIER_IMPORT_SCHEDULE_DISPATCH_LOCK_SECONDS = max(env_int("SUPPLIER_IMPORT_SCHEDULE_DISPATCH_LOCK_SECONDS", 60 * 60), 60)
AUTODB_PRO_SUPPLIER_IMPORT_ENRICHMENT_ENABLED = env_bool("AUTODB_PRO_SUPPLIER_IMPORT_ENRICHMENT_ENABLED", False)
AUTODB_PRO_SUPPLIER_IMPORT_NAME_UPDATE_ENABLED = env_bool("AUTODB_PRO_SUPPLIER_IMPORT_NAME_UPDATE_ENABLED", False)
AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED = env_bool("AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED", False)
AUTODB_PRO_SUPPLIER_IMPORT_IMAGE_UPDATE_ENABLED = env_bool("AUTODB_PRO_SUPPLIER_IMPORT_IMAGE_UPDATE_ENABLED", False)
DATABASE_BACKUP_ENABLED = env_bool("DATABASE_BACKUP_ENABLED", True)
DATABASE_BACKUP_CRON = os.getenv("DATABASE_BACKUP_CRON", "0 23 * * *")
DATABASE_BACKUP_TIMEZONE = os.getenv("DATABASE_BACKUP_TIMEZONE", "Europe/Kyiv")
DATABASE_BACKUP_DIRECTORY = os.getenv("DATABASE_BACKUP_DIRECTORY", "Backup")
DATABASE_BACKUP_RETENTION_COUNT = max(env_int("DATABASE_BACKUP_RETENTION_COUNT", 3), 1)
DATABASE_BACKUP_DISPATCH_LOCK_SECONDS = max(env_int("DATABASE_BACKUP_DISPATCH_LOCK_SECONDS", 60 * 60), 60)
DATABASE_BACKUP_TIMEOUT_SECONDS = max(env_int("DATABASE_BACKUP_TIMEOUT_SECONDS", 60 * 60), 60)
DATABASE_BACKUP_TASK_SOFT_TIME_LIMIT = max(env_int("DATABASE_BACKUP_TASK_SOFT_TIME_LIMIT", 60 * 60), 60)
DATABASE_BACKUP_TASK_TIME_LIMIT = max(env_int("DATABASE_BACKUP_TASK_TIME_LIMIT", 60 * 70), DATABASE_BACKUP_TASK_SOFT_TIME_LIMIT + 60)
DATABASE_BACKUP_PG_DUMP_BIN = os.getenv("DATABASE_BACKUP_PG_DUMP_BIN", "pg_dump")
FITMENT_PROVIDER = os.getenv("FITMENT_PROVIDER", "autodb").strip().lower()

AUTODB_PRO_REMOTE_ENABLED = env_bool("AUTODB_PRO_REMOTE_ENABLED", False)
AUTODB_PRO_REMOTE_CONNECT_TIMEOUT = max(env_int("AUTODB_PRO_REMOTE_CONNECT_TIMEOUT", 10), 1)
AUTODB_PRO_REMOTE_READ_TIMEOUT = max(env_int("AUTODB_PRO_REMOTE_READ_TIMEOUT", 30), 1)
AUTODB_PRO_REMOTE_BATCH_SIZE = max(env_int("AUTODB_PRO_REMOTE_BATCH_SIZE", 100), 1)
AUTODB_PRO_REMOTE_LIMIT_PER_HOUR = max(env_int("AUTODB_PRO_REMOTE_LIMIT_PER_HOUR", 10000), 1)
AUTODB_PRO_REMOTE_COOLDOWN_MINUTES = max(env_int("AUTODB_PRO_REMOTE_COOLDOWN_MINUTES", 60), 1)
AUTODB_BACKOFFICE_BATCH_ITEM_TIMEOUT_SECONDS = max(env_int("AUTODB_BACKOFFICE_BATCH_ITEM_TIMEOUT_SECONDS", 90), 10)
AUTODB_BACKOFFICE_BATCH_SOFT_TIME_LIMIT_BASE_SECONDS = max(
    env_int("AUTODB_BACKOFFICE_BATCH_SOFT_TIME_LIMIT_BASE_SECONDS", 60 * 15),
    300,
)
AUTODB_BACKOFFICE_BATCH_SOFT_TIME_LIMIT_PER_ITEM_SECONDS = max(
    env_int(
        "AUTODB_BACKOFFICE_BATCH_SOFT_TIME_LIMIT_PER_ITEM_SECONDS",
        55,
    ),
    30,
)
AUTODB_BACKOFFICE_BATCH_TIME_LIMIT_GRACE_SECONDS = max(
    env_int("AUTODB_BACKOFFICE_BATCH_TIME_LIMIT_GRACE_SECONDS", 60 * 15),
    60,
)
AUTODB_BACKOFFICE_BATCH_MAX_TIME_LIMIT_SECONDS = max(
    env_int("AUTODB_BACKOFFICE_BATCH_MAX_TIME_LIMIT_SECONDS", 60 * 60 * 10),
    AUTODB_BACKOFFICE_BATCH_SOFT_TIME_LIMIT_BASE_SECONDS + AUTODB_BACKOFFICE_BATCH_TIME_LIMIT_GRACE_SECONDS,
)
AUTODB_PRO_REMOTE_STRICT_QUOTA_GATE_ENABLED = env_bool("AUTODB_PRO_REMOTE_STRICT_QUOTA_GATE_ENABLED", True)
AUTODB_PRO_REMOTE_ENFORCE_GATEWAY_ONLY = env_bool("AUTODB_PRO_REMOTE_ENFORCE_GATEWAY_ONLY", True)
AUTODB_PRO_VEHICLE_CATALOG_API_ENABLED = env_bool("AUTODB_PRO_VEHICLE_CATALOG_API_ENABLED", False)
AUTODB_MANUAL_SEARCH_REMOTE_API_ENABLED = env_bool("AUTODB_MANUAL_SEARCH_REMOTE_API_ENABLED", True)
AUTODB_MANUAL_SEARCH_REMOTE_API_BASE_URL = os.getenv("AUTODB_MANUAL_SEARCH_REMOTE_API_BASE_URL", "https://auto-db.pro/api/v1/").strip()
AUTODB_BATCH_PUBLIC_SEARCH_ENABLED = env_bool("AUTODB_BATCH_PUBLIC_SEARCH_ENABLED", True)

AUTODB_SOURCE_MYSQL_TIMEOUT_SECONDS = max(
    env_int("AUTODB_SOURCE_MYSQL_TIMEOUT_SECONDS", AUTODB_PRO_REMOTE_CONNECT_TIMEOUT),
    1,
)
CELERY_BEAT_SCHEDULE = {
    "supplier-imports-scheduled-dispatch": {
        "task": "supplier_imports.run_scheduled_imports",
        "schedule": crontab(minute="*"),
    },
    "core-database-backup-scheduled-dispatch": {
        "task": "core.dispatch_scheduled_database_backup",
        "schedule": crontab(minute="*"),
    },
    "supplier-imports-cleanup-price-list-files": {
        "task": "supplier_imports.cleanup_price_list_files",
        "schedule": crontab(minute=17),
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
    "autodb-check-remote-quota-recovery": {
        "task": "autodb.check_remote_quota_recovery",
        "schedule": crontab(minute="*"),
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
UTR_ENABLED = env_bool("UTR_ENABLED", False)
UTR_CATALOG_ENRICHMENT_ENABLED = env_bool("UTR_CATALOG_ENRICHMENT_ENABLED", False)
UTR_RATE_LIMIT_PER_MINUTE = max(env_int("UTR_RATE_LIMIT_PER_MINUTE", 10), 1)
UTR_CONCURRENCY = max(1, min(env_int("UTR_CONCURRENCY", 1), 2))
UTR_MAX_RETRIES = max(env_int("UTR_MAX_RETRIES", 3), 1)
UTR_BACKOFF_BASE_SECONDS = max(env_float("UTR_BACKOFF_BASE_SECONDS", 2.0), 0.5)
UTR_CIRCUIT_BREAKER_THRESHOLD = max(env_int("UTR_CIRCUIT_BREAKER_THRESHOLD", 5), 1)
UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS = max(env_int("UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS", 300), 30)
UTR_APPLICABILITY_ENABLED = env_bool("UTR_APPLICABILITY_ENABLED", False)
UTR_CHARACTERISTICS_ENABLED = env_bool("UTR_CHARACTERISTICS_ENABLED", False)
UTR_FORCE_REFRESH = env_bool("UTR_FORCE_REFRESH", False)
UTR_UNSAFE_ALLOW_FORCE_REFRESH = env_bool("UTR_UNSAFE_ALLOW_FORCE_REFRESH", False)
UTR_BATCH_SIZE = max(env_int("UTR_BATCH_SIZE", 25), 1)
UTR_RESOLVE_BATCH_SIZE = max(env_int("UTR_RESOLVE_BATCH_SIZE", UTR_BATCH_SIZE), 1)
UTR_RESOLVE_ENRICH_PRODUCTS_FROM_SEARCH = env_bool("UTR_RESOLVE_ENRICH_PRODUCTS_FROM_SEARCH", True)
_utr_resolve_stage_order = os.getenv("UTR_RESOLVE_STAGE_ORDER", "branded_first").strip().lower()
if _utr_resolve_stage_order not in {"brandless_first", "branded_first"}:
    _utr_resolve_stage_order = "branded_first"
UTR_RESOLVE_STAGE_ORDER = _utr_resolve_stage_order
UTR_CACHE_TTL_SECONDS = max(env_int("UTR_CACHE_TTL_SECONDS", 60 * 60 * 24 * 30), 60)
UTR_SYNC_ENRICH_MAX_PRODUCTS = max(env_int("UTR_SYNC_ENRICH_MAX_PRODUCTS", 1), 1)
UTR_LAZY_ENRICH_QUEUE_LOCK_SECONDS = max(env_int("UTR_LAZY_ENRICH_QUEUE_LOCK_SECONDS", 10 * 60), 60)
UTR_LAZY_CATALOG_BATCH_SIZE = max(env_int("UTR_LAZY_CATALOG_BATCH_SIZE", 25), 1)
UTR_LAZY_CATALOG_APPLICABILITY_ENABLED = env_bool("UTR_LAZY_CATALOG_APPLICABILITY_ENABLED", False)
UTR_LAZY_CATALOG_APPLICABILITY_TOP_N = max(env_int("UTR_LAZY_CATALOG_APPLICABILITY_TOP_N", 52), 0)
UTR_LAZY_APPLICABILITY_QUEUE_LOCK_SECONDS = max(env_int("UTR_LAZY_APPLICABILITY_QUEUE_LOCK_SECONDS", 30 * 60), 60)
UTR_LAZY_ENRICH_CHARACTERISTICS_ENABLED = env_bool("UTR_LAZY_ENRICH_CHARACTERISTICS_ENABLED", False)
UTR_LAZY_ENRICH_APPLICABILITY_ENABLED = env_bool("UTR_LAZY_ENRICH_APPLICABILITY_ENABLED", False)
UTR_SINGLE_RUN_LOCK_KEY = env_int("UTR_SINGLE_RUN_LOCK_KEY", 804721451)
UTR_SINGLE_RUN_LOCK_TTL_SECONDS = max(env_int("UTR_SINGLE_RUN_LOCK_TTL_SECONDS", 60 * 60), 60)

AUTODB_LIVE_CONTENT_ENABLED = env_bool("AUTODB_LIVE_CONTENT_ENABLED", True)
AUTODB_CONTENT_CACHE_TTL_SECONDS = max(env_int("AUTODB_CONTENT_CACHE_TTL_SECONDS", 60 * 30), 30)
AUTODB_OFFLINE_TRANSLATE_ENABLED = env_bool("AUTODB_OFFLINE_TRANSLATE_ENABLED", False)
AUTODB_OFFLINE_TRANSLATE_URL = os.getenv("AUTODB_OFFLINE_TRANSLATE_URL", "http://libretranslate:5000").strip()
AUTODB_OFFLINE_TRANSLATE_API_KEY = os.getenv("AUTODB_OFFLINE_TRANSLATE_API_KEY", "").strip()
AUTODB_OFFLINE_TRANSLATE_PROVIDER = os.getenv("AUTODB_OFFLINE_TRANSLATE_PROVIDER", "libretranslate").strip().lower()
AUTODB_GOOGLE_TRANSLATE_URL = os.getenv(
    "AUTODB_GOOGLE_TRANSLATE_URL",
    "https://translation.googleapis.com/language/translate/v2",
).strip()
AUTODB_GOOGLE_TRANSLATE_API_KEY = os.getenv("AUTODB_GOOGLE_TRANSLATE_API_KEY", "").strip()
AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS = max(env_int("AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS", 4000), 500)
