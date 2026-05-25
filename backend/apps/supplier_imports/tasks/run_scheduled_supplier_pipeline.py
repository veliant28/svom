from __future__ import annotations

import uuid

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError, SupplierIntegrationError
from apps.supplier_imports.services.scheduling.pipeline import ScheduledSupplierImportPipelineService


def get_pipeline_lock_key(*, source_code: str) -> str:
    return f"supplier_imports:pipeline_lock:{source_code}"


def _pipeline_lock_seconds() -> int:
    raw = getattr(settings, "SUPPLIER_IMPORT_PIPELINE_LOCK_SECONDS", 60 * 150)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 60 * 150
    return value if value > 0 else 60 * 150


@shared_task(
    name="supplier_imports.run_scheduled_supplier_pipeline",
    soft_time_limit=int(getattr(settings, "SUPPLIER_IMPORT_SCHEDULED_PIPELINE_SOFT_TIME_LIMIT", 60 * 120)),
    time_limit=int(getattr(settings, "SUPPLIER_IMPORT_SCHEDULED_PIPELINE_TIME_LIMIT", 60 * 150)),
)
def run_scheduled_supplier_pipeline_task(source_code: str) -> dict:
    lock_key = get_pipeline_lock_key(source_code=source_code)
    lock_owner = str(uuid.uuid4())
    lock_seconds = _pipeline_lock_seconds()
    acquired = False
    try:
        acquired = bool(cache.add(lock_key, lock_owner, timeout=lock_seconds))
    except Exception:
        acquired = True
    if not acquired:
        return {
            "source_code": source_code,
            "status": "skipped",
            "detail": "already_running",
        }

    service = ScheduledSupplierImportPipelineService()
    try:
        result = service.run(source_code=source_code)
        return {
            "source_code": result.source_code,
            "status": result.status,
            "detail": result.detail,
            "payload": result.payload,
        }
    except SupplierCooldownError as exc:
        return {
            "source_code": source_code,
            "status": "blocked_by_cooldown",
            "detail": str(exc),
            "retry_after_seconds": exc.retry_after_seconds,
        }
    except SupplierIntegrationError as exc:
        return {
            "source_code": source_code,
            "status": "failed",
            "detail": str(exc),
        }
    finally:
        try:
            current_owner = cache.get(lock_key)
            if current_owner == lock_owner:
                cache.delete(lock_key)
        except Exception:
            pass
