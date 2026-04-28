from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import DatabaseBackupSettings
from apps.core.services.database_backup import DatabaseBackupService


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    DATABASE_BACKUP_TIMEOUT_SECONDS=60,
)
class DatabaseBackupServiceTest(TestCase):
    def test_dispatch_due_backup_catches_missed_scheduled_run(self):
        kyiv = ZoneInfo("Europe/Kyiv")
        backup_settings = DatabaseBackupSettings.objects.create(
            schedule_cron="0 23 * * *",
            schedule_timezone="Europe/Kyiv",
            last_started_at=datetime(2026, 4, 27, 22, 0, tzinfo=kyiv),
        )

        with patch("apps.core.tasks.database_backup.run_database_backup_task.delay", return_value=SimpleNamespace(id="task-1")):
            result = DatabaseBackupService().dispatch_due_backup(now=datetime(2026, 4, 28, 0, 5, tzinfo=kyiv))

        self.assertEqual(result.status, "scheduled")
        self.assertEqual(result.reason, "due")
        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(result.due_at, datetime(2026, 4, 27, 23, 0, tzinfo=kyiv))
        backup_settings.refresh_from_db()
        self.assertEqual(backup_settings.last_started_at, datetime(2026, 4, 27, 22, 0, tzinfo=kyiv))

    def test_run_backup_creates_dump_and_keeps_latest_three_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            for index in range(3):
                path = backup_dir / f"svom-postgresql-svom-2026042{index}-230000.dump"
                path.write_bytes(b"old")
                path.touch()

            DatabaseBackupSettings.objects.create(
                backup_directory=str(backup_dir),
                retention_count=3,
                last_started_at=timezone.now(),
            )

            def fake_pg_dump(command, **kwargs):
                file_index = command.index("--file") + 1
                Path(command[file_index]).write_bytes(b"new-backup")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("apps.core.services.database_backup.subprocess.run", side_effect=fake_pg_dump):
                result = DatabaseBackupService().run_backup()

            self.assertEqual(result.status, DatabaseBackupSettings.STATUS_SUCCESS)
            self.assertTrue(Path(result.backup_path).exists())
            self.assertEqual(result.backup_size, len(b"new-backup"))
            self.assertEqual(len(list(backup_dir.glob("svom-postgresql-*.dump"))), 3)

            backup_settings = DatabaseBackupSettings.objects.get(code=DatabaseBackupSettings.DEFAULT_CODE)
            self.assertEqual(backup_settings.last_status, DatabaseBackupSettings.STATUS_SUCCESS)
            self.assertEqual(backup_settings.last_backup_size, len(b"new-backup"))
