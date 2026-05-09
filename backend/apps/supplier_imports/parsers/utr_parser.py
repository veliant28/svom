from __future__ import annotations

from collections.abc import Iterable
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


class UTRParser:
    parser_code = "utr"
    DEFAULT_STOCK_SANE_MAX = 1_000_000
    _TECHNICAL_STOCK_EXCLUDE = {
        "row_number",
        "normalized_brand",
        "normalized_article",
        "supplier_sku",
        "stock_total",
        "review_decision",
        "review_reason",
    }

    def parse_rows(
        self,
        rows: Iterable[tuple[int, dict[str, str]]],
        *,
        file_name: str,
        context: ParserContext,
    ) -> ParseResult:
        offers, issues = self._parse_table_rows(rows=rows, context=context)
        return ParseResult(offers=offers, issues=issues)

    def parse_content(self, content: str, *, file_name: str, context: ParserContext) -> ParseResult:
        json_offers: list[ParsedOffer] = []
        json_issues: list[ParseIssue] = []

        payloads = extract_json_payloads(content)
        for payload in payloads:
            parsed, parsed_issues = self._parse_payload(payload=payload, context=context)
            json_offers.extend(parsed)
            json_issues.extend(parsed_issues)

        if json_offers:
            return ParseResult(offers=json_offers, issues=json_issues)

        if self._looks_like_table(content):
            table_offers, table_issues = self._parse_table(content=content, context=context)
            return ParseResult(offers=table_offers, issues=table_issues)

        return ParseResult(offers=json_offers, issues=json_issues)

    def _parse_payload(self, *, payload: Any, context: ParserContext) -> tuple[list[ParsedOffer], list[ParseIssue]]:
        if isinstance(payload, dict) and isinstance(payload.get("details"), list):
            return self._parse_details(payload["details"], context=context)

        if isinstance(payload, list):
            all_offers: list[ParsedOffer] = []
            all_issues: list[ParseIssue] = []
            for item in payload:
                if isinstance(item, dict) and isinstance(item.get("details"), list):
                    offers, issues = self._parse_details(item["details"], context=context)
                    all_offers.extend(offers)
                    all_issues.extend(issues)
            return all_offers, all_issues

        return [], []

    def _parse_details(self, details: list[dict[str, Any]], *, context: ParserContext) -> tuple[list[ParsedOffer], list[ParseIssue]]:
        offers: list[ParsedOffer] = []
        issues: list[ParseIssue] = []

        for index, detail in enumerate(details, start=1):
            if not isinstance(detail, dict):
                issues.append(
                    ParseIssue(
                        row_number=index,
                        message="Unsupported UTR detail row type.",
                        raw_payload={"value": detail},
                    )
                )
                continue

            article = str(detail.get("article") or detail.get("oem") or "").strip()
            external_sku = str(detail.get("productCode") or detail.get("id") or article).strip()
            brand_name = str(
                detail.get("displayBrand")
                or (detail.get("brand") or {}).get("name")
                or (detail.get("visibleBrand") or {}).get("title")
                or ""
            ).strip()
            product_name = str(detail.get("title") or (detail.get("detailCard") or {}).get("title") or "").strip()

            price_amount = (
                ((detail.get("yourPrice") or {}).get("amount"))
                or ((detail.get("yourPriceUAH") or {}).get("amount"))
                or ((detail.get("price") or {}).get("amount"))
            )
            price = parse_decimal(price_amount)

            currency = str(
                ((detail.get("yourPrice") or {}).get("currency") or {}).get("code")
                or ((detail.get("yourPriceUAH") or {}).get("currency") or {}).get("code")
                or ((detail.get("price") or {}).get("currency") or {}).get("code")
                or context.default_currency
            ).upper()

            stock_qty = parse_int(detail.get("totalRemains"))
            if stock_qty <= 0:
                remains = detail.get("remains") or []
                if isinstance(remains, list):
                    stock_qty = sum(parse_int(item.get("remain")) for item in remains if isinstance(item, dict))

            lead_time_days = parse_int(detail.get("leadTime") or detail.get("deliveryDays"))

            if not external_sku and not article:
                issues.append(
                    ParseIssue(
                        row_number=index,
                        message="UTR row has no article/external sku.",
                        error_code="missing_article",
                        raw_payload=detail,
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
                    raw_payload=detail,
                )
            )

        return offers, issues

    def _looks_like_table(self, content: str) -> bool:
        sample = content[:1024].lower()
        return any(
            token in sample
            for token in (
                "article",
                "brand",
                "yourprice",
                "price",
                "артикул",
                "бренд",
                "ціна",
                ";",
                "\t",
            )
        )

    def _parse_table(self, *, content: str, context: ParserContext) -> tuple[list[ParsedOffer], list[ParseIssue]]:
        return self._parse_table_rows(rows=parse_table_rows(content), context=context)

    def _parse_table_rows(
        self,
        *,
        rows: Iterable[tuple[int, dict[str, str]]],
        context: ParserContext,
    ) -> tuple[list[ParsedOffer], list[ParseIssue]]:
        mapping = context.mapping_config

        article_fields = resolve_field_names(mapping, "article_fields", ["article", "oem", "sku", "Артикул"])
        external_sku_fields = resolve_field_names(
            mapping,
            "external_sku_fields",
            ["external_sku", "supplier_sku", "id", "sku", "Артикул UTR"],
        )
        brand_fields = resolve_field_names(mapping, "brand_fields", ["displayBrand", "brand", "brand_name", "Бренд"])
        name_fields = resolve_field_names(mapping, "name_fields", ["title", "name", "product_name", "Найменування"])
        price_fields = resolve_field_names(mapping, "price_fields", ["yourPrice", "price", "your_price", "Ціна"])
        currency_fields = resolve_field_names(mapping, "currency_fields", ["currency", "currency_code", "Валюта"])
        stock_fields = resolve_field_names(mapping, "stock_fields", ["remain", "stock", "stock_qty", "quantity", "Кількість"])
        lead_time_fields = resolve_field_names(mapping, "lead_time_fields", ["lead_time", "lead_time_days", "delivery_days"])
        excluded_stock_keys = {
            *article_fields,
            *external_sku_fields,
            *brand_fields,
            *name_fields,
            *price_fields,
            *currency_fields,
            *lead_time_fields,
            *self._TECHNICAL_STOCK_EXCLUDE,
        }
        stock_sane_max = self._resolve_stock_sane_max(mapping=mapping)

        offers: list[ParsedOffer] = []
        issues: list[ParseIssue] = []

        for row_number, row in rows:
            article = str(extract_value(row, article_fields) or "").strip()
            external_sku = str(extract_value(row, external_sku_fields) or article).strip()
            brand_name = str(extract_value(row, brand_fields) or "").strip()
            product_name = str(extract_value(row, name_fields) or "").strip()
            price = parse_decimal(extract_value(row, price_fields))
            currency = str(extract_value(row, currency_fields) or context.default_currency).upper()

            stock_value, stock_status = self._parse_stock_candidate(extract_value(row, stock_fields), sane_max=stock_sane_max)
            stock_qty = max(stock_value, 0)
            stock_values_suspicious = 0
            stock_values_ignored = 0
            max_stock_component = stock_qty if stock_qty > 0 else 0
            if stock_status not in {"ok", "empty"}:
                stock_values_suspicious += 1
                stock_values_ignored += 1

            warehouse_fields = self._resolve_warehouse_stock_fields(
                row=row,
                mapping=mapping,
                excluded_stock_keys=excluded_stock_keys,
            )
            if stock_qty <= 0:
                stock_qty = 0
                for key in warehouse_fields:
                    parsed_stock, status = self._parse_stock_candidate(row.get(key), sane_max=stock_sane_max)
                    if status == "ok":
                        stock_qty += parsed_stock
                        if parsed_stock > max_stock_component:
                            max_stock_component = parsed_stock
                    elif status != "empty":
                        stock_values_suspicious += 1
                        stock_values_ignored += 1

            lead_time_days = parse_int(extract_value(row, lead_time_fields))

            if not external_sku and not article:
                issues.append(
                    ParseIssue(
                        row_number=row_number,
                        message="UTR table row has no article/external sku.",
                        error_code="missing_article",
                        raw_payload=row,
                    )
                )
                continue

            payload = dict(row)
            payload["_utr_stock_normalization"] = {
                "warehouse_fields_count": len(warehouse_fields),
                "stock_values_suspicious_count": int(stock_values_suspicious),
                "stock_values_ignored": int(stock_values_ignored),
                "max_stock_component": int(max_stock_component),
                "max_stock_total_after_normalization": int(max(stock_qty, 0)),
                "sane_max_threshold": int(stock_sane_max),
            }

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
                    raw_payload=payload,
                )
            )

        return offers, issues

    def _resolve_stock_sane_max(self, *, mapping: dict[str, Any]) -> int:
        raw = mapping.get("stock_sane_max")
        try:
            value = int(raw) if raw is not None else self.DEFAULT_STOCK_SANE_MAX
        except (TypeError, ValueError):
            value = self.DEFAULT_STOCK_SANE_MAX
        return max(value, 1)

    def _resolve_warehouse_stock_fields(
        self,
        *,
        row: dict[str, str],
        mapping: dict[str, Any],
        excluded_stock_keys: set[str],
    ) -> list[str]:
        configured = mapping.get("stock_warehouse_fields")
        if isinstance(configured, list):
            fields = [str(item).strip() for item in configured if str(item).strip()]
            return [item for item in fields if item in row]

        fields: list[str] = []
        for key in row.keys():
            if key in excluded_stock_keys:
                continue
            normalized = str(key).strip().lower()
            if (
                "обл" in normalized
                or "склад" in normalized
                or "київ" in normalized
                or "киев" in normalized
                or "kyiv" in normalized
            ):
                fields.append(key)
        return fields

    def _parse_stock_candidate(self, value: Any, *, sane_max: int) -> tuple[int, str]:
        parsed_decimal = parse_decimal(value)
        if parsed_decimal is None:
            raw = str(value or "").strip()
            return (0, "empty" if not raw else "non_numeric")
        if parsed_decimal < 0:
            return 0, "negative"
        parsed_int = int(parsed_decimal)
        if parsed_int > sane_max:
            return 0, "above_sane"
        return parsed_int, "ok"
