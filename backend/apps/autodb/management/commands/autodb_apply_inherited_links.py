from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.autodb.management.commands.autodb_audit_inherited_link_opportunities import (
    Command as InheritedAuditCommand,
    InheritedAuditRow,
)
from apps.autodb.services import can_use_autodb_fitments_for_public_filtering
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.supplier_imports.parsers.utils import normalize_brand


def _brand_hint_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").strip().upper(), flags=re.UNICODE)


@dataclass
class ApplyRow:
    product_id: str
    raw_brand: str
    raw_article: str
    raw_product_name: str
    inherited_autodb_article_key: str
    autodb_title: str
    confidence: float
    recommendation: str
    suspicious_status: str
    link_quality_status: str


@dataclass
class ApplyResult:
    action: str
    reason: str


class Command(BaseCommand):
    help = "Strict-safe apply inherited links from audit opportunities."

    NON_AUTO_BRAND_HINTS = {
        _brand_hint_key("CS SYSTEM"),
        _brand_hint_key("MR.BUILD"),
        _brand_hint_key("MR BUILD"),
        _brand_hint_key("NOVOABRASIVE"),
        _brand_hint_key("VIRA"),
        _brand_hint_key("K2"),
        _brand_hint_key("БЕЗ БРЕНДУ"),
        _brand_hint_key("ТМК"),
    }

    RISKY_CASES = (
        ("LSA", "411124", "300:820099"),
        ("MITKA", "MII107", "300:820099"),
        ("WIX FILTERS", "325193", "324:WL7042"),
    )

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="", help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=0, help="Limit candidate rows after grouping")
        parser.add_argument("--min-confidence", type=float, default=0.8, help="Minimum confidence for apply")
        parser.add_argument(
            "--only-high-confidence",
            action="store_true",
            help="Select only can_inherit_high_confidence candidates before applying limit",
        )
        parser.add_argument(
            "--order-by",
            type=str,
            default="",
            help="Optional ordering for selected candidates. Supported: confidence",
        )
        parser.add_argument(
            "--brand",
            type=str,
            default="",
            help='Optional brand filter, e.g. "WIX FILTERS" or "WIX FILTERS,MANN-FILTER"',
        )
        parser.add_argument("--dry-run", action="store_true", help="Do not write Product changes")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV output path")
        parser.add_argument("--wait-for-autodb", type=int, default=0, help="Wait up to N seconds for local Auto_DB_Pro readiness")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE.")

        limit = max(int(options.get("limit") or 0), 0)
        min_confidence = max(min(float(options.get("min_confidence") or 0.8), 1.0), 0.0)
        only_high_confidence = bool(options.get("only_high_confidence"))
        order_by = str(options.get("order_by") or "").strip().lower()
        raw_brand_filter = str(options.get("brand") or "").strip()
        dry_run = bool(options.get("dry_run"))
        export_csv = str(options.get("export_csv") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        if order_by and order_by != "confidence":
            raise CommandError("Unsupported --order-by value. Supported: confidence")
        brand_filter_keys = self._parse_brand_filters(raw_brand_filter)

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} reason={readiness.reason}"
            )

        self.stdout.write(
            "Auto_DB_Pro apply inherited links started "
            f"supplier={supplier_code} limit={limit or 'none'} dry_run={dry_run} "
            f"only_high_confidence={only_high_confidence} order_by={order_by or '-'} "
            f"brand_filter={raw_brand_filter or '-'} min_confidence={min_confidence:.2f}"
        )

        audit_rows = self._load_audit_rows(supplier_code=supplier_code, limit=0)
        scoped_rows = self._filter_audit_rows_by_brand(rows=audit_rows, brand_filter_keys=brand_filter_keys)
        candidates = self._to_candidates(scoped_rows)

        product_ids = {item.product_id for item in candidates}
        products = {str(key): value for key, value in Product.objects.in_bulk(product_ids).items()}

        summary = {
            "candidates_total": len(candidates),
            "high_confidence_candidates": 0,
            "safe_candidates": 0,
            "applied": 0,
            "would_apply": 0,
            "skipped_low_confidence": 0,
            "skipped_needs_manual_review": 0,
            "skipped_suspicious": 0,
            "skipped_non_auto": 0,
            "skipped_already_linked": 0,
            "failed": 0,
        }
        actions: list[dict[str, Any]] = []
        eligible_candidates: list[ApplyRow] = []

        for row in candidates:
            product = products.get(row.product_id)
            result = self._prequalify_row(
                row=row,
                product=product,
                min_confidence=min_confidence,
                only_high_confidence=only_high_confidence,
                summary=summary,
            )
            if result.action == "eligible":
                eligible_candidates.append(row)
            else:
                actions.append(
                    {
                        "product_id": row.product_id,
                        "raw_brand": row.raw_brand,
                        "raw_article": row.raw_article,
                        "raw_product_name": row.raw_product_name,
                        "inherited_autodb_article_key": row.inherited_autodb_article_key,
                        "autodb_title": row.autodb_title,
                        "confidence": f"{row.confidence:.2f}",
                        "action": "skip",
                        "reason": result.reason,
                    }
                )

        summary["high_confidence_candidates"] = len(eligible_candidates)
        if order_by == "confidence":
            eligible_candidates.sort(
                key=lambda item: (
                    -item.confidence,
                    normalize_brand(item.raw_brand or ""),
                    str(item.raw_article or "").strip().upper(),
                )
            )
        if limit > 0:
            eligible_candidates = eligible_candidates[:limit]
        summary["safe_candidates"] = len(eligible_candidates)

        for row in eligible_candidates:
            result = self._apply_prequalified_row(row=row, product=products.get(row.product_id), dry_run=dry_run, summary=summary)
            actions.append(
                {
                    "product_id": row.product_id,
                    "raw_brand": row.raw_brand,
                    "raw_article": row.raw_article,
                    "raw_product_name": row.raw_product_name,
                    "inherited_autodb_article_key": row.inherited_autodb_article_key,
                    "autodb_title": row.autodb_title,
                    "confidence": f"{row.confidence:.2f}",
                    "action": result.action,
                    "reason": result.reason,
                }
            )

        self._print_summary(summary=summary)
        self._print_focused_cases(actions=actions)
        if export_csv:
            self._export_csv(path=export_csv, rows=actions)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")
        self.stdout.write("- next_step_hint: run enrichment commands separately if needed")

    def _load_audit_rows(self, *, supplier_code: str, limit: int) -> list[InheritedAuditRow]:
        audit = InheritedAuditCommand()
        offers = audit._build_queryset(supplier_code=supplier_code, limit=limit)
        return audit._audit_inherited_offers(offers=offers)

    def _to_candidates(self, rows: list[InheritedAuditRow]) -> list[ApplyRow]:
        grouped: dict[tuple[str, str, str, str], ApplyRow] = {}
        for item in rows:
            key = (
                item.matched_product_id,
                item.inherited_autodb_article_key,
                normalize_brand(item.raw_brand or ""),
                str(item.raw_article or "").strip().upper(),
            )
            confidence = self._confidence(item.reason)
            current = grouped.get(key)
            candidate = ApplyRow(
                product_id=item.matched_product_id,
                raw_brand=item.raw_brand,
                raw_article=item.raw_article,
                raw_product_name=item.raw_product_name,
                inherited_autodb_article_key=item.inherited_autodb_article_key,
                autodb_title=item.autodb_title,
                confidence=confidence,
                recommendation=item.recommendation,
                suspicious_status=item.suspicious_status,
                link_quality_status=item.link_quality_status,
            )
            if current is None or candidate.confidence > current.confidence:
                grouped[key] = candidate
        return list(grouped.values())

    def _prequalify_row(
        self,
        *,
        row: ApplyRow,
        product: Product | None,
        min_confidence: float,
        only_high_confidence: bool,
        summary: dict[str, int],
    ) -> ApplyResult:
        if product is None:
            summary["failed"] += 1
            return ApplyResult(action="skip", reason="product_not_found")

        if row.recommendation in {"needs_manual_review", "blocked_by_suspicious_quality"}:
            summary["skipped_needs_manual_review"] += 1
            return ApplyResult(action="skip", reason=row.recommendation)
        if row.recommendation in {"suspicious_do_not_inherit"}:
            summary["skipped_suspicious"] += 1
            return ApplyResult(action="skip", reason="suspicious_do_not_inherit")
        if row.recommendation == "non_auto_ignore":
            summary["skipped_non_auto"] += 1
            return ApplyResult(action="skip", reason="non_auto_ignore")
        if row.recommendation == "can_inherit_medium_confidence":
            summary["skipped_low_confidence"] += 1
            return ApplyResult(action="skip", reason="medium_confidence_not_allowed")
        if only_high_confidence and row.recommendation != "can_inherit_high_confidence":
            summary["skipped_needs_manual_review"] += 1
            return ApplyResult(action="skip", reason=f"only_high_confidence_filtered:{row.recommendation}")
        if row.recommendation != "can_inherit_high_confidence":
            summary["skipped_needs_manual_review"] += 1
            return ApplyResult(action="skip", reason=f"unsupported_recommendation:{row.recommendation}")

        if row.confidence < min_confidence:
            summary["skipped_low_confidence"] += 1
            return ApplyResult(action="skip", reason=f"low_confidence:{row.confidence:.2f}")

        if row.suspicious_status == "yes":
            summary["skipped_suspicious"] += 1
            return ApplyResult(action="skip", reason="suspicious_status")
        if row.link_quality_status in {
            AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        }:
            summary["skipped_suspicious"] += 1
            return ApplyResult(action="skip", reason=f"link_quality:{row.link_quality_status}")
        if not can_use_autodb_fitments_for_public_filtering(product=product):
            summary["skipped_suspicious"] += 1
            return ApplyResult(action="skip", reason="public_filtering_blocked")
        if self._is_non_auto_or_invalid_brand(row.raw_brand):
            summary["skipped_non_auto"] += 1
            return ApplyResult(action="skip", reason="invalid_or_non_auto_brand")

        key = str(row.inherited_autodb_article_key or "").strip()
        if not key or ":" not in key:
            summary["failed"] += 1
            return ApplyResult(action="failed", reason="invalid_autodb_article_key")
        supplier_part, article_number = key.split(":", 1)
        try:
            supplier_id = int(supplier_part)
        except (TypeError, ValueError):
            summary["failed"] += 1
            return ApplyResult(action="skip", reason="invalid_supplier_id_in_key")

        if str(product.autodb_article_key or "").strip() != key:
            summary["failed"] += 1
            return ApplyResult(action="skip", reason="product_key_mismatch")

        return ApplyResult(action="eligible", reason="strict_safe_passed")

    def _apply_prequalified_row(
        self,
        *,
        row: ApplyRow,
        product: Product | None,
        dry_run: bool,
        summary: dict[str, int],
    ) -> ApplyResult:
        if product is None:
            summary["failed"] += 1
            return ApplyResult(action="failed", reason="product_not_found")
        key = str(row.inherited_autodb_article_key or "").strip()
        supplier_part, article_number = key.split(":", 1)
        supplier_id = int(supplier_part)

        needs_update = (
            product.autodb_supplier_id != supplier_id
            or str(product.autodb_article_number or "").strip() != article_number
            or str(product.catalog_source or "").strip() != Product.CATALOG_SOURCE_AUTODB_PRO
        )
        if not needs_update:
            summary["skipped_already_linked"] += 1
            return ApplyResult(action="skip", reason="already_linked_same_bridge")
        if dry_run:
            summary["would_apply"] += 1
            return ApplyResult(action="dry_run_apply", reason="strict_safe_passed")

        product.autodb_supplier_id = supplier_id
        product.autodb_article_number = article_number
        product.autodb_article_key = key
        product.catalog_source = Product.CATALOG_SOURCE_AUTODB_PRO
        with transaction.atomic():
            product.save(
                update_fields=(
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "autodb_article_key",
                    "catalog_source",
                    "updated_at",
                )
            )
        summary["applied"] += 1
        return ApplyResult(action="applied", reason="strict_safe_passed")

    def _parse_brand_filters(self, raw_value: str) -> set[str]:
        if not raw_value:
            return set()
        values = [part.strip() for part in raw_value.split(",")]
        return {_brand_hint_key(item) for item in values if item}

    def _filter_audit_rows_by_brand(self, *, rows: list[InheritedAuditRow], brand_filter_keys: set[str]) -> list[InheritedAuditRow]:
        if not brand_filter_keys:
            return rows
        return [row for row in rows if _brand_hint_key(row.raw_brand) in brand_filter_keys]

    def _is_non_auto_or_invalid_brand(self, raw_brand: str) -> bool:
        normalized = normalize_brand(raw_brand or "")
        if not normalized:
            return True
        return _brand_hint_key(raw_brand) in self.NON_AUTO_BRAND_HINTS

    def _confidence(self, reason: str) -> float:
        text = str(reason or "").strip().lower()
        if text.startswith("token_overlap="):
            try:
                return max(min(float(text.split("=", 1)[1]), 1.0), 0.0)
            except (TypeError, ValueError):
                return 0.0
        if text.startswith("article_number_present_in_autodb_title"):
            return 1.0
        if text.startswith("article_number_in_article_field"):
            return 1.0
        if text.startswith("article_number_in_external_sku"):
            return 1.0
        if text.startswith("article_number_in_raw_name"):
            return 1.0
        return 0.0

    def _print_summary(self, *, summary: dict[str, int]):
        self.stdout.write("Apply inherited links summary:")
        self.stdout.write(f"- candidates_total: {summary['candidates_total']}")
        self.stdout.write(f"- high_confidence_candidates: {summary['high_confidence_candidates']}")
        self.stdout.write(f"- safe_candidates: {summary['safe_candidates']}")
        self.stdout.write(f"- applied: {summary['applied']}")
        self.stdout.write(f"- would_apply: {summary['would_apply']}")
        self.stdout.write(f"- skipped_low_confidence: {summary['skipped_low_confidence']}")
        self.stdout.write(f"- skipped_needs_manual_review: {summary['skipped_needs_manual_review']}")
        self.stdout.write(f"- skipped_suspicious: {summary['skipped_suspicious']}")
        self.stdout.write(f"- skipped_non_auto: {summary['skipped_non_auto']}")
        self.stdout.write(f"- skipped_already_linked: {summary['skipped_already_linked']}")
        self.stdout.write(f"- failed: {summary['failed']}")

    def _print_focused_cases(self, *, actions: list[dict[str, Any]]):
        self.stdout.write("Focused risky cases (must stay skipped):")
        by_key = {
            (
                normalize_brand(str(item.get("raw_brand") or "")),
                str(item.get("raw_article") or "").strip().upper(),
                str(item.get("inherited_autodb_article_key") or "").strip(),
            ): item
            for item in actions
        }
        for raw_brand, raw_article, expected_key in self.RISKY_CASES:
            key = (normalize_brand(raw_brand), str(raw_article).strip().upper(), expected_key)
            item = by_key.get(key)
            if not item:
                self.stdout.write(f"- {raw_brand} / {raw_article} / {expected_key}: not_in_current_selection")
                continue
            self.stdout.write(
                f"- {raw_brand} / {raw_article} / {expected_key}: action={item['action']} reason={item['reason']} "
                f"confidence={item['confidence']}"
            )

    def _export_csv(self, *, path: str, rows: list[dict[str, Any]]):
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "raw_brand",
                    "raw_article",
                    "raw_product_name",
                    "inherited_autodb_article_key",
                    "autodb_title",
                    "confidence",
                    "action",
                    "reason",
                ],
            )
            writer.writeheader()
            for item in rows:
                writer.writerow(item)
