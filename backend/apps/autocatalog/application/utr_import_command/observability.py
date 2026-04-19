from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.conf import settings

from apps.supplier_imports.services.integrations.utr_client import UtrClient

from .types import CommandOutput


def is_utr_enabled() -> bool:
    return bool(getattr(settings, "UTR_ENABLED", True))


def reset_process_metrics() -> None:
    UtrClient.reset_process_metrics()


def resolve_force_refresh(raw_options: Mapping[str, Any]) -> bool:
    return bool(raw_options.get("force_refresh") or getattr(settings, "UTR_FORCE_REFRESH", False))


def is_unsafe_force_refresh_enabled() -> bool:
    return bool(getattr(settings, "UTR_UNSAFE_ALLOW_FORCE_REFRESH", False))


def empty_run_counters() -> dict[str, int]:
    return {
        "skipped_due_to_existing_lock": 0,
        "skipped_due_to_force_refresh_protection": 0,
    }


def write_observability(output: CommandOutput, *, run_counters: dict[str, int]) -> None:
    output.write("[utr-observability]")
    metrics = UtrClient.get_process_metrics()
    for key in (
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
    ):
        output.write(f"  - {key}: {int(metrics.get(key, 0))}")

    output.write(f"  - skipped_due_to_existing_lock: {int(run_counters.get('skipped_due_to_existing_lock', 0))}")
    output.write(
        "  - skipped_due_to_force_refresh_protection: "
        f"{int(run_counters.get('skipped_due_to_force_refresh_protection', 0))}"
    )
