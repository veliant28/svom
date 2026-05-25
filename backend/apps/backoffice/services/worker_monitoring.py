from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import current_app
from django.conf import settings
from django.core.cache import cache

WORKER_REGISTRY_CACHE_KEY = "backoffice:workers:registry"
WORKER_CPU_HISTORY_CACHE_KEY = "backoffice:workers:cpu_history"
WORKER_RUNTIME_CACHE_KEY = "backoffice:workers:runtime"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:  # NaN
        return default
    return parsed


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _worker_status(*, online: bool, active_count: int, stuck: bool) -> str:
    if not online:
        return "offline"
    if stuck:
        return "stuck"
    if active_count > 0:
        return "active"
    return "idle"


@dataclass
class WorkerSample:
    name: str
    cpu_percent: float
    active_count: int
    reserved_count: int
    scheduled_count: int
    longest_task_seconds: int
    total_tasks_processed: int
    online: bool
    stuck: bool
    status: str
    last_seen_at: datetime
    last_heartbeat_at: datetime
    pool_processes: list[int]
    current_task_ids: list[str]
    current_task_names: list[str]
    queues: list[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cpu_percent": round(self.cpu_percent, 2),
            "active_count": self.active_count,
            "reserved_count": self.reserved_count,
            "scheduled_count": self.scheduled_count,
            "longest_task_seconds": self.longest_task_seconds,
            "total_tasks_processed": self.total_tasks_processed,
            "online": self.online,
            "stuck": self.stuck,
            "status": self.status,
            "last_seen_at": _iso(self.last_seen_at),
            "last_heartbeat_at": _iso(self.last_heartbeat_at),
            "pool_processes": self.pool_processes,
            "current_task_ids": self.current_task_ids,
            "current_task_names": self.current_task_names,
            "queues": self.queues,
        }


