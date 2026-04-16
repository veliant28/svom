from celery import shared_task

from apps.supplier_imports.services import ScheduledImportService


@shared_task(name="supplier_imports.run_scheduled_imports")
def run_scheduled_imports_task() -> dict:
    results = ScheduledImportService().dispatch_due_sources()
    return {
        "checked": len(results),
        "scheduled": len([item for item in results if item.status == "scheduled"]),
        "results": [
            {
                "source_code": item.source_code,
                "status": item.status,
                "task_id": item.task_id,
                "reason": item.reason,
            }
            for item in results
        ],
    }
