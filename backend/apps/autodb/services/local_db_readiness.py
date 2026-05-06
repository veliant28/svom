from __future__ import annotations

from dataclasses import dataclass
import time

from django.conf import settings
from django.db import connections


_RECOVERY_PATTERNS = (
    "the database system is starting up",
    "the database system is not yet accepting connections",
    "consistent recovery state has not been yet reached",
    "the database system is shutting down",
)
_CONNECTION_REFUSED_PATTERNS = (
    "connection refused",
    "could not connect to server",
    "server closed the connection unexpectedly",
    "connection is bad",
    "operation not permitted",
)


@dataclass(frozen=True)
class LocalAutoDbReadinessResult:
    ready: bool
    reason: str
    error_message: str
    host: str
    port: str
    database: str
    attempts: int
    waited_seconds: float


def check_local_autodb_ready() -> LocalAutoDbReadinessResult:
    return _check_local_autodb_ready(attempts=1, waited_seconds=0.0)


def wait_for_local_autodb_ready(*, timeout_seconds: int, interval_seconds: float = 2.0) -> LocalAutoDbReadinessResult:
    timeout = max(int(timeout_seconds or 0), 0)
    interval = max(float(interval_seconds or 0.1), 0.1)
    started = time.monotonic()
    attempts = 0
    result = _check_local_autodb_ready(attempts=1, waited_seconds=0.0)
    attempts += 1

    while (not result.ready) and (time.monotonic() - started) < timeout:
        time.sleep(interval)
        attempts += 1
        result = _check_local_autodb_ready(
            attempts=attempts,
            waited_seconds=round(time.monotonic() - started, 3),
        )

    return LocalAutoDbReadinessResult(
        ready=result.ready,
        reason=result.reason,
        error_message=result.error_message,
        host=result.host,
        port=result.port,
        database=result.database,
        attempts=attempts,
        waited_seconds=round(time.monotonic() - started, 3),
    )


def is_local_autodb_unavailable_error(message: str) -> bool:
    normalized = _normalize_message(message)
    reason = _classify_reason(normalized)
    return reason in {
        "db_starting_or_recovering",
        "connection_unavailable",
        "connection_refused",
        "configuration_error",
    }


def _check_local_autodb_ready(*, attempts: int, waited_seconds: float) -> LocalAutoDbReadinessResult:
    conn = connections["auto_db_pro"]
    host, port, database = _connection_meta(conn)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host=host,
            port=port,
            database=database,
            attempts=attempts,
            waited_seconds=waited_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        raw_message = _sanitize_error_message(str(exc), conn)
        normalized = _normalize_message(raw_message)
        return LocalAutoDbReadinessResult(
            ready=False,
            reason=_classify_reason(normalized),
            error_message=raw_message,
            host=host,
            port=port,
            database=database,
            attempts=attempts,
            waited_seconds=waited_seconds,
        )


def _classify_reason(normalized_message: str) -> str:
    if not normalized_message:
        return "unknown"
    if any(pattern in normalized_message for pattern in _RECOVERY_PATTERNS):
        return "db_starting_or_recovering"
    if any(pattern in normalized_message for pattern in _CONNECTION_REFUSED_PATTERNS):
        return "connection_refused"
    if "does not exist" in normalized_message:
        return "database_not_found"
    if "password authentication failed" in normalized_message:
        return "auth_failed"
    if "could not translate host name" in normalized_message:
        return "configuration_error"
    if "connection to server at" in normalized_message:
        return "connection_unavailable"
    return "unknown"


def _connection_meta(conn) -> tuple[str, str, str]:
    cfg = getattr(conn, "settings_dict", {}) or {}
    host = str(cfg.get("HOST") or "-").strip() or "-"
    port = str(cfg.get("PORT") or "-").strip() or "-"
    database = str(cfg.get("NAME") or "-").strip() or "-"
    return host, port, database


def _normalize_message(message: str) -> str:
    return str(message or "").strip().lower()


def _sanitize_error_message(message: str, conn) -> str:
    sanitized = str(message or "")
    cfg = getattr(conn, "settings_dict", {}) or {}
    password = str(cfg.get("PASSWORD") or "")
    if password:
        sanitized = sanitized.replace(password, "***")
    global_password = str(getattr(settings, "AUTODB_PRO_LOCAL_DATABASE_PASSWORD", "") or "")
    if global_password:
        sanitized = sanitized.replace(global_password, "***")
    return sanitized.strip()