class BackofficeWorkerMonitorService:
    def __init__(self) -> None:
        self._history_limit = max(_parse_int(getattr(settings, "BACKOFFICE_WORKER_HISTORY_LIMIT", 240), 240), 30)
        self._offline_ttl_seconds = max(_parse_int(getattr(settings, "BACKOFFICE_WORKER_OFFLINE_TTL_SECONDS", 1800), 1800), 120)
        self._stuck_runtime_seconds = max(_parse_int(getattr(settings, "BACKOFFICE_WORKER_STUCK_RUNTIME_SECONDS", 900), 900), 60)
        self._stuck_no_progress_seconds = max(_parse_int(getattr(settings, "BACKOFFICE_WORKER_STUCK_NO_PROGRESS_SECONDS", 240), 240), 60)
        self._stuck_low_cpu_threshold = max(_parse_float(getattr(settings, "BACKOFFICE_WORKER_STUCK_LOW_CPU_THRESHOLD", 0.6), 0.6), 0.0)

    def collect_dashboard(self) -> dict[str, Any]:
        now = _now_utc()

        inspect = current_app.control.inspect(timeout=0.9)
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        scheduled = inspect.scheduled() or {}
        queues = inspect.active_queues() or {}

        live_workers = sorted(set(stats.keys()) | set(active.keys()) | set(reserved.keys()) | set(scheduled.keys()) | set(queues.keys()))

        prev_runtime = cache.get(WORKER_RUNTIME_CACHE_KEY, {})
        runtime_snapshot: dict[str, dict[str, Any]] = {}

        registry = cache.get(WORKER_REGISTRY_CACHE_KEY, {})
        if not isinstance(registry, dict):
            registry = {}

        samples: list[WorkerSample] = []

        for worker_name in live_workers:
            stat_payload = stats.get(worker_name) or {}
            rusage = stat_payload.get("rusage") or {}
            usage_seconds = _parse_float(rusage.get("utime"), 0.0) + _parse_float(rusage.get("stime"), 0.0)
            uptime_seconds = max(_parse_float(stat_payload.get("uptime"), 0.0), 0.0)

            prev = prev_runtime.get(worker_name) if isinstance(prev_runtime, dict) else None
            cpu_percent = 0.0
            if isinstance(prev, dict):
                prev_usage = _parse_float(prev.get("usage"), 0.0)
                prev_seen_ts = _parse_float(prev.get("seen_ts"), 0.0)
                wall_delta = max(now.timestamp() - prev_seen_ts, 0.0)
                usage_delta = max(usage_seconds - prev_usage, 0.0)
                if wall_delta > 0:
                    cpu_percent = min((usage_delta / wall_delta) * 100.0, 400.0)

            active_tasks = active.get(worker_name) or []
            reserved_tasks = reserved.get(worker_name) or []
            scheduled_tasks = scheduled.get(worker_name) or []
            queue_items = queues.get(worker_name) or []

            active_count = len(active_tasks)
            reserved_count = len(reserved_tasks)
            scheduled_count = len(scheduled_tasks)

            active_task_ids: list[str] = []
            active_task_names: list[str] = []
            max_runtime = 0

            for task in active_tasks:
                if not isinstance(task, dict):
                    continue
                task_id = str(task.get("id") or "").strip()
                task_name = str(task.get("name") or "").strip()
                if task_id:
                    active_task_ids.append(task_id)
                if task_name:
                    active_task_names.append(task_name)
                started_at = _parse_float(task.get("time_start"), 0.0)
                if started_at > 0:
                    max_runtime = max(max_runtime, int(max(now.timestamp() - started_at, 0.0)))

            total_processed = 0
            total_payload = stat_payload.get("total") or {}
            if isinstance(total_payload, dict):
                for value in total_payload.values():
                    total_processed += max(_parse_int(value, 0), 0)

            progress_signature = {
                "task_ids": sorted(active_task_ids),
                "total": total_processed,
                "active": active_count,
            }
            reg_entry = registry.get(worker_name) if isinstance(registry.get(worker_name), dict) else {}
            progress_since = _parse_float(reg_entry.get("progress_since_ts"), now.timestamp())
            if reg_entry.get("progress_signature") != progress_signature:
                progress_since = now.timestamp()

            no_progress_seconds = int(max(now.timestamp() - progress_since, 0.0))
            stuck = bool(
                active_count > 0
                and max_runtime >= self._stuck_runtime_seconds
                and no_progress_seconds >= self._stuck_no_progress_seconds
                and cpu_percent <= self._stuck_low_cpu_threshold
            )

            status = _worker_status(online=True, active_count=active_count, stuck=stuck)

            queue_names: list[str] = []
            for item in queue_items:
                if isinstance(item, dict):
                    queue_name = str(item.get("name") or "").strip()
                    if queue_name:
                        queue_names.append(queue_name)

            pool_processes = []
            pool_payload = stat_payload.get("pool") or {}
            if isinstance(pool_payload, dict):
                raw_processes = pool_payload.get("processes") or []
                if isinstance(raw_processes, list):
                    pool_processes = [_parse_int(value, 0) for value in raw_processes if _parse_int(value, 0) > 0]

            registry[worker_name] = {
                "last_seen_at": _iso(now),
                "last_seen_ts": now.timestamp(),
                "progress_signature": progress_signature,
                "progress_since_ts": progress_since,
                "last_heartbeat_at": _iso(now),
                "status": status,
            }

            runtime_snapshot[worker_name] = {
                "usage": usage_seconds,
                "uptime": uptime_seconds,
                "seen_ts": now.timestamp(),
            }

            samples.append(
                WorkerSample(
                    name=worker_name,
                    cpu_percent=cpu_percent,
                    active_count=active_count,
                    reserved_count=reserved_count,
                    scheduled_count=scheduled_count,
                    longest_task_seconds=max_runtime,
                    total_tasks_processed=total_processed,
                    online=True,
                    stuck=stuck,
                    status=status,
                    last_seen_at=now,
                    last_heartbeat_at=now,
                    pool_processes=pool_processes,
                    current_task_ids=active_task_ids,
                    current_task_names=active_task_names,
                    queues=queue_names,
                )
            )

        # keep recent offline workers visible
        for worker_name, entry in list(registry.items()):
            if any(item.name == worker_name for item in samples):
                continue
            if not isinstance(entry, dict):
                continue
            last_seen_ts = _parse_float(entry.get("last_seen_ts"), 0.0)
            if last_seen_ts <= 0:
                continue
            offline_for = now - datetime.fromtimestamp(last_seen_ts, tz=timezone.utc)
            if offline_for > timedelta(seconds=self._offline_ttl_seconds):
                registry.pop(worker_name, None)
                continue

            last_seen_at = datetime.fromtimestamp(last_seen_ts, tz=timezone.utc)
            last_heartbeat_raw = str(entry.get("last_heartbeat_at") or "").strip()
            try:
                last_heartbeat_at = datetime.fromisoformat(last_heartbeat_raw) if last_heartbeat_raw else last_seen_at
                if last_heartbeat_at.tzinfo is None:
                    last_heartbeat_at = last_heartbeat_at.replace(tzinfo=timezone.utc)
            except ValueError:
                last_heartbeat_at = last_seen_at

            samples.append(
                WorkerSample(
                    name=worker_name,
                    cpu_percent=0.0,
                    active_count=0,
                    reserved_count=0,
                    scheduled_count=0,
                    longest_task_seconds=0,
                    total_tasks_processed=0,
                    online=False,
                    stuck=False,
                    status="offline",
                    last_seen_at=last_seen_at,
                    last_heartbeat_at=last_heartbeat_at,
                    pool_processes=[],
                    current_task_ids=[],
                    current_task_names=[],
                    queues=[],
                )
            )

        samples.sort(key=lambda item: (item.online is False, item.status != "stuck", item.status != "active", item.name.lower()))

        status_counts = {
            "active": sum(1 for item in samples if item.status == "active"),
            "idle": sum(1 for item in samples if item.status == "idle"),
            "stuck": sum(1 for item in samples if item.status == "stuck"),
            "offline": sum(1 for item in samples if item.status == "offline"),
        }

        history = cache.get(WORKER_CPU_HISTORY_CACHE_KEY, [])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "timestamp": _iso(now),
                "workers": {item.name: round(item.cpu_percent, 2) for item in samples if item.online},
            }
        )
        history = history[-self._history_limit :]

        cache.set(WORKER_CPU_HISTORY_CACHE_KEY, history, timeout=self._offline_ttl_seconds * 4)
        cache.set(WORKER_REGISTRY_CACHE_KEY, registry, timeout=self._offline_ttl_seconds * 4)
        cache.set(WORKER_RUNTIME_CACHE_KEY, runtime_snapshot, timeout=self._offline_ttl_seconds * 4)

        return {
            "generated_at": _iso(now),
            "workers": [item.to_payload() for item in samples],
            "status_counts": status_counts,
            "cpu_history": history,
        }


