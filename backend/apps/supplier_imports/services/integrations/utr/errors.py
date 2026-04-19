from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


def is_circuit_open_error(exc: SupplierClientError) -> bool:
    message = str(exc).strip().lower()
    return exc.status_code == 503 and "circuit breaker active" in message


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


def is_expired_token_error(exc: SupplierClientError) -> bool:
    message = str(exc).strip().lower()
    return "expired jwt token" in message


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


def is_retryable_error(exc: SupplierClientError) -> bool:
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


def is_timeout_error(exc: SupplierClientError) -> bool:
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
