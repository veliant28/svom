from __future__ import annotations

from datetime import timedelta

from celery import current_app
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from apps.autodb.models import AutoDbMatchingRun
from apps.autodb.tasks import BACKOFFICE_TECDOC_BATCH_RUN_TYPE, run_backoffice_tecdoc_batch_bind_task

from .._base import BackofficeAPIView
from .utils import parse_positive_int, safe_str


class BackofficeAutoDbMatchingTecdocBatchRunAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        active = _active_batch_run()
        if active is not None:
            return Response(
                {
                    "dry_run": False,
                    "created": False,
                    "status": "already_running",
                    "run": _serialize_run(active),
                    "message": "TecDoc batch is already running.",
                },
                status=status.HTTP_200_OK,
            )

        product_ids = _parse_product_ids(request.data.get("product_ids"))
        if product_ids:
            batch_size = len(product_ids)
        else:
            batch_size = parse_positive_int(request.data.get("batch_size"), default=200, maximum=1000)
        actor = str(getattr(request.user, "id", "") or "")
        run = AutoDbMatchingRun.objects.create(
            run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE,
            status=AutoDbMatchingRun.STATUS_RUNNING,
            dry_run=False,
            created_by_source=f"backoffice:{safe_str(getattr(request.user, 'email', '')) or actor}",
            summary_json={
                "running": True,
                "requested_limit": batch_size,
                "processed": 0,
                "bound": 0,
                "failed": 0,
                "stopped_reason": "",
                "last_error": "",
            },
        )
        task = run_backoffice_tecdoc_batch_bind_task.delay(
            run_id=str(run.id),
            limit=int(batch_size),
            actor_id=actor,
            product_ids=product_ids or None,
        )
        run.summary_json = {
            **(run.summary_json or {}),
            "task_id": str(task.id),
        }
        run.save(update_fields=["summary_json", "updated_at"])
        return Response(
            {
                "dry_run": False,
                "created": True,
                "status": "queued",
                "selected_products_count": len(product_ids),
                "run": _serialize_run(run),
                "task_id": str(task.id),
                "message": "TecDoc batch queued.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BackofficeAutoDbMatchingTecdocBatchStopAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def post(self, request):
        del request
        active = _active_batch_run()
        if active is None:
            return Response(
                {
                    "dry_run": False,
                    "status": "no_active_run",
                    "stopped": False,
                    "message": "No active TecDoc batch run.",
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
        return Response(
            {
                "dry_run": False,
                "status": "stopped",
                "stopped": True,
                "revoked": revoked,
                "run": _serialize_run(active),
                "message": "TecDoc batch stop requested.",
            },
            status=status.HTTP_200_OK,
        )


class BackofficeAutoDbMatchingTecdocBatchStateAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        active = _active_batch_run()
        latest = (
            AutoDbMatchingRun.objects.filter(run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE)
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


def _active_batch_run() -> AutoDbMatchingRun | None:
    run = (
        AutoDbMatchingRun.objects.filter(
            run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE,
            status=AutoDbMatchingRun.STATUS_RUNNING,
        )
        .order_by("-created_at")
        .first()
    )
    if run is None:
        return None

    # Guard against stale runs that can block UI button forever if worker/session died.
    now = timezone.now()
    if run.updated_at and run.updated_at < (now - timedelta(minutes=15)):
        summary = dict(run.summary_json or {})
        summary["running"] = False
        summary["stopped_reason"] = summary.get("stopped_reason") or "stale_timeout"
        summary["last_error"] = summary.get("last_error") or "stale run auto-closed"
        summary["finished_at"] = now.isoformat()
        run.summary_json = summary
        run.status = AutoDbMatchingRun.STATUS_PARTIAL
        run.finished_at = now
        run.error = "stale run auto-closed"
        run.save(update_fields=["summary_json", "status", "finished_at", "error", "updated_at"])
        return None

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
