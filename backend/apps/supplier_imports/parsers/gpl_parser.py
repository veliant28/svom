from __future__ import annotations

import json
import re
from typing import Any

from apps.supplier_imports.parsers.base import ParseIssue, ParsedOffer, ParseResult, ParserContext
from apps.supplier_imports.parsers.utils import (
    extract_json_payloads,
    extract_value,
    normalize_article,
    parse_decimal,
    parse_int,
    parse_table_rows,
    resolve_field_names,
)


_CURRENCY_BY_NUMERIC = {
    "980": "UAH",
    "840": "USD",
    "978": "EUR",
}

_RRC_PRICE_FIELDS: tuple[str, ...] = (
    "РРЦ грн.",
    "РРЦ",
    "rrc_currency_980",
    "rrp_currency_980",
    "rrc_price_currency_980",
    "rrp_price_currency_980",
    "recommended_price_currency_980",
    "RRC",
    "RRP",
    "rrc",
    "rrp",
)


class GPLParser:
    parser_code = "gpl"

    def parse_content(self, content: str, *, file_name: str, context: ParserContext) -> ParseResult:
        try:
            strict_payload = json.loads(content)
        except json.JSONDecodeError:
            strict_payload = None

        if strict_payload is not None:
            parsed, parsed_issues = self._parse_payload(payload=strict_payload, context=context)
            return ParseResult(offers=parsed, issues=parsed_issues)

        json_offers: list[ParsedOffer] = []
        json_issues: list[ParseIssue] = []

        payloads = extract_json_payloads(content)
        for payload in payloads:
            if not self._is_embedded_payload_supported(payload):
                continue
            parsed, parsed_issues = self._parse_payload(payload=payload, context=context)
            json_offers.extend(parsed)
            json_issues.extend(parsed_issues)

        if json_offers or json_issues:
            return ParseResult(offers=json_offers, issues=json_issues)

        if self._looks_like_table(content):
            table_offers, table_issues = self._parse_table(content=content, context=context)
            return ParseResult(offers=table_offers, issues=table_issues)

        return ParseResult(offers=json_offers, issues=json_issues)

    def _is_embedded_payload_supported(self, payload: Any) -> bool:
        if isinstance(payload, dict):
            if isinstance(payload.get("items"), list):
                return True
            data = payload.get("data")
            return isinstance(data, dict) and isinstance(data.get("items"), list)

        if isinstance(payload, list):
            return bool(payload) and isinstance(payload[0], dict)

        return False

    def _parse_payload(self, *, payload: Any, context: ParserContext) -> tuple[list[ParsedOffer], list[ParseIssue]]:
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return self._parse_items(data.get("items", []), context=context)

            if isinstance(payload.get("items"), list):
                return self._parse_items(payload.get("items", []), context=context)

        if isinstance(payload, list):
            return self._parse_items(payload, context=context)

        return [], []

    def _parse_items(self, items: list[dict[str, Any]], *, context: ParserContext) -> tuple[list[ParsedOffer], list[ParseIssue]]:
        offers: list[ParsedOffer] = []
        issues: list[ParseIssue] = []

        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                issues.append(
                    ParseIssue(
                        row_number=index,
                        message="Unsupported GPL item row type.",
                        raw_payload={"value": item},
                    )
                )
                continue

            article = str(item.get("article") or item.get("sku") or item.get("cid") or "").strip()
            external_sku = str(item.get("cid") or article).strip()
            brand_name = str(
                item.get("brand")
                or item.get("group")
                or item.get("Група ТД")
                or item.get("category")
                or item.get("Категорія")
                or item.get("manufacturer")
                or ""
            ).strip()
            product_name = str(item.get("name") or item.get("title") or "").strip()

            price_field = self._select_rrc_price_field(item=item)
            price = parse_decimal(item.get(price_field) if price_field else None)
            currency = self._resolve_currency(item=item, price_field=price_field, default=context.default_currency)

            stock_qty = self._extract_stock_quantity(item)
            lead_time_days = parse_int(item.get("lead_time") or item.get("lead_time_days") or item.get("delivery_days"))

            if not article and not external_sku:
                issues.append(
                    ParseIssue(
                        row_number=index,
                        message="GPL row has no article/external sku.",
                        error_code="missing_article",
                        raw_payload=item,
                    )
                )
                continue

            offers.append(
                ParsedOffer(
                    supplier=context.source_code,
                    external_sku=external_sku or article,
                    article=article or external_sku,
                    normalized_article=normalize_article(article or external_sku),
                    brand_name=brand_name,
                    product_name=product_name,
                    price=price,
                    currency=currency,
                    stock_qty=max(stock_qty, 0),
                    lead_time_days=max(lead_time_days, 0),
                    raw_payload=item,
                )
            )

        return offers, issues

    def _select_rrc_price_field(self, *, item: dict[str, Any]) -> str | None:
        for field_name in _RRC_PRICE_FIELDS:
            if field_name in item:
                return field_name

        for key in item.keys():
            if isinstance(key, str) and self._is_rrc_field_name(key):
                return key
        return None

    @staticmethod
    def _is_rrc_field_name(field_name: str) -> bool:
        normalized = field_name.strip().lower()
        if not normalized:
            return False
        if "ррц" in normalized:
            return True
        return bool(re.search(r"\brrc\b|\brrp\b|recommended_price", normalized))

    def _resolve_currency(self, *, item: dict[str, Any], price_field: str | None, default: str) -> str:
        if isinstance(item.get("currency"), dict):
            value = item.get("currency", {}).get("currency")
            if value:
                return str(value).upper()

        if price_field:
            match = re.search(r"_(\d{3})$", price_field)
            if match:
                return _CURRENCY_BY_NUMERIC.get(match.group(1), default)

        return default.upper()

    def _extract_stock_quantity(self, item: dict[str, Any]) -> int:
        warehouses = [parse_int(value) for key, value in item.items() if str(key).startswith("count_warehouse_")]
        if not warehouses:
            warehouses = [parse_int(value) for key, value in item.items() if str(key).startswith("Склад")]
        if warehouses:
            return sum(warehouses)
        return parse_int(item.get("stock_qty") or item.get("count") or item.get("quantity"))

    def _looks_like_table(self, content: str) -> bool:
        sample = content[:1024].lower()
        return any(
            token in sample
            for token in (
                "article",
                "price_currency",
                "count_warehouse",
                "артикул",
                "ціна",
                "склад",
                ";",
                "\t",
            )
        )

    def _parse_table(self, *, content: str, context: ParserContext) -> tuple[list[ParsedOffer], list[ParseIssue]]:
        mapping = context.mapping_config

        article_fields = resolve_field_names(mapping, "article_fields", ["article", "sku", "cid", "Артикул", "Артикул ТД"])
        external_sku_fields = resolve_field_names(mapping, "external_sku_fields", ["cid", "external_sku", "supplier_sku", "Код"])
        brand_fields = resolve_field_names(
            mapping,
            "brand_fields",
            ["brand", "group", "Група ТД", "category", "Категорія", "manufacturer"],
        )
        name_fields = resolve_field_names(mapping, "name_fields", ["name", "title", "Найменування"])
        price_fields = resolve_field_names(
            mapping,
            "price_fields",
            list(_RRC_PRICE_FIELDS),
        )
        price_fields = [field_name for field_name in price_fields if self._is_rrc_field_name(str(field_name))]
        if not price_fields:
            price_fields = list(_RRC_PRICE_FIELDS)
        currency_fields = resolve_field_names(mapping, "currency_fields", ["currency", "currency_code", "Валюта"])
        stock_fields = resolve_field_names(mapping, "stock_fields", ["stock_qty", "count", "quantity"])
        lead_time_fields = resolve_field_names(mapping, "lead_time_fields", ["lead_time", "lead_time_days", "delivery_days"])

        offers: list[ParsedOffer] = []
        issues: list[ParseIssue] = []

        for row_number, row in parse_table_rows(content):
            article = str(extract_value(row, article_fields) or "").strip()
            external_sku = str(extract_value(row, external_sku_fields) or article).strip()
            brand_name = str(extract_value(row, brand_fields) or "").strip()
            product_name = str(extract_value(row, name_fields) or "").strip()

            price_value = extract_value(row, price_fields)
            if price_value is None:
                for key, value in row.items():
                    if self._is_rrc_field_name(key):
                        price_value = value
                        break
            price = parse_decimal(price_value)

            currency = str(extract_value(row, currency_fields) or context.default_currency).upper()
            stock_qty = parse_int(extract_value(row, stock_fields))
            if stock_qty == 0:
                stock_qty = sum(
                    parse_int(value)
                    for key, value in row.items()
                    if key.startswith("count_warehouse_") or key.startswith("Склад")
                )

            lead_time_days = parse_int(extract_value(row, lead_time_fields))

            if not article and not external_sku:
                issues.append(
                    ParseIssue(
                        row_number=row_number,
                        message="GPL table row has no article/external sku.",
                        error_code="missing_article",
                        raw_payload=row,
                    )
                )
                continue

            offers.append(
                ParsedOffer(
                    supplier=context.source_code,
                    external_sku=external_sku or article,
                    article=article or external_sku,
                    normalized_article=normalize_article(article or external_sku),
                    brand_name=brand_name,
                    product_name=product_name,
                    price=price,
                    currency=currency,
                    stock_qty=max(stock_qty, 0),
                    lead_time_days=max(lead_time_days, 0),
                    raw_payload=row,
                )
            )

        return offers, issues