class BackofficeWorkerControlService:
    def stop_worker(self, *, worker_name: str) -> dict[str, Any]:
        reply = current_app.control.broadcast("shutdown", destination=[worker_name], reply=True)
        return {
            "status": "ok",
            "action": "stop",
            "worker": worker_name,
            "reply": reply,
        }

    def restart_worker(self, *, worker_name: str) -> dict[str, Any]:
        # Celery has no universal in-place restart command.
        # We trigger graceful shutdown; external process manager should restart it.
        reply = current_app.control.broadcast("shutdown", destination=[worker_name], reply=True)
        return {
            "status": "ok",
            "action": "restart",
            "worker": worker_name,
            "reply": reply,
            "detail": "shutdown_sent",
        }

    def pause_worker(self, *, worker_name: str, queues: list[str]) -> dict[str, Any]:
        queue_names = sorted(set(queue for queue in queues if queue)) or ["celery"]
        replies: list[Any] = []
        for queue_name in queue_names:
            response = current_app.control.cancel_consumer(queue_name, destination=[worker_name], reply=True)
            replies.append({"queue": queue_name, "reply": response})
        return {
            "status": "ok",
            "action": "pause",
            "worker": worker_name,
            "queues": queue_names,
            "reply": replies,
        }

    def resume_worker(self, *, worker_name: str, queues: list[str]) -> dict[str, Any]:
        queue_names = sorted(set(queue for queue in queues if queue)) or ["celery"]
        replies: list[Any] = []
        for queue_name in queue_names:
            response = current_app.control.add_consumer(queue_name, destination=[worker_name], reply=True)
            replies.append({"queue": queue_name, "reply": response})
        return {
            "status": "ok",
            "action": "resume",
            "worker": worker_name,
            "queues": queue_names,
            "reply": replies,
        }

    def kill_task(self, *, task_id: str) -> dict[str, Any]:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return {
                "status": "error",
                "action": "kill_task",
                "detail": "task_id_required",
            }
        current_app.control.revoke(normalized_task_id, terminate=True, signal="SIGKILL")
        return {
            "status": "ok",
            "action": "kill_task",
            "task_id": normalized_task_id,
            "detail": "revoke_sent",
        }
