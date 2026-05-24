from __future__ import annotations

from datetime import datetime, timedelta

from celery import current_app
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from apps.autodb.models import AutoDbMatchingRun
from apps.autodb.tasks import (
    BACKOFFICE_TECDOC_API_BATCH_RUN_TYPE,
    BACKOFFICE_TECDOC_BATCH_RUN_TYPE,
    run_backoffice_tecdoc_batch_bind_task,
)
from apps.core.services import (
    send_system_autodb_batch_started_notification,
    send_system_autodb_batch_stopped_notification,
)

from .._base import BackofficeAPIView
from .utils import parse_bool, parse_positive_int, safe_str


def _actor_label(user) -> str:
    if user is None:
        return "-"
    full_name = str((user.get_full_name() or "")).strip()
    if full_name:
        return full_name
    email = str(getattr(user, "email", "") or "").strip()
    if email:
        return email
    return str(getattr(user, "id", "") or "-")


def _resolve_batch_task_limits(batch_size: int) -> tuple[int, int]:
    normalized_size = max(int(batch_size or 0), 1)
    soft_base = max(int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_SOFT_TIME_LIMIT_BASE_SECONDS", 60 * 15) or 0), 300)
    per_item = max(int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_SOFT_TIME_LIMIT_PER_ITEM_SECONDS", 55) or 0), 30)
    hard_grace = max(int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_TIME_LIMIT_GRACE_SECONDS", 60 * 15) or 0), 60)
    max_hard_limit = max(
        int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_MAX_TIME_LIMIT_SECONDS", 60 * 60 * 10) or 0),
        soft_base + hard_grace,
    )

    soft_limit = soft_base + (normalized_size * per_item)
    hard_limit = soft_limit + hard_grace
    if max_hard_limit > 0:
        hard_limit = min(hard_limit, max_hard_limit)
        soft_limit = min(soft_limit, max(hard_limit - 60, 60))
    if soft_limit >= hard_limit:
        soft_limit = max(60, hard_limit - 60)
    return soft_limit, hard_limit


def _resolve_continuous_batch_task_limits() -> tuple[int, int]:
    soft_limit = max(
        int(getattr(settings, "AUTODB_BACKOFFICE_CONTINUOUS_BATCH_SOFT_TIME_LIMIT_SECONDS", 60 * 60 * 24) or 0),
        60 * 60,
    )
    hard_limit = max(
        int(getattr(settings, "AUTODB_BACKOFFICE_CONTINUOUS_BATCH_TIME_LIMIT_SECONDS", soft_limit + 60 * 60) or 0),
        soft_limit + 60,
    )
    return soft_limit, hard_limit


class BackofficeAutoDbMatchingTecdocBatchRunAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        return _run_batch(
            request=request,
            run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE,
            batch_title="TecDoc batch",
            strict_tecdoc_only=False,
            batch_source="legacy_batch",
        )


class BackofficeAutoDbMatchingTecdocBatchStopAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        return _stop_batch(
            request=request,
            run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE,
            batch_title="TecDoc batch",
        )


class BackofficeAutoDbMatchingTecdocBatchStateAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        return _state_batch(run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE)


class BackofficeAutoDbMatchingTecdocApiBatchRunAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        return _run_batch(
            request=request,
            run_type=BACKOFFICE_TECDOC_API_BATCH_RUN_TYPE,
            batch_title="TecDoc API batch",
            strict_tecdoc_only=True,
            batch_source="tecdoc_api",
        )


class BackofficeAutoDbMatchingTecdocApiBatchStopAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        return _stop_batch(
            request=request,
            run_type=BACKOFFICE_TECDOC_API_BATCH_RUN_TYPE,
            batch_title="TecDoc API batch",
        )


class BackofficeAutoDbMatchingTecdocApiBatchStateAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        return _state_batch(run_type=BACKOFFICE_TECDOC_API_BATCH_RUN_TYPE)


def _run_batch(
    *,
    request,
    run_type: str,
    batch_title: str,
    strict_tecdoc_only: bool,
    batch_source: str,
) -> Response:
    active = _active_batch_run(run_type=run_type)
    if active is not None:
        return Response(
            {
                "dry_run": False,
                "created": False,
                "status": "already_running",
                "run": _serialize_run(active),
                "message": f"{batch_title} is already running.",
            },
            status=status.HTTP_200_OK,
        )

    product_ids = _parse_product_ids(request.data.get("product_ids"))
    continuous_requested = parse_bool(request.data.get("continuous")) is True
    # Keep bulk/product_ids mode backward-compatible (single-pass only).
    continuous = bool(continuous_requested and not product_ids)
    if product_ids:
        batch_size = len(product_ids)
    else:
        batch_size = parse_positive_int(request.data.get("batch_size"), default=50, maximum=1000)
    actor = str(getattr(request.user, "id", "") or "")
    run = AutoDbMatchingRun.objects.create(
        run_type=run_type,
        status=AutoDbMatchingRun.STATUS_RUNNING,
        dry_run=False,
        created_by_source=f"backoffice:{safe_str(getattr(request.user, 'email', '')) or actor}",
        summary_json={
            "running": True,
            "requested_limit": batch_size,
            "processed": 0,
            "bound": 0,
            "failed": 0,
            "continuous": continuous,
            "strict_tecdoc_only": bool(strict_tecdoc_only),
            "batch_source": str(batch_source or "legacy_batch"),
            "stopped_reason": "",
            "last_error": "",
        },
    )
    soft_time_limit, time_limit = (
        _resolve_continuous_batch_task_limits()
        if continuous
        else _resolve_batch_task_limits(int(batch_size))
    )
    task = run_backoffice_tecdoc_batch_bind_task.apply_async(
        kwargs={
            "run_id": str(run.id),
            "limit": int(batch_size),
            "actor_id": actor,
            "product_ids": product_ids or None,
            "continuous": continuous,
            "strict_tecdoc_only": bool(strict_tecdoc_only),
            "batch_source": str(batch_source or "legacy_batch"),
        },
        soft_time_limit=soft_time_limit,
        time_limit=time_limit,
    )
    run.summary_json = {
        **(run.summary_json or {}),
        "task_id": str(task.id),
        "task_soft_time_limit_seconds": int(soft_time_limit),
        "task_time_limit_seconds": int(time_limit),
        "continuous": continuous,
    }
    run.save(update_fields=["summary_json", "updated_at"])
    send_system_autodb_batch_started_notification(
        run_id=str(run.id),
        actor_name=_actor_label(getattr(request, "user", None)),
        requested_limit=int(batch_size),
        selected_products_count=len(product_ids),
    )
    return Response(
        {
            "dry_run": False,
            "created": True,
            "status": "queued",
            "selected_products_count": len(product_ids),
            "run": _serialize_run(run),
            "task_id": str(task.id),
            "message": f"{batch_title} queued.",
        },
        status=status.HTTP_202_ACCEPTED,
    )


def _stop_batch(*, request, run_type: str, batch_title: str) -> Response:
    active = _active_batch_run(run_type=run_type)
    if active is None:
        return Response(
            {
                "dry_run": False,
                "status": "no_active_run",
                "stopped": False,
                "message": f"No active {batch_title} run.",
            },
            status=status.HTTP_200_OK,
        )

    summary = dict(active.summary_json or {})
    task_id = safe_str(summary.get("task_id"))
    revoked = False
    if task_id:
        current_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
        revoked = True

    now = timezone.now()
    summary["running"] = False
    summary["stopped_reason"] = "manual_stop"
    summary["last_error"] = summary.get("last_error") or "manual stop requested"
    summary["finished_at"] = now.isoformat()
    active.summary_json = summary
    active.status = AutoDbMatchingRun.STATUS_PARTIAL
    active.finished_at = now
    active.error = "manual stop requested"
    active.save(update_fields=["summary_json", "status", "finished_at", "error", "updated_at"])
    send_system_autodb_batch_stopped_notification(
        run_id=str(active.id),
        actor_name=_actor_label(getattr(request, "user", None)),
        processed=int(summary.get("processed") or 0),
        found=int(summary.get("bound") or 0),
        linked=int(summary.get("bound") or 0),
        not_found=int(summary.get("failed") or 0),
        stop_reason=str(summary.get("stopped_reason") or "manual_stop"),
    )
    return Response(
        {
            "dry_run": False,
            "status": "stopped",
            "stopped": True,
            "revoked": revoked,
            "run": _serialize_run(active),
            "message": f"{batch_title} stop requested.",
        },
        status=status.HTTP_200_OK,
    )


def _state_batch(*, run_type: str) -> Response:
    active = _active_batch_run(run_type=run_type)
    latest = (
        AutoDbMatchingRun.objects.filter(run_type=run_type)
        .order_by("-created_at")
        .first()
    )
    return Response(
        {
            "running": active is not None,
            "active_run": _serialize_run(active) if active is not None else None,
            "latest_run": _serialize_run(latest) if latest is not None else None,
        }
    )


def _active_batch_run(*, run_type: str) -> AutoDbMatchingRun | None:
    run = (
        AutoDbMatchingRun.objects.filter(
            run_type=run_type,
            status=AutoDbMatchingRun.STATUS_RUNNING,
        )
        .order_by("-created_at")
        .first()
    )
    if run is None:
        return None

    now = timezone.now()
    summary = dict(run.summary_json or {})
    if _should_recover_orphaned_run(run=run, summary=summary, now=now):
        resumed = _try_resume_orphaned_run(run=run, summary=summary)
        if resumed is not None:
            return resumed
        _close_stale_run(run=run, summary=summary, now=now, reason="orphaned_task")
        return None

    # Guard against stale runs that can block UI button forever if worker/session died.
    if run.updated_at and run.updated_at < (now - timedelta(minutes=15)):
        _close_stale_run(run=run, summary=summary, now=now, reason="stale_timeout")
        return None

    return run


def _close_stale_run(*, run: AutoDbMatchingRun, summary: dict, now, reason: str) -> None:
    if reason == "orphaned_task":
        fallback_error = "orphaned run auto-closed"
    else:
        fallback_error = "stale run auto-closed"
    summary["running"] = False
    summary["stopped_reason"] = summary.get("stopped_reason") or reason
    summary["last_error"] = summary.get("last_error") or fallback_error
    summary["finished_at"] = now.isoformat()
    run.summary_json = summary
    run.status = AutoDbMatchingRun.STATUS_PARTIAL
    run.finished_at = now
    run.error = fallback_error
    run.save(update_fields=["summary_json", "status", "finished_at", "error", "updated_at"])


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _resolve_last_heartbeat(*, run: AutoDbMatchingRun, summary: dict):
    parsed = _parse_iso_datetime(str(summary.get("last_heartbeat_at") or ""))
    if parsed is not None:
        return parsed
    return run.updated_at or run.started_at


def _task_visible_for_workers(task_id: str) -> bool:
    try:
        inspector = current_app.control.inspect(timeout=0.8)
        query = inspector.query_task(task_id) or {}
        for worker_payload in query.values():
            if isinstance(worker_payload, dict) and task_id in worker_payload:
                return True
        active = inspector.active() or {}
        for worker_tasks in active.values():
            for task in worker_tasks or []:
                if str((task or {}).get("id") or "") == task_id:
                    return True
        reserved = inspector.reserved() or {}
        for worker_tasks in reserved.values():
            for task in worker_tasks or []:
                if str((task or {}).get("id") or "") == task_id:
                    return True
        scheduled = inspector.scheduled() or {}
        for worker_entries in scheduled.values():
            for entry in worker_entries or []:
                request = (entry or {}).get("request") or {}
                if str(request.get("id") or "") == task_id:
                    return True
        return False
    except Exception:  # noqa: BLE001
        # If inspect is unavailable, do not auto-close/requeue to avoid false positives.
        return True


def _should_recover_orphaned_run(*, run: AutoDbMatchingRun, summary: dict, now) -> bool:
    task_id = safe_str(summary.get("task_id"))
    if not task_id:
        return False
    heartbeat = _resolve_last_heartbeat(run=run, summary=summary)
    if heartbeat is None:
        return False
    grace_seconds = max(int(getattr(settings, "AUTODB_BACKOFFICE_ORPHAN_TASK_GRACE_SECONDS", 180) or 180), 60)
    if heartbeat >= (now - timedelta(seconds=grace_seconds)):
        return False
    return not _task_visible_for_workers(task_id)


def _try_resume_orphaned_run(*, run: AutoDbMatchingRun, summary: dict) -> AutoDbMatchingRun | None:
    # Only continuous mode can be safely auto-resumed.
    if not bool(summary.get("continuous")):
        return None
    requested_limit = parse_positive_int(summary.get("requested_limit"), default=50, maximum=1000)
    actor_id = safe_str(summary.get("actor_id"))
    strict_tecdoc_only = bool(summary.get("strict_tecdoc_only"))
    batch_source = safe_str(summary.get("batch_source")) or ("tecdoc_api" if run.run_type == BACKOFFICE_TECDOC_API_BATCH_RUN_TYPE else "legacy_batch")
    soft_time_limit, time_limit = _resolve_continuous_batch_task_limits()
    task = run_backoffice_tecdoc_batch_bind_task.apply_async(
        kwargs={
            "run_id": str(run.id),
            "limit": int(requested_limit),
            "actor_id": actor_id,
            "product_ids": None,
            "continuous": True,
            "strict_tecdoc_only": bool(strict_tecdoc_only),
            "batch_source": str(batch_source),
        },
        soft_time_limit=soft_time_limit,
        time_limit=time_limit,
    )
    summary["task_id"] = str(task.id)
    summary["task_soft_time_limit_seconds"] = int(soft_time_limit)
    summary["task_time_limit_seconds"] = int(time_limit)
    summary["running"] = True
    summary["retry_reason"] = "orphan_requeued"
    summary["retry_in_seconds"] = 0
    previous_error = safe_str(summary.get("last_error"))
    summary["last_error"] = previous_error or "orphaned task auto-requeued"
    run.summary_json = summary
    run.save(update_fields=["summary_json", "updated_at"])
    return run


def _serialize_run(run: AutoDbMatchingRun) -> dict:
    summary = dict(run.summary_json or {})
    return {
        "id": str(run.id),
        "status": run.status,
        "run_type": run.run_type,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "summary": summary,
        "error": safe_str(run.error),
    }


def _parse_product_ids(value: object) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str) and value.strip():
        items = [value]
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        candidate = safe_str(item)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out[:1000]
