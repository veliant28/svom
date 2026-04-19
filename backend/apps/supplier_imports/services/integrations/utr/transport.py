from __future__ import annotations

import logging
import time

from apps.supplier_imports.services.integrations.client_utils import (
    HttpBytesResponse,
    HttpJsonResponse,
    http_bytes_request,
    http_json_request,
)
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

logger = logging.getLogger(__name__)


def safe_json_request(
    client,
    *,
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    cache_key: str | None = None,
    force_refresh: bool | None = None,
    request_reason: str = "",
) -> HttpJsonResponse:
    client._ensure_enabled()
    should_force_refresh = client._resolve_force_refresh(force_refresh)
    reason = request_reason or f"{method.upper()} {url}"

    if cache_key and not should_force_refresh:
        cached_payload = client._cache_get(cache_key)
        if cached_payload is not None:
            client._increment_metric("requests_skipped_cache")
            logger.info("[UTR] cache-hit reason=%s key=%s", reason, cache_key)
            return HttpJsonResponse(status=200, payload=cached_payload)

    client._ensure_circuit_is_closed()
    with client.__class__._semaphore:
        for attempt in range(1, client.max_retries + 1):
            client._wait_global_rate_limit_slot(reason=reason)
            try:
                client._increment_metric("requests_sent_total")
                response = http_json_request(
                    method=method,
                    url=url,
                    payload=payload,
                    headers=headers,
                    timeout=timeout,
                )
                client._mark_request_success()
                if cache_key:
                    client._cache_set(cache_key, response.payload, timeout=client.cache_ttl_seconds)
                return response
            except SupplierClientError as exc:
                client._mark_request_failure(exc=exc)
                if attempt >= client.max_retries or not client._is_retryable_error(exc=exc):
                    raise
                client._increment_metric("retries_total")
                delay_seconds = client._compute_backoff_seconds(attempt=attempt, status_code=exc.status_code)
                logger.warning(
                    "[UTR] retry reason=%s attempt=%s/%s status=%s delay=%.2fs",
                    reason,
                    attempt,
                    client.max_retries,
                    exc.status_code,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
    raise SupplierClientError("UTR request failed unexpectedly.")


def safe_bytes_request(
    client,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    request_reason: str = "",
) -> HttpBytesResponse:
    client._ensure_enabled()
    reason = request_reason or f"{method.upper()} {url}"

    client._ensure_circuit_is_closed()
    with client.__class__._semaphore:
        for attempt in range(1, client.max_retries + 1):
            client._wait_global_rate_limit_slot(reason=reason)
            try:
                client._increment_metric("requests_sent_total")
                response = http_bytes_request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                )
                client._mark_request_success()
                return response
            except SupplierClientError as exc:
                client._mark_request_failure(exc=exc)
                if attempt >= client.max_retries or not client._is_retryable_error(exc=exc):
                    raise
                client._increment_metric("retries_total")
                delay_seconds = client._compute_backoff_seconds(attempt=attempt, status_code=exc.status_code)
                logger.warning(
                    "[UTR] retry-bytes reason=%s attempt=%s/%s status=%s delay=%.2fs",
                    reason,
                    attempt,
                    client.max_retries,
                    exc.status_code,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
    raise SupplierClientError("UTR bytes request failed unexpectedly.")
