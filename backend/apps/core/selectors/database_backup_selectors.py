from __future__ import annotations

from django.conf import settings as django_settings
from django.utils import timezone

from apps.core.models import DatabaseBackupSettings


def get_database_backup_settings() -> DatabaseBackupSettings:
    settings, _ = DatabaseBackupSettings.objects.get_or_create(
        code=DatabaseBackupSettings.DEFAULT_CODE,
        defaults={
            "is_enabled": bool(getattr(django_settings, "DATABASE_BACKUP_ENABLED", True)),
            "schedule_cron": getattr(django_settings, "DATABASE_BACKUP_CRON", "0 23 * * *"),
            "schedule_timezone": getattr(django_settings, "DATABASE_BACKUP_TIMEZONE", "Europe/Kyiv"),
            "backup_directory": getattr(django_settings, "DATABASE_BACKUP_DIRECTORY", "Backup"),
            "retention_count": int(getattr(django_settings, "DATABASE_BACKUP_RETENTION_COUNT", 3) or 3),
            "last_started_at": timezone.now(),
        },
    )
    return settings
