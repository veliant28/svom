from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

from .errors import is_timeout_error

METRIC_NAMES = (
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


def build_process_metrics(metric_names: tuple[str, ...]) -> dict[str, int]:
    return {name: 0 for name in metric_names}


def reset_process_metrics(cls) -> None:
    with cls._metrics_lock:
        cls._process_metrics = build_process_metrics(cls._metrics_names)


def get_process_metrics(cls) -> dict[str, int]:
    with cls._metrics_lock:
        return {name: int(cls._process_metrics.get(name, 0)) for name in cls._metrics_names}


def increment_metric(instance, name: str, amount: int = 1) -> None:
    if name not in instance._metrics_names:
        return
    increment = max(int(amount), 1)
    with instance.__class__._metrics_lock:
        current = int(instance.__class__._process_metrics.get(name, 0))
        instance.__class__._process_metrics[name] = current + increment


def record_error_metrics(instance, *, exc: SupplierClientError) -> None:
    if exc.status_code == 429:
        increment_metric(instance, "http_429_total")
    if isinstance(exc.status_code, int) and 500 <= exc.status_code <= 599:
        increment_metric(instance, "http_5xx_total")
    if is_timeout_error(exc):
        increment_metric(instance, "timeouts_total")
