from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.services.worker_monitoring import BackofficeWorkerControlService, BackofficeWorkerMonitorService


class BackofficeWorkersDashboardAPIView(BackofficeAPIView):
    required_capability = "workers.manage"

    def get(self, request):
        payload = BackofficeWorkerMonitorService().collect_dashboard()
        return Response(payload, status=status.HTTP_200_OK)


class BackofficeWorkersActionAPIView(BackofficeAPIView):
    required_capability = "workers.manage"

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        action = str(body.get("action") or "").strip().lower()
        worker_name = str(body.get("worker") or "").strip()
        queues = body.get("queues")
        queue_list = [str(item).strip() for item in queues] if isinstance(queues, list) else []
        task_id = str(body.get("task_id") or "").strip()

        service = BackofficeWorkerControlService()

        if action in {"stop", "restart", "pause", "resume"} and not worker_name:
            return Response({"detail": "worker is required."}, status=status.HTTP_400_BAD_REQUEST)

        if action == "stop":
            payload = service.stop_worker(worker_name=worker_name)
        elif action == "restart":
            payload = service.restart_worker(worker_name=worker_name)
        elif action == "pause":
            payload = service.pause_worker(worker_name=worker_name, queues=queue_list)
        elif action == "resume":
            payload = service.resume_worker(worker_name=worker_name, queues=queue_list)
        elif action == "kill_task":
            payload = service.kill_task(task_id=task_id)
            if payload.get("status") != "ok":
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": "Unsupported action."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload, status=status.HTTP_200_OK)
