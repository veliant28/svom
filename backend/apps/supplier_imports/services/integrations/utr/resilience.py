from __future__ import annotations

import logging
import random
import time

from django.core.cache import cache

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

logger = logging.getLogger(__name__)


def wait_global_rate_limit_slot(*, rate_limit_per_minute: int, reason: str) -> None:
    del reason
    interval_seconds = 60.0 / float(rate_limit_per_minute)
    next_allowed_key = "utr:rate_limit:next_allowed_at"
    lock_key = "utr:rate_limit:lock"

    while True:
        try:
            if not cache.add(lock_key, "1", timeout=5):
                time.sleep(0.05 + random.uniform(0.0, 0.15))
                continue
            try:
                now = time.time()
                raw_next_allowed = cache.get(next_allowed_key)
                try:
                    next_allowed = float(raw_next_allowed or 0.0)
                except (TypeError, ValueError):
                    next_allowed = 0.0

                if next_allowed <= now:
                    cache.set(next_allowed_key, now + interval_seconds, timeout=60 * 60)
                    return
                wait_seconds = min(max(next_allowed - now, 0.0), 120.0)
            finally:
                cache.delete(lock_key)
            time.sleep(wait_seconds + random.uniform(0.0, 0.2))
        except Exception:
            # If shared cache is unavailable, keep conservative local delay fallback.
            time.sleep(interval_seconds)
            return


def ensure_circuit_is_closed(*, cache_get) -> None:
    raw_open_until = cache_get("utr:circuit_breaker:open_until")
    try:
        open_until = float(raw_open_until or 0.0)
    except (TypeError, ValueError):
        open_until = 0.0

    now = time.time()
    if open_until > now:
        retry_after = max(int(open_until - now), 1)
        raise SupplierClientError(
            f"UTR circuit breaker active. Retry after {retry_after} sec.",
            status_code=503,
        )


def mark_request_success(*, cache_delete) -> None:
    cache_delete("utr:circuit_breaker:failures")
    cache_delete("utr:circuit_breaker:open_until")


def mark_request_failure(
    instance,
    *,
    exc: SupplierClientError,
    circuit_breaker_threshold: int,
    circuit_breaker_cooldown_seconds: int,
    cache_set,
    increment_metric,
    record_error_metrics,
) -> None:
    record_error_metrics(instance, exc=exc)
    failures_key = "utr:circuit_breaker:failures"
    failures = 1
    try:
        if not cache.add(failures_key, 1, timeout=60 * 60):
            try:
                failures = int(cache.incr(failures_key))
            except ValueError:
                cache.set(failures_key, 1, timeout=60 * 60)
                failures = 1
    except Exception:
        return

    if failures < circuit_breaker_threshold:
        return

    open_until = time.time() + circuit_breaker_cooldown_seconds
    cache_set("utr:circuit_breaker:open_until", open_until, timeout=circuit_breaker_cooldown_seconds + 60)
    increment_metric(instance, "circuit_breaker_open_total")
    logger.warning(
        "[UTR] circuit-open failures=%s status=%s cooldown=%ss",
        failures,
        exc.status_code,
        circuit_breaker_cooldown_seconds,
    )


def compute_backoff_seconds(*, backoff_base_seconds: float, attempt: int, status_code: int | None) -> float:
    delay = backoff_base_seconds * (2 ** max(attempt - 1, 0))
    if status_code == 429:
        delay = max(delay, backoff_base_seconds * 4)
    jitter = random.uniform(0.0, backoff_base_seconds)
    return min(delay + jitter, 120.0)
