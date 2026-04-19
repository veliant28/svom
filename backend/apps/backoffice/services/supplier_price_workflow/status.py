from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


def normalize_status_value(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "_")


def is_ready_status(status: str) -> bool:
    return status in {"ready", "complete", "completed", "downloaded", "uploaded"}


def is_failed_status(status: str) -> bool:
    return status in {"failed", "error", "cancelled", "canceled"}


def extract_remote_status(payload: dict | str) -> str:
    if isinstance(payload, str):
        return normalize_status_value(payload)
    if not isinstance(payload, dict):
        return ""
    for key in ("status", "data", "state"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_status_value(value)
    return ""


def is_utr_nonfatal_delete_error(exc: SupplierClientError) -> bool:
    status_code = exc.status_code or 0
    message = str(exc).strip().lower()
    if not message:
        return False
    if status_code == 404:
        return True
    if status_code not in {400, 409}:
        return False
    markers = (
        "not found",
        "not ready",
        "already deleted",
        "не найден",
        "не готов",
        "ще не готов",
    )
    return any(marker in message for marker in markers)


def generation_wait_seconds(*, expected_ready_at) -> int:
    if not expected_ready_at:
        return 1
    delta = int((expected_ready_at - timezone.now()).total_seconds())
    return max(delta, 1)
