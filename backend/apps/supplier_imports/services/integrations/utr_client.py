from __future__ import annotations

import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from django.conf import settings
from django.core.cache import cache

from apps.supplier_imports.services.integrations.client_utils import (
    HttpBytesResponse,
    HttpJsonResponse,
    http_bytes_request,
    http_json_request,
    parse_datetime_maybe,
)
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.services.integrations.token_storage_service import SupplierTokenStorageService
from apps.supplier_imports.selectors import get_supplier_integration_by_code

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupplierTokenResult:
    access_token: str
    refresh_token: str
    access_expires_at: object | None
    refresh_expires_at: object | None = None


@dataclass(frozen=True)
class UtrBatchSearchResult:
    rows: list[dict]
    access_token: str
    auth_retry_performed: bool = False
    auth_retry_method: str = ""


class UtrClient:
    _semaphore_lock = threading.Lock()
    _semaphore_size = 1
    _semaphore = threading.BoundedSemaphore(1)
    _metrics_lock = threading.Lock()
    _metrics_names = (
        "requests_sent_total",
        "requests_skipped_cache",
        "retries_total",
        "timeouts_total",
        "http_429_total",
        "http_5xx_total",
        "circuit_breaker_open_total",
        "auth_refresh_total",
        "auth_relogin_total",
        "auth_retry_batch_total",
    )
    _process_metrics = {name: 0 for name in _metrics_names}

    def __init__(self, *, base_url: str | None = None):
        raw = base_url or os.getenv("UTR_API_BASE_URL", "https://order24-api.utr.ua")
        self.base_url = raw.rstrip("/")

        self.enabled = bool(getattr(settings, "UTR_ENABLED", True))
        self.rate_limit_per_minute = max(int(getattr(settings, "UTR_RATE_LIMIT_PER_MINUTE", 6)), 1)
        self.concurrency = max(1, min(int(getattr(settings, "UTR_CONCURRENCY", 1)), 2))
        self.max_retries = max(int(getattr(settings, "UTR_MAX_RETRIES", 3)), 1)
        self.backoff_base_seconds = max(float(getattr(settings, "UTR_BACKOFF_BASE_SECONDS", 2.0)), 0.5)
        self.circuit_breaker_threshold = max(int(getattr(settings, "UTR_CIRCUIT_BREAKER_THRESHOLD", 5)), 1)
        self.circuit_breaker_cooldown_seconds = max(
            int(getattr(settings, "UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS", 300)),
            30,
        )
        self.force_refresh_by_default = bool(getattr(settings, "UTR_FORCE_REFRESH", False))
        self.cache_ttl_seconds = max(int(getattr(settings, "UTR_CACHE_TTL_SECONDS", 60 * 60 * 24 * 30)), 60)
        self.token_storage = SupplierTokenStorageService()

        self._ensure_shared_semaphore_capacity()

    @classmethod
    def reset_process_metrics(cls) -> None:
        with cls._metrics_lock:
            cls._process_metrics = {name: 0 for name in cls._metrics_names}

    @classmethod
    def get_process_metrics(cls) -> dict[str, int]:
        with cls._metrics_lock:
            return {name: int(cls._process_metrics.get(name, 0)) for name in cls._metrics_names}

    @staticmethod
    def is_circuit_open_error(exc: SupplierClientError) -> bool:
        message = str(exc).strip().lower()
        return exc.status_code == 503 and "circuit breaker active" in message

    @staticmethod
    def is_auth_error(exc: SupplierClientError) -> bool:
        if exc.status_code in {401, 403}:
            return True
        message = str(exc).strip().lower()
        markers = (
            "expired jwt token",
            "invalid jwt token",
            "jwt token",
            "unauthorized",
            "authentication",
            "auth",
            "forbidden",
        )
        return any(marker in message for marker in markers)

    @staticmethod
    def is_expired_token_error(exc: SupplierClientError) -> bool:
        message = str(exc).strip().lower()
        return "expired jwt token" in message

    @staticmethod
    def is_transport_error(exc: SupplierClientError) -> bool:
        if exc.status_code is None:
            return True
        message = str(exc).strip().lower()
        markers = (
            "не удалось выполнить запрос",
            "failed to establish",
            "temporary failure",
            "connection",
            "network",
            "dns",
            "name resolution",
        )
        return any(marker in message for marker in markers)

    def obtain_token(self, *, login: str, password: str, browser_fingerprint: str) -> SupplierTokenResult:
        response = self._safe_json_request(
            method="POST",
            url=f"{self.base_url}/api/login_check",
            payload={
                "email": login,
                "password": password,
                "browser_fingerprint": browser_fingerprint,
            },
            force_refresh=True,
            request_reason="auth_obtain_token",
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        token = str(payload.get("token", "")).strip()
        refresh_token = str(payload.get("refresh_token", "")).strip()
        if not token:
            raise SupplierClientError("UTR не вернул access token.")
        if not refresh_token:
            raise SupplierClientError("UTR не вернул refresh token.")
        return SupplierTokenResult(
            access_token=token,
            refresh_token=refresh_token,
            access_expires_at=parse_datetime_maybe(str(payload.get("expires_at", ""))),
            refresh_expires_at=None,
        )

    def refresh_token(self, *, refresh_token: str, browser_fingerprint: str) -> SupplierTokenResult:
        response = self._safe_json_request(
            method="POST",
            url=f"{self.base_url}/api/token/refresh",
            payload={
                "refresh_token": refresh_token,
                "browser_fingerprint": browser_fingerprint,
            },
            force_refresh=True,
            request_reason="auth_refresh_token",
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        token = str(payload.get("token", "")).strip()
        next_refresh_token = str(payload.get("refresh_token", "")).strip()
        if not token:
            raise SupplierClientError("UTR не вернул access token при обновлении.")
        if not next_refresh_token:
            raise SupplierClientError("UTR не вернул refresh token при обновлении.")
        return SupplierTokenResult(
            access_token=token,
            refresh_token=next_refresh_token,
            access_expires_at=parse_datetime_maybe(str(payload.get("expires_at", ""))),
            refresh_expires_at=None,
        )

    def check_connection(self, *, access_token: str) -> dict:
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/api/brands",
            headers={"Authorization": f"Bearer {access_token}"},
            request_reason="connection_check",
        )
        payload = response.payload
        if isinstance(payload, list):
            return {
                "ok": True,
                "brands_count": len(payload),
            }
        if isinstance(payload, dict):
            return {"ok": True, "payload": payload}
        return {"ok": True}

    def fetch_brands(self, *, access_token: str) -> list[dict]:
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/api/brands",
            headers={"Authorization": f"Bearer {access_token}"},
            request_reason="brands_fetch",
        )
        payload = response.payload
        if not isinstance(payload, list):
            raise SupplierClientError("UTR вернул неожиданный формат списка брендов.")
        rows: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            external_code = str(item.get("externalCode", "")).strip()
            rows.append(
                {
                    "name": name,
                    "external_code": external_code,
                }
            )
        return rows

    def get_pricelist_export_params(self, *, access_token: str) -> dict:
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/pricelists/export-params",
            headers={"Authorization": f"Bearer {access_token}"},
            request_reason="pricelist_export_params",
        )
        payload = response.payload
        if not isinstance(payload, dict):
            raise SupplierClientError("UTR вернул неожиданный формат параметров прайса.")
        return payload

    def request_pricelist_export(self, *, access_token: str, payload: dict) -> dict:
        response = self._safe_json_request(
            method="POST",
            url=f"{self.base_url}/pricelists/export-request",
            headers={"Authorization": f"Bearer {access_token}"},
            payload=payload,
            force_refresh=True,
            request_reason="pricelist_export_request",
        )
        body = response.payload
        if not isinstance(body, dict):
            raise SupplierClientError("UTR вернул неожиданный формат ответа на запрос прайса.")
        return body

    def get_pricelist_status(self, *, access_token: str, pricelist_id: str) -> dict | str:
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/pricelists/{pricelist_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            request_reason="pricelist_status",
        )
        payload = response.payload
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            return payload
        raise SupplierClientError("UTR вернул неожиданный формат статуса прайса.")

    def list_pricelists(self, *, access_token: str) -> list[dict]:
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/pricelists",
            headers={"Authorization": f"Bearer {access_token}"},
            request_reason="pricelists_list",
        )
        payload = response.payload
        if not isinstance(payload, list):
            raise SupplierClientError("UTR вернул неожиданный формат списка прайсов.")
        rows: list[dict] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def fetch_applicability(
        self,
        *,
        access_token: str,
        detail_id: str,
        force_refresh: bool | None = None,
        request_reason: str = "detail_applicability",
    ) -> list[dict]:
        normalized_detail_id = str(detail_id or "").strip()
        cache_key = self._cache_key("applicability", normalized_detail_id)
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/api/applicability/{normalized_detail_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            cache_key=cache_key,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )
        payload = response.payload
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise SupplierClientError("UTR вернул неожиданный формат применяемости.")
        rows: list[dict] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def search_details(
        self,
        *,
        access_token: str,
        oem: str,
        brand: str = "",
        force_refresh: bool | None = None,
        request_reason: str = "detail_search",
    ) -> list[dict]:
        normalized_oem = str(oem or "").strip()
        if not normalized_oem:
            return []

        query_params = {}
        normalized_brand = str(brand or "").strip()
        if normalized_brand:
            query_params["brand"] = normalized_brand

        query_string = f"?{urlencode(query_params)}" if query_params else ""
        url = f"{self.base_url}/api/search/{quote(normalized_oem, safe='')}{query_string}"
        cache_key = self._cache_key("search", normalized_oem, normalized_brand)
        response = self._safe_json_request(
            method="GET",
            url=url,
            headers={"Authorization": f"Bearer {access_token}"},
            cache_key=cache_key,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        details = payload.get("details")
        if details is None:
            return []
        if not isinstance(details, list):
            raise SupplierClientError("UTR вернул неожиданный формат поиска деталей.")

        rows: list[dict] = []
        for item in details:
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def search_details_batch(
        self,
        *,
        access_token: str,
        details: list[dict],
        force_refresh: bool | None = None,
        request_reason: str = "detail_search_batch",
    ) -> UtrBatchSearchResult:
        normalized_queries: list[dict[str, str]] = []
        for item in details:
            if not isinstance(item, dict):
                continue
            oem = str(item.get("oem") or item.get("article") or "").strip()
            if not oem:
                continue
            brand = str(item.get("brand") or "").strip()
            normalized_queries.append(
                {
                    "oem": oem,
                    "brand": brand,
                }
            )
        if not normalized_queries:
            return UtrBatchSearchResult(rows=[], access_token=access_token)

        should_force_refresh = self._resolve_force_refresh(force_refresh)
        rows: list[dict] = [{"details": []} for _ in normalized_queries]
        current_access_token = str(access_token or "").strip()
        auth_retry_performed = False
        auth_retry_method = ""
        pending_payload: list[dict] = []
        pending_indexes: list[int] = []

        if not should_force_refresh:
            for index, query in enumerate(normalized_queries):
                cache_key = self._cache_key("search", query["oem"], query["brand"])
                cached_payload = self._cache_get(cache_key)
                if isinstance(cached_payload, dict) and isinstance(cached_payload.get("details"), list):
                    cached_details = [item for item in cached_payload.get("details") or [] if isinstance(item, dict)]
                    rows[index] = {"details": cached_details}
                    self._increment_metric("requests_skipped_cache")
                    continue
                payload_item = {"oem": query["oem"]}
                if query["brand"]:
                    payload_item["brand"] = query["brand"]
                pending_payload.append(payload_item)
                pending_indexes.append(index)
        else:
            for index, query in enumerate(normalized_queries):
                payload_item = {"oem": query["oem"]}
                if query["brand"]:
                    payload_item["brand"] = query["brand"]
                pending_payload.append(payload_item)
                pending_indexes.append(index)

        if pending_payload:
            try:
                response = self._safe_json_request(
                    method="POST",
                    url=f"{self.base_url}/api/search",
                    headers={"Authorization": f"Bearer {current_access_token}"},
                    payload={"details": pending_payload},
                    force_refresh=True,
                    request_reason=request_reason,
                )
            except SupplierClientError as exc:
                if self.is_expired_token_error(exc):
                    logger.warning("[UTR] expired-access-token detected during batch search, trying auth recovery.")
                    recovered_token, auth_method = self._recover_access_token_for_utr()
                    if recovered_token:
                        auth_retry_performed = True
                        auth_retry_method = auth_method
                        current_access_token = recovered_token
                        self._increment_metric("auth_retry_batch_total")
                        logger.info(
                            "[UTR] batch-auth-retry method=%s batch_size=%s reason=%s",
                            auth_method,
                            len(pending_payload),
                            request_reason,
                        )
                        response = self._safe_json_request(
                            method="POST",
                            url=f"{self.base_url}/api/search",
                            headers={"Authorization": f"Bearer {current_access_token}"},
                            payload={"details": pending_payload},
                            force_refresh=True,
                            request_reason=request_reason,
                        )
                    else:
                        raise
                else:
                    raise
            payload = response.payload
            if not isinstance(payload, list):
                raise SupplierClientError("UTR вернул неожиданный формат пакетного поиска деталей.")

            for result_index, original_index in enumerate(pending_indexes):
                response_item: dict = {}
                if result_index < len(payload) and isinstance(payload[result_index], dict):
                    response_item = payload[result_index]
                query = normalized_queries[original_index]
                details_payload = response_item.get("details")
                if isinstance(details_payload, list):
                    normalized_details = [item for item in details_payload if isinstance(item, dict)]
                    rows[original_index] = {"details": normalized_details}
                    cache_key = self._cache_key("search", query["oem"], query["brand"])
                    self._cache_set(cache_key, {"details": normalized_details}, timeout=self.cache_ttl_seconds)
                elif isinstance(response_item.get("error"), str):
                    rows[original_index] = {"error": response_item["error"]}
                else:
                    rows[original_index] = {"details": []}

        return UtrBatchSearchResult(
            rows=rows,
            access_token=current_access_token,
            auth_retry_performed=auth_retry_performed,
            auth_retry_method=auth_retry_method,
        )

    def fetch_detail(
        self,
        *,
        access_token: str,
        detail_id: str,
        force_refresh: bool | None = None,
        request_reason: str = "detail_info",
    ) -> dict:
        normalized_detail_id = str(detail_id or "").strip()
        cache_key = self._cache_key("detail", normalized_detail_id)
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/api/detail/{normalized_detail_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            cache_key=cache_key,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )
        payload = response.payload
        if not isinstance(payload, dict):
            raise SupplierClientError("UTR вернул неожиданный формат информации о детали.")
        return payload

    def fetch_characteristics(
        self,
        *,
        access_token: str,
        detail_id: str,
        force_refresh: bool | None = None,
        request_reason: str = "detail_characteristics",
    ) -> list[dict]:
        normalized_detail_id = str(detail_id or "").strip()
        cache_key = self._cache_key("characteristics", normalized_detail_id)
        response = self._safe_json_request(
            method="GET",
            url=f"{self.base_url}/api/characteristics/{normalized_detail_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            cache_key=cache_key,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )
        payload = response.payload
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise SupplierClientError("UTR вернул неожиданный формат характеристик.")
        rows: list[dict] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def download_pricelist(self, *, access_token: str, export_token: str) -> tuple[bytes, str]:
        response = self._safe_bytes_request(
            method="GET",
            url=f"{self.base_url}/pricelists/export/{export_token}",
            headers={"Authorization": f"Bearer {access_token}"},
            request_reason="pricelist_download",
        )
        content_type = response.headers.get("content-type", "")
        return response.body, content_type

    def delete_pricelist(self, *, access_token: str, pricelist_id: str) -> dict:
        response = self._safe_json_request(
            method="DELETE",
            url=f"{self.base_url}/pricelists/delete/{pricelist_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            force_refresh=True,
            request_reason="pricelist_delete",
        )
        payload = response.payload
        if isinstance(payload, dict):
            return payload
        return {}

    def _safe_json_request(
        self,
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
        self._ensure_enabled()
        should_force_refresh = self._resolve_force_refresh(force_refresh)
        reason = request_reason or f"{method.upper()} {url}"

        if cache_key and not should_force_refresh:
            cached_payload = self._cache_get(cache_key)
            if cached_payload is not None:
                self._increment_metric("requests_skipped_cache")
                logger.info("[UTR] cache-hit reason=%s key=%s", reason, cache_key)
                return HttpJsonResponse(status=200, payload=cached_payload)

        self._ensure_circuit_is_closed()
        with self.__class__._semaphore:
            for attempt in range(1, self.max_retries + 1):
                self._wait_global_rate_limit_slot(reason=reason)
                try:
                    self._increment_metric("requests_sent_total")
                    response = http_json_request(
                        method=method,
                        url=url,
                        payload=payload,
                        headers=headers,
                        timeout=timeout,
                    )
                    self._mark_request_success()
                    if cache_key:
                        self._cache_set(cache_key, response.payload, timeout=self.cache_ttl_seconds)
                    return response
                except SupplierClientError as exc:
                    self._mark_request_failure(exc=exc)
                    if attempt >= self.max_retries or not self._is_retryable_error(exc=exc):
                        raise
                    self._increment_metric("retries_total")
                    delay_seconds = self._compute_backoff_seconds(attempt=attempt, status_code=exc.status_code)
                    logger.warning(
                        "[UTR] retry reason=%s attempt=%s/%s status=%s delay=%.2fs",
                        reason,
                        attempt,
                        self.max_retries,
                        exc.status_code,
                        delay_seconds,
                    )
                    time.sleep(delay_seconds)
        raise SupplierClientError("UTR request failed unexpectedly.")

    def _safe_bytes_request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
        request_reason: str = "",
    ) -> HttpBytesResponse:
        self._ensure_enabled()
        reason = request_reason or f"{method.upper()} {url}"

        self._ensure_circuit_is_closed()
        with self.__class__._semaphore:
            for attempt in range(1, self.max_retries + 1):
                self._wait_global_rate_limit_slot(reason=reason)
                try:
                    self._increment_metric("requests_sent_total")
                    response = http_bytes_request(
                        method=method,
                        url=url,
                        headers=headers,
                        timeout=timeout,
                    )
                    self._mark_request_success()
                    return response
                except SupplierClientError as exc:
                    self._mark_request_failure(exc=exc)
                    if attempt >= self.max_retries or not self._is_retryable_error(exc=exc):
                        raise
                    self._increment_metric("retries_total")
                    delay_seconds = self._compute_backoff_seconds(attempt=attempt, status_code=exc.status_code)
                    logger.warning(
                        "[UTR] retry-bytes reason=%s attempt=%s/%s status=%s delay=%.2fs",
                        reason,
                        attempt,
                        self.max_retries,
                        exc.status_code,
                        delay_seconds,
                    )
                    time.sleep(delay_seconds)
        raise SupplierClientError("UTR bytes request failed unexpectedly.")

    def _resolve_force_refresh(self, force_refresh: bool | None) -> bool:
        if force_refresh is None:
            return bool(self.force_refresh_by_default)
        return bool(force_refresh)

    def _ensure_enabled(self) -> None:
        if self.enabled:
            return
        raise SupplierClientError("UTR integration disabled by UTR_ENABLED=0.")

    def _ensure_shared_semaphore_capacity(self) -> None:
        with self.__class__._semaphore_lock:
            if self.__class__._semaphore_size == self.concurrency:
                return
            self.__class__._semaphore_size = self.concurrency
            self.__class__._semaphore = threading.BoundedSemaphore(self.concurrency)

    def _wait_global_rate_limit_slot(self, *, reason: str) -> None:
        del reason
        interval_seconds = 60.0 / float(self.rate_limit_per_minute)
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

    def _ensure_circuit_is_closed(self) -> None:
        raw_open_until = self._cache_get("utr:circuit_breaker:open_until")
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

    def _mark_request_success(self) -> None:
        self._cache_delete("utr:circuit_breaker:failures")
        self._cache_delete("utr:circuit_breaker:open_until")

    def _mark_request_failure(self, *, exc: SupplierClientError) -> None:
        self._record_error_metrics(exc=exc)
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

        if failures < self.circuit_breaker_threshold:
            return

        open_until = time.time() + self.circuit_breaker_cooldown_seconds
        self._cache_set("utr:circuit_breaker:open_until", open_until, timeout=self.circuit_breaker_cooldown_seconds + 60)
        self._increment_metric("circuit_breaker_open_total")
        logger.warning(
            "[UTR] circuit-open failures=%s status=%s cooldown=%ss",
            failures,
            exc.status_code,
            self.circuit_breaker_cooldown_seconds,
        )

    def _is_retryable_error(self, *, exc: SupplierClientError) -> bool:
        if exc.status_code in {408, 429, 500, 502, 503, 504}:
            return True
        message = str(exc).strip().lower()
        markers = (
            "timeout",
            "timed out",
            "temporarily unavailable",
            "temporary failure",
            "connection reset",
            "too many requests",
        )
        return any(marker in message for marker in markers)

    def _compute_backoff_seconds(self, *, attempt: int, status_code: int | None) -> float:
        delay = self.backoff_base_seconds * (2 ** max(attempt - 1, 0))
        if status_code == 429:
            delay = max(delay, self.backoff_base_seconds * 4)
        jitter = random.uniform(0.0, self.backoff_base_seconds)
        return min(delay + jitter, 120.0)

    def _record_error_metrics(self, *, exc: SupplierClientError) -> None:
        if exc.status_code == 429:
            self._increment_metric("http_429_total")
        if isinstance(exc.status_code, int) and 500 <= exc.status_code <= 599:
            self._increment_metric("http_5xx_total")
        if self._is_timeout_error(exc=exc):
            self._increment_metric("timeouts_total")

    def _is_timeout_error(self, *, exc: SupplierClientError) -> bool:
        if exc.status_code in {408, 504}:
            return True
        message = str(exc).strip().lower()
        markers = (
            "timeout",
            "timed out",
            "read timed out",
            "connection timed out",
        )
        return any(marker in message for marker in markers)

    def _increment_metric(self, name: str, amount: int = 1) -> None:
        if name not in self._metrics_names:
            return
        increment = max(int(amount), 1)
        with self.__class__._metrics_lock:
            current = int(self.__class__._process_metrics.get(name, 0))
            self.__class__._process_metrics[name] = current + increment

    def _recover_access_token_for_utr(self) -> tuple[str, str]:
        integration = get_supplier_integration_by_code(source_code="utr")
        browser_fingerprint = integration.browser_fingerprint or "svom-backoffice"

        if integration.refresh_token:
            try:
                result = self.refresh_token(
                    refresh_token=integration.refresh_token,
                    browser_fingerprint=browser_fingerprint,
                )
                self.token_storage.store_tokens(
                    integration=integration,
                    access_token=result.access_token,
                    refresh_token=result.refresh_token,
                    access_expires_at=result.access_expires_at,
                    refresh_expires_at=result.refresh_expires_at,
                    refreshed=True,
                )
                self._increment_metric("auth_refresh_total")
                logger.info("[UTR] token refresh succeeded for batch-retry.")
                return result.access_token, "refresh"
            except SupplierClientError as exc:
                logger.warning("[UTR] token refresh failed during batch-retry: %s", exc)

        login = str(integration.login or "").strip()
        password = str(integration.password or "").strip()
        if login and password:
            try:
                result = self.obtain_token(
                    login=login,
                    password=password,
                    browser_fingerprint=browser_fingerprint,
                )
                self.token_storage.store_tokens(
                    integration=integration,
                    access_token=result.access_token,
                    refresh_token=result.refresh_token,
                    access_expires_at=result.access_expires_at,
                    refresh_expires_at=result.refresh_expires_at,
                    refreshed=False,
                )
                self._increment_metric("auth_relogin_total")
                logger.info("[UTR] re-login succeeded for batch-retry.")
                return result.access_token, "relogin"
            except SupplierClientError as exc:
                logger.warning("[UTR] re-login failed during batch-retry: %s", exc)

        return "", ""

    def _cache_key(self, *parts: str) -> str:
        normalized_parts: list[str] = []
        for part in parts:
            text = str(part or "").strip().lower()
            if not text:
                text = "_"
            normalized_parts.append(quote(text, safe=""))
        return "utr:api:" + ":".join(normalized_parts)

    def _cache_get(self, key: str):
        try:
            return cache.get(key)
        except Exception:
            return None

    def _cache_set(self, key: str, value, *, timeout: int) -> None:
        try:
            cache.set(key, value, timeout=timeout)
        except Exception:
            return

    def _cache_delete(self, key: str) -> None:
        try:
            cache.delete(key)
        except Exception:
            return
