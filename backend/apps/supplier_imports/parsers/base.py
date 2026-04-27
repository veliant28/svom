from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class ParserContext:
    source_code: str
    mapping_config: dict[str, Any] = field(default_factory=dict)
    default_currency: str = "UAH"


@dataclass(frozen=True)
class ParsedOffer:
    supplier: str
    external_sku: str
    article: str
    normalized_article: str
    brand_name: str
    product_name: str
    price: Decimal | None
    currency: str
    stock_qty: int
    lead_time_days: int
    raw_payload: dict[str, Any]
    price_levels: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ParseIssue:
    message: str
    row_number: int | None = None
    external_sku: str = ""
    error_code: str = "parse_error"
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParseResult:
    offers: list[ParsedOffer] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)


class SupplierOfferParser(Protocol):
    parser_code: str

    def parse_content(self, content: str, *, file_name: str, context: ParserContext) -> ParseResult: ...
