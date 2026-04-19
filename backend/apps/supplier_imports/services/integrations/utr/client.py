from __future__ import annotations

import os
import threading

from django.conf import settings

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.services.integrations.token_storage_service import SupplierTokenStorageService

from . import auth, diagnostics, errors, metrics, resilience, transport
from . import cache as cache_helpers
from .endpoints import brands, catalog, pricelists, search
from .auth import SupplierTokenResult
from .endpoints.search import UtrBatchSearchResult


class UtrClient:
    _semaphore_lock = threading.Lock()
    _semaphore_size = 1
    _semaphore = threading.BoundedSemaphore(1)
    _metrics_lock = threading.Lock()
    _metrics_names = metrics.METRIC_NAMES
    _process_metrics = metrics.build_process_metrics(_metrics_names)

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
        metrics.reset_process_metrics(cls)

    @classmethod
    def get_process_metrics(cls) -> dict[str, int]:
        return metrics.get_process_metrics(cls)

    @staticmethod
    def is_circuit_open_error(exc: SupplierClientError) -> bool:
        return errors.is_circuit_open_error(exc)

    @staticmethod
    def is_auth_error(exc: SupplierClientError) -> bool:
        return errors.is_auth_error(exc)

    @staticmethod
    def is_expired_token_error(exc: SupplierClientError) -> bool:
        return errors.is_expired_token_error(exc)

    @staticmethod
    def is_transport_error(exc: SupplierClientError) -> bool:
        return errors.is_transport_error(exc)

    def obtain_token(self, *, login: str, password: str, browser_fingerprint: str) -> SupplierTokenResult:
        return auth.obtain_token(self, login=login, password=password, browser_fingerprint=browser_fingerprint)

    def refresh_token(self, *, refresh_token: str, browser_fingerprint: str) -> SupplierTokenResult:
        return auth.refresh_token(self, refresh_token=refresh_token, browser_fingerprint=browser_fingerprint)

    def check_connection(self, *, access_token: str) -> dict:
        return brands.check_connection(self, access_token=access_token)

    def fetch_brands(self, *, access_token: str) -> list[dict]:
        return brands.fetch_brands(self, access_token=access_token)

    def get_pricelist_export_params(self, *, access_token: str) -> dict:
        return pricelists.get_pricelist_export_params(self, access_token=access_token)

    def request_pricelist_export(self, *, access_token: str, payload: dict) -> dict:
        return pricelists.request_pricelist_export(self, access_token=access_token, payload=payload)

    def get_pricelist_status(self, *, access_token: str, pricelist_id: str) -> dict | str:
        return pricelists.get_pricelist_status(self, access_token=access_token, pricelist_id=pricelist_id)

    def list_pricelists(self, *, access_token: str) -> list[dict]:
        return pricelists.list_pricelists(self, access_token=access_token)

    def fetch_applicability(
        self,
        *,
        access_token: str,
        detail_id: str,
        force_refresh: bool | None = None,
        request_reason: str = "detail_applicability",
    ) -> list[dict]:
        return catalog.fetch_applicability(
            self,
            access_token=access_token,
            detail_id=detail_id,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )

    def search_details(
        self,
        *,
        access_token: str,
        oem: str,
        brand: str = "",
        force_refresh: bool | None = None,
        request_reason: str = "detail_search",
    ) -> list[dict]:
        return search.search_details(
            self,
            access_token=access_token,
            oem=oem,
            brand=brand,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )

    def search_details_batch(
        self,
        *,
        access_token: str,
        details: list[dict],
        force_refresh: bool | None = None,
        request_reason: str = "detail_search_batch",
    ) -> UtrBatchSearchResult:
        return search.search_details_batch(
            self,
            access_token=access_token,
            details=details,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )

    def fetch_detail(
        self,
        *,
        access_token: str,
        detail_id: str,
        force_refresh: bool | None = None,
        request_reason: str = "detail_info",
    ) -> dict:
        return catalog.fetch_detail(
            self,
            access_token=access_token,
            detail_id=detail_id,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )

    def fetch_characteristics(
        self,
        *,
        access_token: str,
        detail_id: str,
        force_refresh: bool | None = None,
        request_reason: str = "detail_characteristics",
    ) -> list[dict]:
        return catalog.fetch_characteristics(
            self,
            access_token=access_token,
            detail_id=detail_id,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )

    def download_pricelist(self, *, access_token: str, export_token: str) -> tuple[bytes, str]:
        return pricelists.download_pricelist(self, access_token=access_token, export_token=export_token)

    def delete_pricelist(self, *, access_token: str, pricelist_id: str) -> dict:
        return pricelists.delete_pricelist(self, access_token=access_token, pricelist_id=pricelist_id)

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
    ):
        return transport.safe_json_request(
            self,
            method=method,
            url=url,
            payload=payload,
            headers=headers,
            timeout=timeout,
            cache_key=cache_key,
            force_refresh=force_refresh,
            request_reason=request_reason,
        )

    def _safe_bytes_request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
        request_reason: str = "",
    ):
        return transport.safe_bytes_request(
            self,
            method=method,
            url=url,
            headers=headers,
            timeout=timeout,
            request_reason=request_reason,
        )

    def _resolve_force_refresh(self, force_refresh: bool | None) -> bool:
        return diagnostics.resolve_force_refresh(
            force_refresh=force_refresh,
            force_refresh_by_default=self.force_refresh_by_default,
        )

    def _ensure_enabled(self) -> None:
        diagnostics.ensure_enabled(enabled=self.enabled)

    def _ensure_shared_semaphore_capacity(self) -> None:
        diagnostics.ensure_shared_semaphore_capacity(self.__class__, concurrency=self.concurrency)

    def _wait_global_rate_limit_slot(self, *, reason: str) -> None:
        resilience.wait_global_rate_limit_slot(
            rate_limit_per_minute=self.rate_limit_per_minute,
            reason=reason,
        )

    def _ensure_circuit_is_closed(self) -> None:
        resilience.ensure_circuit_is_closed(cache_get=self._cache_get)

    def _mark_request_success(self) -> None:
        resilience.mark_request_success(cache_delete=self._cache_delete)

    def _mark_request_failure(self, *, exc: SupplierClientError) -> None:
        resilience.mark_request_failure(
            self,
            exc=exc,
            circuit_breaker_threshold=self.circuit_breaker_threshold,
            circuit_breaker_cooldown_seconds=self.circuit_breaker_cooldown_seconds,
            cache_set=self._cache_set,
            increment_metric=metrics.increment_metric,
            record_error_metrics=metrics.record_error_metrics,
        )

    def _is_retryable_error(self, *, exc: SupplierClientError) -> bool:
        return errors.is_retryable_error(exc)

    def _compute_backoff_seconds(self, *, attempt: int, status_code: int | None) -> float:
        return resilience.compute_backoff_seconds(
            backoff_base_seconds=self.backoff_base_seconds,
            attempt=attempt,
            status_code=status_code,
        )

    def _record_error_metrics(self, *, exc: SupplierClientError) -> None:
        metrics.record_error_metrics(self, exc=exc)

    def _is_timeout_error(self, *, exc: SupplierClientError) -> bool:
        return errors.is_timeout_error(exc)

    def _increment_metric(self, name: str, amount: int = 1) -> None:
        metrics.increment_metric(self, name, amount)

    def _recover_access_token_for_utr(self) -> tuple[str, str]:
        return auth.recover_access_token_for_utr(self)

    def _cache_key(self, *parts: str) -> str:
        return cache_helpers.build_cache_key(*parts)

    def _cache_get(self, key: str):
        return cache_helpers.cache_get(key)

    def _cache_set(self, key: str, value, *, timeout: int) -> None:
        cache_helpers.cache_set(key, value, timeout=timeout)

    def _cache_delete(self, key: str) -> None:
        cache_helpers.cache_delete(key)


__all__ = ["UtrClient", "SupplierTokenResult", "UtrBatchSearchResult"]
