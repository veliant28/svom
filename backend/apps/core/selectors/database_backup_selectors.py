from __future__ import annotations

from django.conf import settings as django_settings
from django.utils import timezone

from apps.core.models import DatabaseBackupSettings


def _profile_defaults(*, code: str) -> dict[str, object]:
    if code == DatabaseBackupSettings.AUTO_DB_PRO_CLONE_CODE:
        return {
            "is_enabled": bool(getattr(django_settings, "AUTODB_CLONE_BACKUP_ENABLED", True)),
            "schedule_cron": getattr(django_settings, "AUTODB_CLONE_BACKUP_CRON", "0 1 * * *"),
            "schedule_timezone": getattr(django_settings, "AUTODB_CLONE_BACKUP_TIMEZONE", "Europe/Kyiv"),
            "backup_directory": getattr(django_settings, "AUTODB_CLONE_BACKUP_DIRECTORY", "Backup/autodb-clone"),
            "retention_count": int(getattr(django_settings, "AUTODB_CLONE_BACKUP_RETENTION_COUNT", 3) or 3),
            "last_started_at": timezone.now(),
        }
    return {
        "is_enabled": bool(getattr(django_settings, "DATABASE_BACKUP_ENABLED", True)),
        "schedule_cron": getattr(django_settings, "DATABASE_BACKUP_CRON", "0 23 * * *"),
        "schedule_timezone": getattr(django_settings, "DATABASE_BACKUP_TIMEZONE", "Europe/Kyiv"),
        "backup_directory": getattr(django_settings, "DATABASE_BACKUP_DIRECTORY", "Backup"),
        "retention_count": int(getattr(django_settings, "DATABASE_BACKUP_RETENTION_COUNT", 3) or 3),
        "last_started_at": timezone.now(),
    }


def get_database_backup_settings(*, code: str = DatabaseBackupSettings.DEFAULT_CODE) -> DatabaseBackupSettings:
    profile_code = (code or DatabaseBackupSettings.DEFAULT_CODE).strip() or DatabaseBackupSettings.DEFAULT_CODE
    settings, _ = DatabaseBackupSettings.objects.get_or_create(
        code=profile_code,
        defaults=_profile_defaults(code=profile_code),
    )
    return settings
