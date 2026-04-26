import os

from .base import *  # noqa: F403

DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", SECRET_KEY)  # noqa: F405
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

DATABASES["default"] = {  # noqa: F405
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("POSTGRES_DB", "svom"),
    "USER": os.getenv("POSTGRES_USER", "svom"),
    "PASSWORD": os.getenv("POSTGRES_PASSWORD", "svom"),
    "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "PORT": os.getenv("POSTGRES_PORT", "5433"),
}

CACHES["default"]["LOCATION"] = os.getenv("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1")  # noqa: F405
CELERY_BROKER_URL = os.getenv("REDIS_CELERY_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

elasticsearch_hosts = os.getenv("ELASTICSEARCH_HOSTS", "http://127.0.0.1:9200")
ELASTICSEARCH["hosts"] = [host.strip() for host in elasticsearch_hosts.split(",") if host.strip()]  # noqa: F405
SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "db")

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
