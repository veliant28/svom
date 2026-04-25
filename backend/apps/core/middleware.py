from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("apps.core.request_timing")


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._is_enabled_for_path(request.path):
            return self.get_response(request)

        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        started_at = time.perf_counter()
        query_stats: dict[str, Any] = {
            "count": 0,
            "total_ms": 0.0,
            "slow": [],
        }

        def sql_timing_wrapper(execute, sql, params, many, context):
            sql_started_at = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                elapsed_ms = (time.perf_counter() - sql_started_at) * 1000
                query_stats["count"] += 1
                query_stats["total_ms"] += elapsed_ms
                slow_sql_ms = float(getattr(settings, "REQUEST_TIMING_SLOW_SQL_MS", 100.0))
                if elapsed_ms >= slow_sql_ms:
                    query_stats["slow"].append(
                        {
                            "ms": round(elapsed_ms, 2),
                            "sql": self._compact_sql(sql),
                        }
                    )

        response: HttpResponse | None = None
        error: BaseException | None = None
        try:
            with connection.execute_wrapper(sql_timing_wrapper):
                response = self.get_response(request)
            return response
        except BaseException as exc:
            error = exc
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self._log_request_timing(
                request=request,
                response=response,
                request_id=request_id,
                elapsed_ms=elapsed_ms,
                query_stats=query_stats,
                error=error,
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id
                response.headers["Server-Timing"] = (
                    f"app;dur={elapsed_ms:.1f}, db;dur={query_stats['total_ms']:.1f};desc=\"SQL\""
                )

    @staticmethod
    def _is_enabled_for_path(path: str) -> bool:
        if not bool(getattr(settings, "REQUEST_TIMING_LOG_ENABLED", False)):
            return False
        prefixes = tuple(getattr(settings, "REQUEST_TIMING_LOG_PATH_PREFIXES", ("/api/",)))
        return any(path.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def _compact_sql(sql: str) -> str:
        max_length = int(getattr(settings, "REQUEST_TIMING_SQL_SNIPPET_LENGTH", 240))
        compact = " ".join(str(sql).split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[:max_length]}..."

    @staticmethod
    def _log_request_timing(
        *,
        request: HttpRequest,
        response: HttpResponse | None,
        request_id: str,
        elapsed_ms: float,
        query_stats: dict[str, Any],
        error: BaseException | None,
    ) -> None:
        min_ms = float(getattr(settings, "REQUEST_TIMING_LOG_MIN_MS", 0.0))
        should_log = (
            elapsed_ms >= min_ms
            or bool(query_stats["slow"])
            or error is not None
        )
        if not should_log:
            return

        payload = {
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "status": getattr(response, "status_code", 500),
            "total_ms": round(elapsed_ms, 2),
            "sql_count": query_stats["count"],
            "sql_ms": round(query_stats["total_ms"], 2),
            "slow_sql": query_stats["slow"][:5],
        }
        if error is not None:
            payload["error"] = error.__class__.__name__

        logger.warning("backend_request_timing %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))
