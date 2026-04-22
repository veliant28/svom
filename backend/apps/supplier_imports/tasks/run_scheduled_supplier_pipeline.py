from __future__ import annotations

from celery import shared_task

from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError, SupplierIntegrationError
from apps.supplier_imports.services.scheduling.pipeline import ScheduledSupplierImportPipelineService


@shared_task(name="supplier_imports.run_scheduled_supplier_pipeline")
def run_scheduled_supplier_pipeline_task(source_code: str) -> dict:
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
