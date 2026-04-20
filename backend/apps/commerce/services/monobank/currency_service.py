from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any

from django.utils import timezone

from .client import MonobankApiClient
from .invoice_service import get_monobank_settings, is_currency_snapshot_fresh


TARGET_CURRENCY_PAIRS = {
    (840, 980): "USD/UAH",
    (978, 980): "EUR/UAH",
}


def get_currency_rates(*, force_refresh: bool = False) -> dict[str, Any]:
    settings = get_monobank_settings()

    if not force_refresh and settings.currency_rates_snapshot and is_currency_snapshot_fresh(settings):
        return {
            "rows": settings.currency_rates_snapshot,
            "last_fetched_at": settings.last_currency_sync_at,
        }

    rows = _normalize_currency_rows(MonobankApiClient.get_public_currency())

    now = timezone.now()
    settings.currency_rates_snapshot = rows
    settings.last_currency_sync_at = now
    settings.last_sync_at = now
    settings.save(update_fields=("currency_rates_snapshot", "last_currency_sync_at", "last_sync_at", "updated_at"))

    return {
        "rows": rows,
        "last_fetched_at": now,
    }


def _normalize_currency_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in raw_rows:
        currency_code_a = _as_int(row.get("currencyCodeA"))
        currency_code_b = _as_int(row.get("currencyCodeB"))
        if currency_code_a is None or currency_code_b is None:
            continue

        pair_label = TARGET_CURRENCY_PAIRS.get((currency_code_a, currency_code_b))
        if not pair_label:
            continue

        date_value = _as_int(row.get("date")) or 0
        updated_at = datetime.fromtimestamp(max(date_value, 0), tz=dt_timezone.utc)

        normalized.append(
            {
                "pair": pair_label,
                "currency_code_a": currency_code_a,
                "currency_code_b": currency_code_b,
                "rate_buy": _as_float(row.get("rateBuy")),
                "rate_sell": _as_float(row.get("rateSell")),
                "rate_cross": _as_float(row.get("rateCross")),
                "updated_at": updated_at.isoformat(),
            }
        )

    normalized.sort(key=lambda item: item["pair"])
    return normalized


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
