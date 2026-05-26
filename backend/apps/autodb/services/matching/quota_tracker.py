from __future__ import annotations

import os
import re
import sys
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.autodb.models import AutoDbRemoteQuotaState

DEFAULT_LIMIT_PER_HOUR = 10000
WINDOW_MINUTES = 60
MAX_POINTS = 180
_BASIC_AUTH_RE = re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)
_MYSQL_USER_RE = re.compile(r"User\s+'[^']+'", re.IGNORECASE)
_CURRENT_VALUE_RE = re.compile(r"current value:\s*(\d+)", re.IGNORECASE)


class AutoDbRemoteQuotaTracker:
    def record_success(
        self,
        quota: AutoDbRemoteQuotaState,
        *,
        query_count: int,
        run_id: str = "",
        status: str = "ok",
    ) -> AutoDbRemoteQuotaState:
        now = timezone.now()
        with transaction.atomic():
            locked = self._lock_quota(quota)
            _window_reset_applied, quota_recovered = self._ensure_window(locked, now=now)
            count = max(int(query_count or 0), 0)
            previous_used = int(locked.estimated_queries_used or 0)
            optimistic_used = previous_used + count
            locked.last_ok_at = now
            locked.last_query_at = now
            locked.last_error = ""
            consumer = self._consumer_name(run_id=run_id)
            updated_points = self._append_point(
                locked.recent_points_json,
                timestamp=now,
                query_count=count,
                cumulative_used=optimistic_used,
                run_id=run_id,
                consumer=consumer,
                status=status,
            )
            recent_points = self._recent_points(updated_points, now=now)
            rolling_used = self._rolling_used(recent_points)
            self._sync_window_from_points(locked, recent_points=recent_points, now=now)
            locked.estimated_queries_used = rolling_used
            locked.recent_points_json = self._recompute_cumulative_points(recent_points)
            locked.save(
                update_fields=[
                    "estimated_limit_per_hour",
                    "window_started_at",
                    "expected_reset_at",
                    "estimated_queries_used",
                    "last_ok_at",
                    "last_query_at",
                    "last_quota_error_at",
                    "cooldown_until",
                    "last_error",
                    "recent_points_json",
                    "updated_at",
                ]
            )
            if quota_recovered:
                remote_key = str(locked.remote_key or "")
                transaction.on_commit(lambda: self._notify_quota_recovered(remote_key=remote_key))
            return locked

    def record_quota_error(
        self,
        quota: AutoDbRemoteQuotaState,
        *,
        error: str,
        cooldown_minutes: int,
        run_id: str = "",
    ) -> AutoDbRemoteQuotaState:
        now = timezone.now()
        with transaction.atomic():
            locked = self._lock_quota(quota)
            self._ensure_window(locked, now=now)
            sanitized_error = self._sanitize_error(error)
            inferred_limit = self._infer_limit_from_error(sanitized_error)
            if inferred_limit > 0:
                configured_limit = max(
                    int(getattr(settings, "AUTODB_PRO_REMOTE_LIMIT_PER_HOUR", DEFAULT_LIMIT_PER_HOUR) or DEFAULT_LIMIT_PER_HOUR),
                    1,
                )
                normalized_limit = min(inferred_limit, configured_limit)
                locked.estimated_limit_per_hour = normalized_limit
                # If MySQL already returned ER_USER_LIMIT_REACHED, real usage has reached
                # the account quota threshold for the current window.
                locked.estimated_queries_used = max(int(locked.estimated_queries_used or 0), normalized_limit)
            locked.last_quota_error_at = now
            locked.last_query_at = now
            locked.cooldown_until = now + timedelta(minutes=int(cooldown_minutes))
            locked.expected_reset_at = locked.cooldown_until
            locked.last_error = sanitized_error
            consumer = self._consumer_name(run_id=run_id)
            locked.recent_points_json = self._append_point(
                locked.recent_points_json,
                timestamp=now,
                query_count=0,
                cumulative_used=int(locked.estimated_queries_used or 0),
                run_id=run_id,
                consumer=consumer,
                status="quota_paused",
                error=sanitized_error,
            )
            locked.save(
                update_fields=[
                    "estimated_limit_per_hour",
                    "estimated_queries_used",
                    "window_started_at",
                    "expected_reset_at",
                    "last_quota_error_at",
                    "last_query_at",
                    "cooldown_until",
                    "last_error",
                    "recent_points_json",
                    "updated_at",
                ]
            )
            return locked

    def serialize(self, quota: AutoDbRemoteQuotaState | None) -> dict[str, Any]:
        now = timezone.now()
        if quota is None:
            limit = DEFAULT_LIMIT_PER_HOUR
            return self._payload(status="ok", limit=limit, used=0, now=now, recent_points=[])

        window_reset_applied, quota_recovered = self._ensure_window(quota, now=now)
        if window_reset_applied:
            quota.save(
                update_fields=[
                    "estimated_limit_per_hour",
                    "window_started_at",
                    "expected_reset_at",
                    "estimated_queries_used",
                    "cooldown_until",
                    "last_error",
                    "recent_points_json",
                    "updated_at",
                ]
            )
        if quota_recovered:
            self._notify_quota_recovered(remote_key=str(quota.remote_key or ""))
        paused = bool(quota.cooldown_until and quota.cooldown_until > now)
        status = "quota_paused" if paused else self._usage_status(quota)
        recent_points = self._recent_points(quota.recent_points_json, now=now)
        return self._payload(
            status=status,
            limit=int(quota.estimated_limit_per_hour or DEFAULT_LIMIT_PER_HOUR),
            used=int(quota.estimated_queries_used or 0),
            now=now,
            recent_points=recent_points,
            quota=quota,
        )

    def _ensure_window(self, quota: AutoDbRemoteQuotaState, *, now) -> tuple[bool, bool]:
        configured_limit = max(int(getattr(settings, "AUTODB_PRO_REMOTE_LIMIT_PER_HOUR", DEFAULT_LIMIT_PER_HOUR) or DEFAULT_LIMIT_PER_HOUR), 1)
        current_limit = int(quota.estimated_limit_per_hour or 0)
        quota.estimated_limit_per_hour = min(current_limit, configured_limit) if current_limit > 0 else configured_limit
        changed = False
        quota_recovered = False
        recent_points = self._recent_points(quota.recent_points_json, now=now)

        # Keep rolling-window accounting in normal mode, but when remote cooldown
        # fully expires we intentionally start a fresh cycle from zero.
        if quota.cooldown_until and quota.cooldown_until <= now:
            quota.cooldown_until = None
            quota.last_error = ""
            quota_recovered = True
            recent_points = []
            changed = True

        recomputed_points = self._recompute_cumulative_points(recent_points)
        rolling_used = self._rolling_used(recent_points)

        if quota.recent_points_json != recomputed_points:
            quota.recent_points_json = recomputed_points
            changed = True

        if int(quota.estimated_queries_used or 0) != rolling_used:
            quota.estimated_queries_used = rolling_used
            changed = True

        changed = self._sync_window_from_points(quota, recent_points=recent_points, now=now) or changed

        return changed, quota_recovered

    def _notify_quota_recovered(self, *, remote_key: str) -> None:
        try:
            from apps.core.services import send_system_autodb_quota_recovered_notification

            send_system_autodb_quota_recovered_notification(remote_key=remote_key)
        except Exception:  # noqa: BLE001
            return

    def _append_point(
        self,
        points: Any,
        *,
        timestamp,
        query_count: int,
        cumulative_used: int,
        run_id: str,
        consumer: str,
        status: str,
        error: str = "",
    ) -> list[dict]:
        bucket = timestamp.replace(second=0, microsecond=0).isoformat()
        out = [item for item in points if isinstance(item, dict)] if isinstance(points, list) else []
        for item in out:
            if (
                item.get("timestamp") == bucket
                and item.get("run_id", "") == run_id
                and item.get("consumer", "") == consumer
                and item.get("status", "") == status
            ):
                item["query_count"] = int(item.get("query_count") or 0) + query_count
                item["cumulative_used"] = cumulative_used
                if error:
                    item["error"] = error
                return out[-MAX_POINTS:]
        out.append(
            {
                "timestamp": bucket,
                "query_count": query_count,
                "cumulative_used": cumulative_used,
                "run_id": run_id,
                "consumer": consumer,
                "status": status,
                "error": error,
            }
        )
        return out[-MAX_POINTS:]

    def _recent_points(self, points: Any, *, now) -> list[dict]:
        raw = [item for item in points if isinstance(item, dict)] if isinstance(points, list) else []
        cutoff = now - timedelta(minutes=WINDOW_MINUTES)
        return [item for item in raw if self._point_is_recent(item, cutoff=cutoff)][-MAX_POINTS:]

    def _rolling_used(self, points: list[dict]) -> int:
        return sum(max(int(item.get("query_count") or 0), 0) for item in points)

    def _recompute_cumulative_points(self, points: list[dict]) -> list[dict]:
        cumulative = 0
        normalized: list[dict] = []
        for raw in points:
            query_count = max(int(raw.get("query_count") or 0), 0)
            cumulative += query_count
            next_point = dict(raw)
            next_point["query_count"] = query_count
            next_point["cumulative_used"] = cumulative
            normalized.append(next_point)
        return normalized

    def _sync_window_from_points(self, quota: AutoDbRemoteQuotaState, *, recent_points: list[dict], now) -> bool:
        current_started = quota.window_started_at
        current_reset = quota.expected_reset_at
        if recent_points:
            first_dt = self._point_datetime(recent_points[0])
            if first_dt is None:
                started = now.replace(second=0, microsecond=0)
            else:
                started = first_dt
            reset_at = started + timedelta(minutes=WINDOW_MINUTES)
        else:
            started = now.replace(second=0, microsecond=0)
            reset_at = started + timedelta(minutes=WINDOW_MINUTES)
        if current_started != started or current_reset != reset_at:
            quota.window_started_at = started
            quota.expected_reset_at = reset_at
            return True
        return False

    def _point_datetime(self, item: dict) -> timezone.datetime | None:
        try:
            value = timezone.datetime.fromisoformat(str(item.get("timestamp")))
        except (TypeError, ValueError):
            return None
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def _point_is_recent(self, item: dict, *, cutoff) -> bool:
        try:
            value = timezone.datetime.fromisoformat(str(item.get("timestamp")))
        except (TypeError, ValueError):
            return False
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value >= cutoff

    def _usage_status(self, quota: AutoDbRemoteQuotaState) -> str:
        limit = max(int(quota.estimated_limit_per_hour or DEFAULT_LIMIT_PER_HOUR), 1)
        percent = int(quota.estimated_queries_used or 0) / limit * 100
        if percent >= 80:
            return "warning"
        return "ok"

    def _payload(self, *, status: str, limit: int, used: int, now, recent_points: list[dict], quota=None) -> dict[str, Any]:
        remaining = max(limit - used, 0)
        reset_at = getattr(quota, "expected_reset_at", None) if quota is not None else now + timedelta(minutes=WINDOW_MINUTES)
        seconds_until_reset = max(int((reset_at - now).total_seconds()), 0) if reset_at else 0
        consumers = self._consumers_breakdown(recent_points)
        top_consumers = consumers[:3]
        return {
            "status": status,
            "estimated_limit_per_hour": limit,
            "estimated_queries_used": used,
            "estimated_queries_remaining": remaining,
            "usage_percent": round((used / max(limit, 1)) * 100, 2),
            "window_started_at": getattr(quota, "window_started_at", None).isoformat() if quota and quota.window_started_at else None,
            "expected_reset_at": reset_at.isoformat() if reset_at else None,
            "seconds_until_reset": seconds_until_reset,
            "last_ok_at": getattr(quota, "last_ok_at", None).isoformat() if quota and quota.last_ok_at else None,
            "last_query_at": getattr(quota, "last_query_at", None).isoformat() if quota and quota.last_query_at else None,
            "last_quota_error_at": getattr(quota, "last_quota_error_at", None).isoformat() if quota and quota.last_quota_error_at else None,
            "cooldown_until": getattr(quota, "cooldown_until", None).isoformat() if quota and quota.cooldown_until else None,
            "recent_points": recent_points,
            "consumers_breakdown": consumers,
            "top_consumers": top_consumers,
        }

    def is_paused(self, quota: AutoDbRemoteQuotaState | None) -> bool:
        payload = self.serialize(quota)
        return str(payload.get("status") or "") == "quota_paused"

    def _sanitize_error(self, error: str) -> str:
        text = _BASIC_AUTH_RE.sub(r"\1", str(error or ""))
        text = _MYSQL_USER_RE.sub("User '[redacted]'", text)
        return text[:300]

    def _infer_limit_from_error(self, error: str) -> int:
        message = str(error or "")
        if "max_questions" not in message.lower():
            return 0
        match = _CURRENT_VALUE_RE.search(message)
        if not match:
            return 0
        inferred = int(match.group(1) or 0)
        return max(inferred, 0)

    def _lock_quota(self, quota: AutoDbRemoteQuotaState) -> AutoDbRemoteQuotaState:
        return AutoDbRemoteQuotaState.objects.select_for_update().get(pk=quota.pk)

    def _consumer_name(self, *, run_id: str) -> str:
        token = str(run_id or "").strip().lower()
        if token.startswith("catalog-"):
            return "catalog"
        if token.startswith("manual-") or "manual" in token:
            return "manual"
        if token.startswith("remote-select1") or token.startswith("autodb-lookup"):
            return "lookup"
        if token.startswith("batch") or token.startswith("tecdoc"):
            return "celery_batch"
        if "backoffice" in token:
            return "backoffice"
        if token and token not in {"known", "remaining"}:
            if self._looks_like_uuid(token):
                return self._runtime_consumer()
            return "service"
        return self._runtime_consumer()

    def _runtime_consumer(self) -> str:
        argv = " ".join(str(item) for item in sys.argv).lower()
        if "celery" in argv:
            return "celery_batch"
        if "manage.py" in argv:
            return "management"
        cmd = str(os.getenv("SERVER_SOFTWARE") or "").lower()
        if "gunicorn" in cmd or "uvicorn" in cmd:
            return "api"
        return "unknown"

    def _looks_like_uuid(self, value: str) -> bool:
        cleaned = value.replace("-", "")
        return len(cleaned) == 32 and all(char in "0123456789abcdef" for char in cleaned)

    def _consumers_breakdown(self, points: list[dict]) -> list[dict[str, Any]]:
        totals: dict[str, int] = {}
        overall = 0
        for item in points:
            count = max(int(item.get("query_count") or 0), 0)
            consumer = str(item.get("consumer") or "").strip() or self._consumer_name(run_id=str(item.get("run_id") or ""))
            totals[consumer] = totals.get(consumer, 0) + count
            overall += count
        if overall <= 0:
            return []
        rows = sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))
        return [
            {
                "consumer": name,
                "query_count": value,
                "percent": round((value / overall) * 100, 2),
            }
            for name, value in rows
        ]
