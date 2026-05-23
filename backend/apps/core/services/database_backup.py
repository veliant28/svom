from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as dj_timezone

from apps.core.models import DatabaseBackupSettings
from apps.core.selectors.database_backup_selectors import get_database_backup_settings
from apps.supplier_imports.services.scheduling.cron_expression import CronExpression, compute_next_run


@dataclass(frozen=True)
class DatabaseBackupDispatchResult:
    status: str
    task_id: str | None
    reason: str
    due_at: datetime | None = None


@dataclass(frozen=True)
class DatabaseBackupResult:
    status: str
    backup_path: str
    backup_size: int
    deleted_paths: list[str]
    message: str

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "backup_path": self.backup_path,
            "backup_size": self.backup_size,
            "deleted_paths": self.deleted_paths,
            "message": self.message,
        }


@dataclass(frozen=True)
class BackupProfileConfig:
    code: str
    db_alias: str
    file_prefix: str


class DatabaseBackupService:
    DEFAULT_DISPATCH_LOCK_SECONDS = 60 * 60
    DEFAULT_TIMEOUT_SECONDS = 60 * 60
    MAIN_FILE_PREFIX = "svom-postgresql"
    CLONE_FILE_PREFIX = "svom-postgresql-autodb-clone"

    def dispatch_due_backup(
        self,
        *,
        backup_code: str = DatabaseBackupSettings.DEFAULT_CODE,
        now: datetime | None = None,
    ) -> DatabaseBackupDispatchResult:
        profile = self._resolve_profile(code=backup_code)

        backup_settings = get_database_backup_settings(code=profile.code)
        self.close_stale_running_backup(backup_settings=backup_settings, now=now)
        due_at = self.resolve_due_at(backup_settings=backup_settings, now=now or dj_timezone.now())
        if due_at is None:
            return DatabaseBackupDispatchResult(status="skipped", task_id=None, reason="not_due")

        if not self._acquire_dispatch_lock(backup_settings=backup_settings, due_at=due_at):
            return DatabaseBackupDispatchResult(status="skipped", task_id=None, reason="dispatch_locked", due_at=due_at)

        try:
            task = self._enqueue_run_task(backup_code=profile.code)
        except Exception:
            self._clear_dispatch_lock(backup_settings=backup_settings, due_at=due_at)
            raise

        return DatabaseBackupDispatchResult(status="scheduled", task_id=task.id, reason="due", due_at=due_at)

    def close_stale_running_backup(
        self,
        *,
        backup_settings: DatabaseBackupSettings | None = None,
        backup_code: str = DatabaseBackupSettings.DEFAULT_CODE,
        now: datetime | None = None,
    ) -> bool:
        profile = self._resolve_profile(code=backup_code)
        instance = backup_settings or get_database_backup_settings(code=profile.code)
        if instance.last_status != DatabaseBackupSettings.STATUS_RUNNING or not instance.last_started_at:
            return False

        moment = now or dj_timezone.now()
        timeout_seconds = self._timeout_seconds()
        if instance.last_started_at > moment - timedelta(seconds=timeout_seconds):
            return False

        instance.last_status = DatabaseBackupSettings.STATUS_FAILED
        instance.last_failed_at = moment
        instance.last_finished_at = moment
        instance.last_message = "Auto-closed stale database backup run."
        instance.save(update_fields=("last_status", "last_failed_at", "last_finished_at", "last_message", "updated_at"))
        return True

    def resolve_due_at(self, *, backup_settings: DatabaseBackupSettings, now: datetime) -> datetime | None:
        if not backup_settings.is_enabled or not backup_settings.schedule_cron:
            return None

        timezone = self._resolve_timezone(backup_settings.schedule_timezone)
        if timezone is None:
            return None

        try:
            cron = CronExpression.parse(backup_settings.schedule_cron)
        except ValueError:
            return None

        local_now = now.astimezone(timezone).replace(second=0, microsecond=0)
        if cron.matches(local_now):
            due_at = local_now
        else:
            due_at = self._resolve_previous_scheduled_at(cron=cron, local_now=local_now)
            if due_at is None:
                return None

        if backup_settings.last_started_at is None:
            return due_at

        last_local = backup_settings.last_started_at.astimezone(timezone).replace(second=0, microsecond=0)
        if last_local < due_at:
            return due_at
        return None

    def get_next_run(
        self,
        *,
        backup_settings: DatabaseBackupSettings,
        now: datetime | None = None,
    ) -> datetime | None:
        timezone_name = backup_settings.schedule_timezone or settings.TIME_ZONE
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return None

        baseline = (now or datetime.now(tz=timezone)).astimezone(timezone)
        return compute_next_run(
            cron_expression=backup_settings.schedule_cron,
            timezone_name=timezone_name,
            now=baseline,
        )

    def run_backup(self, *, backup_code: str = DatabaseBackupSettings.DEFAULT_CODE) -> DatabaseBackupResult:
        profile = self._resolve_profile(code=backup_code)
        backup_settings = get_database_backup_settings(code=profile.code)
        lock_acquired = self._acquire_run_lock(backup_code=profile.code)
        if not lock_acquired:
            return DatabaseBackupResult(
                status=DatabaseBackupSettings.STATUS_SKIPPED,
                backup_path="",
                backup_size=0,
                deleted_paths=[],
                message="Database backup is already running.",
            )

        backup_path = Path()
        moment = dj_timezone.now()
        try:
            backup_settings.last_started_at = moment
            backup_settings.last_status = DatabaseBackupSettings.STATUS_RUNNING
            backup_settings.last_message = ""
            backup_settings.save(update_fields=("last_started_at", "last_status", "last_message", "updated_at"))

            backup_dir = self._resolve_backup_directory(backup_settings.backup_directory)
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / self._build_backup_filename(
                moment=moment,
                db_alias=profile.db_alias,
                file_prefix=profile.file_prefix,
            )

            self._run_pg_dump(backup_path=backup_path, db_alias=profile.db_alias)

            if not backup_path.exists():
                raise RuntimeError("pg_dump finished without creating a backup file.")

            backup_size = backup_path.stat().st_size
            deleted_paths = self._apply_retention(
                backup_dir=backup_dir,
                retention_count=backup_settings.retention_count,
                file_prefix=profile.file_prefix,
            )
            finished_at = dj_timezone.now()
            message = f"PostgreSQL backup ({profile.code}) created: {backup_path.name}"
            backup_settings.last_finished_at = finished_at
            backup_settings.last_success_at = finished_at
            backup_settings.last_status = DatabaseBackupSettings.STATUS_SUCCESS
            backup_settings.last_message = message
            backup_settings.last_backup_path = str(backup_path)
            backup_settings.last_backup_size = backup_size
            backup_settings.save(
                update_fields=(
                    "last_finished_at",
                    "last_success_at",
                    "last_status",
                    "last_message",
                    "last_backup_path",
                    "last_backup_size",
                    "updated_at",
                )
            )
            return DatabaseBackupResult(
                status=DatabaseBackupSettings.STATUS_SUCCESS,
                backup_path=str(backup_path),
                backup_size=backup_size,
                deleted_paths=deleted_paths,
                message=message,
            )
        except Exception as exc:
            if backup_path and backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    pass

            finished_at = dj_timezone.now()
            backup_settings.last_finished_at = finished_at
            backup_settings.last_failed_at = finished_at
            backup_settings.last_status = DatabaseBackupSettings.STATUS_FAILED
            backup_settings.last_message = str(exc)
            backup_settings.save(
                update_fields=("last_finished_at", "last_failed_at", "last_status", "last_message", "updated_at")
            )
            raise
        finally:
            self._clear_run_lock(backup_code=profile.code)

    def _run_pg_dump(self, *, backup_path: Path, db_alias: str) -> None:
        database = settings.DATABASES[db_alias]
        db_name = str(database.get("NAME") or "")
        db_user = str(database.get("USER") or "")
        db_password = str(database.get("PASSWORD") or "")
        db_host = str(database.get("HOST") or "")
        db_port = str(database.get("PORT") or "")
        pg_dump_bin = str(getattr(settings, "DATABASE_BACKUP_PG_DUMP_BIN", "pg_dump") or "pg_dump")

        command = [
            pg_dump_bin,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(backup_path),
        ]
        if db_host:
            command.extend(["--host", db_host])
        if db_port:
            command.extend(["--port", db_port])
        if db_user:
            command.extend(["--username", db_user])
        command.append(db_name)

        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password

        completed = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=self._timeout_seconds(),
            check=False,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(stderr or f"pg_dump failed with exit code {completed.returncode}.")

    def _apply_retention(self, *, backup_dir: Path, retention_count: int, file_prefix: str) -> list[str]:
        keep_count = max(int(retention_count or 0), 1)
        backups = sorted(
            backup_dir.glob(f"{file_prefix}-*.dump"),
            key=lambda item: (item.stat().st_mtime, item.name),
            reverse=True,
        )
        deleted: list[str] = []
        for path in backups[keep_count:]:
            try:
                path.unlink()
                deleted.append(str(path))
            except OSError:
                continue
        return deleted

    def _resolve_backup_directory(self, raw_path: str) -> Path:
        backup_dir = Path(raw_path or "Backup")
        if not backup_dir.is_absolute():
            backup_dir = Path(settings.ROOT_DIR) / backup_dir
        return backup_dir

    def _build_backup_filename(self, *, moment: datetime, db_alias: str, file_prefix: str) -> str:
        database = settings.DATABASES[db_alias]
        db_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(database.get("NAME") or "database")).strip("-")
        timestamp = moment.astimezone(ZoneInfo(getattr(settings, "TIME_ZONE", "Europe/Kyiv"))).strftime("%Y%m%d-%H%M%S")
        return f"{file_prefix}-{db_name}-{timestamp}.dump"

    def _resolve_timezone(self, timezone_name: str) -> ZoneInfo | None:
        try:
            return ZoneInfo(timezone_name or settings.TIME_ZONE)
        except ZoneInfoNotFoundError:
            return None

    def _resolve_previous_scheduled_at(self, *, cron: CronExpression, local_now: datetime) -> datetime | None:
        probe = local_now - timedelta(minutes=1)
        horizon = local_now - timedelta(days=60)
        while probe >= horizon:
            if cron.matches(probe):
                return probe
            probe -= timedelta(minutes=1)
        return None

    def _acquire_dispatch_lock(self, *, backup_settings: DatabaseBackupSettings, due_at: datetime) -> bool:
        try:
            return bool(cache.add(self._dispatch_lock_key(backup_settings=backup_settings, due_at=due_at), "1", timeout=self._dispatch_lock_seconds()))
        except Exception:
            return True

    def _clear_dispatch_lock(self, *, backup_settings: DatabaseBackupSettings, due_at: datetime) -> None:
        try:
            cache.delete(self._dispatch_lock_key(backup_settings=backup_settings, due_at=due_at))
        except Exception:
            pass

    def _dispatch_lock_key(self, *, backup_settings: DatabaseBackupSettings, due_at: datetime) -> str:
        return f"core:database_backup:scheduled_dispatch:{backup_settings.id}:{due_at.isoformat()}"

    def _acquire_run_lock(self, *, backup_code: str) -> bool:
        try:
            return bool(cache.add(self._run_lock_key(backup_code=backup_code), "1", timeout=self._timeout_seconds()))
        except Exception:
            return True

    def _clear_run_lock(self, *, backup_code: str) -> None:
        try:
            cache.delete(self._run_lock_key(backup_code=backup_code))
        except Exception:
            pass

    def _run_lock_key(self, *, backup_code: str) -> str:
        normalized = (backup_code or DatabaseBackupSettings.DEFAULT_CODE).strip() or DatabaseBackupSettings.DEFAULT_CODE
        return f"core:database_backup:run:{normalized}"

    def _resolve_profile(self, *, code: str) -> BackupProfileConfig:
        normalized = (code or DatabaseBackupSettings.DEFAULT_CODE).strip() or DatabaseBackupSettings.DEFAULT_CODE
        if normalized == DatabaseBackupSettings.AUTO_DB_PRO_CLONE_CODE:
            return BackupProfileConfig(
                code=DatabaseBackupSettings.AUTO_DB_PRO_CLONE_CODE,
                db_alias="auto_db_pro",
                file_prefix=self.CLONE_FILE_PREFIX,
            )
        return BackupProfileConfig(
            code=DatabaseBackupSettings.DEFAULT_CODE,
            db_alias="default",
            file_prefix=self.MAIN_FILE_PREFIX,
        )

    def _enqueue_run_task(self, *, backup_code: str):
        if backup_code == DatabaseBackupSettings.AUTO_DB_PRO_CLONE_CODE:
            from apps.core.tasks.database_backup import run_autodb_clone_backup_task

            return run_autodb_clone_backup_task.delay()

        from apps.core.tasks.database_backup import run_database_backup_task

        return run_database_backup_task.delay()

    def _dispatch_lock_seconds(self) -> int:
        raw = getattr(settings, "DATABASE_BACKUP_DISPATCH_LOCK_SECONDS", self.DEFAULT_DISPATCH_LOCK_SECONDS)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return self.DEFAULT_DISPATCH_LOCK_SECONDS
        return value if value > 0 else self.DEFAULT_DISPATCH_LOCK_SECONDS

    def _timeout_seconds(self) -> int:
        raw = getattr(settings, "DATABASE_BACKUP_TIMEOUT_SECONDS", self.DEFAULT_TIMEOUT_SECONDS)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return self.DEFAULT_TIMEOUT_SECONDS
        return value if value > 0 else self.DEFAULT_TIMEOUT_SECONDS
