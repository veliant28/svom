from __future__ import annotations

import threading

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


def resolve_force_refresh(*, force_refresh: bool | None, force_refresh_by_default: bool) -> bool:
    if force_refresh is None:
        return bool(force_refresh_by_default)
    return bool(force_refresh)


def ensure_enabled(*, enabled: bool) -> None:
    if enabled:
        return
    raise SupplierClientError("UTR integration disabled by UTR_ENABLED=0.")


def ensure_shared_semaphore_capacity(cls, *, concurrency: int) -> None:
    with cls._semaphore_lock:
        if cls._semaphore_size == concurrency:
            return
        cls._semaphore_size = concurrency
        cls._semaphore = threading.BoundedSemaphore(concurrency)
