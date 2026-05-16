from __future__ import annotations

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
                "run": _serialize_run(run),
                "task_id": str(task.id),
                "message": "TecDoc batch queued.",
            },
            status=status.HTTP_202_ACCEPTED,
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
    return (
        AutoDbMatchingRun.objects.filter(
            run_type=BACKOFFICE_TECDOC_BATCH_RUN_TYPE,
            status=AutoDbMatchingRun.STATUS_RUNNING,
        )
        .order_by("-created_at")
        .first()
    )


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
