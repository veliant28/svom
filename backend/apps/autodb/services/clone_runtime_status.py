from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
import signal
import subprocess
from typing import Any

from django.db import connections
from django.utils import timezone

from apps.autodb.models import AutoDbSyncState


@dataclass(frozen=True)
class CloneRuntimeStatus:
    table: str
    state_status: str
    actual_status: str
    process_running: bool
    pid: int | None
    processed_rows: int
    total_rows: int
    failed_rows: int
    table_row_count: int
    last_cursor: str
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime | None
    last_error: str
    reconciled: bool
    reconcile_note: str


def get_passanger_car_trees_runtime_status(*, reconcile: bool = False) -> CloneRuntimeStatus:
    table = "passanger_car_trees"
    state = AutoDbSyncState.objects.using("auto_db_pro").filter(source_table=table).first()
    table_row_count = _count_table_rows(table)
    pid = _resolve_active_sync_pid()
    process_running = pid is not None

    state_status = str(getattr(state, "status", "") or "missing")
    processed_rows = int(getattr(state, "processed_rows", 0) or 0)
    total_rows = int(getattr(state, "total_rows", 0) or 0)
    failed_rows = int(getattr(state, "failed_rows", 0) or 0)
    last_cursor = str(getattr(state, "last_cursor", "") or "")
    started_at = getattr(state, "started_at", None)
    finished_at = getattr(state, "finished_at", None)
    updated_at = getattr(state, "updated_at", None)
    last_error = str(getattr(state, "last_error", "") or "")

    actual_status = state_status
    reconcile_note = ""
    reconciled = False

    if state is None:
        actual_status = "missing"
    elif process_running:
        actual_status = "running"
    elif state_status == AutoDbSyncState.Status.COMPLETED:
        actual_status = "completed"
    elif state_status == AutoDbSyncState.Status.RUNNING:
        if total_rows > 0 and processed_rows >= total_rows and table_row_count >= total_rows:
            actual_status = "completed"
            reconcile_note = "stale_running_state_but_counts_confirm_complete"
            if reconcile:
                _update_state(
                    state=state,
                    status=AutoDbSyncState.Status.COMPLETED,
                    error="",
                    finished_at=timezone.now(),
                )
                reconciled = True
        else:
            actual_status = "paused"
            reconcile_note = "process_not_running_resume_allowed"
            if reconcile:
                _update_state(
                    state=state,
                    status=AutoDbSyncState.Status.PAUSED,
                    error="process_not_running_resume_allowed",
                    finished_at=timezone.now(),
                )
                reconciled = True
    elif state_status == AutoDbSyncState.Status.FAILED:
        actual_status = "failed"
    elif state_status == AutoDbSyncState.Status.PAUSED:
        actual_status = "paused"

    refreshed_state = state
    if reconcile and reconciled:
        refreshed_state = AutoDbSyncState.objects.using("auto_db_pro").filter(source_table=table).first()
        state_status = str(getattr(refreshed_state, "status", "") or state_status)
        finished_at = getattr(refreshed_state, "finished_at", finished_at)
        updated_at = getattr(refreshed_state, "updated_at", updated_at)
        last_error = str(getattr(refreshed_state, "last_error", "") or last_error)

    return CloneRuntimeStatus(
        table=table,
        state_status=state_status,
        actual_status=actual_status,
        process_running=process_running,
        pid=pid,
        processed_rows=processed_rows,
        total_rows=total_rows,
        failed_rows=failed_rows,
        table_row_count=table_row_count,
        last_cursor=last_cursor,
        started_at=started_at,
        finished_at=finished_at,
        updated_at=updated_at,
        last_error=last_error,
        reconciled=reconciled,
        reconcile_note=reconcile_note,
    )


def _resolve_active_sync_pid() -> int | None:
    pid = _read_pid_file()
    if pid is not None and _pid_exists(pid):
        return pid

    for pattern in (
        "manage.py autodb_clone_sync --only passanger_car_trees",
        "run_autodb_clone_sync.sh",
    ):
        found = _find_pid_by_pattern(pattern)
        if found is not None:
            return found
    return None


def _find_pid_by_pattern(pattern: str) -> int | None:
    command = ["pgrep", "-f", pattern]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True)
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            found = int(line)
        except ValueError:
            continue
        if _pid_exists(found):
            return found
    return None


def _read_pid_file() -> int | None:
    path = os.path.expanduser("~/Django/passanger_car_trees_sync.pid")
    if not os.path.exists(path):
        return None
    try:
        raw = open(path, encoding="utf-8").read().strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _count_table_rows(table: str) -> int:
    with connections["auto_db_pro"].cursor() as cursor:
        cursor.execute(f'SELECT COUNT(*)::bigint FROM "{table}"')
        row = cursor.fetchone()
    try:
        return int(row[0]) if row else 0
    except (TypeError, ValueError):
        return 0


def _update_state(
    *,
    state: AutoDbSyncState,
    status: str,
    error: str,
    finished_at: datetime | None,
) -> None:
    state.status = status
    state.last_error = error[:4000]
    if finished_at is not None:
        state.finished_at = finished_at
    metadata: dict[str, Any] = dict(state.metadata or {})
    metadata["updated_at"] = datetime.now(UTC).isoformat()
    metadata["status"] = status
    state.metadata = metadata
    state.save(using="auto_db_pro", update_fields=("status", "last_error", "finished_at", "metadata", "updated_at"))
