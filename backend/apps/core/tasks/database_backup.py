from __future__ import annotations

from celery import shared_task
from django.conf import settings

from apps.core.services.database_backup import DatabaseBackupService


@shared_task(name="core.dispatch_scheduled_database_backup")
def dispatch_scheduled_database_backup_task() -> dict:
    result = DatabaseBackupService().dispatch_due_backup()
    return {
        "status": result.status,
        "task_id": result.task_id,
        "reason": result.reason,
        "due_at": result.due_at.isoformat() if result.due_at else None,
    }


@shared_task(
    name="core.run_database_backup",
    soft_time_limit=int(getattr(settings, "DATABASE_BACKUP_TASK_SOFT_TIME_LIMIT", 60 * 60)),
    time_limit=int(getattr(settings, "DATABASE_BACKUP_TASK_TIME_LIMIT", 60 * 70)),
)
def run_database_backup_task() -> dict:
    return DatabaseBackupService().run_backup().as_dict()
