from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MonobankInvoiceResult:
    invoice_id: str
    page_url: str
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class MonobankWidgetInitPayload:
    key_id: str
    request_id: str
    signature: str
    payload_base64: str


@dataclass(frozen=True)
class MonobankRateRow:
    pair: str
    currency_code_a: int
    currency_code_b: int
    rate_buy: float | None
    rate_sell: float | None
    rate_cross: float | None
    updated_at: datetime


@dataclass(frozen=True)
class MonobankConnectionCheckResult:
    ok: bool
    message: str
    public_key: str
