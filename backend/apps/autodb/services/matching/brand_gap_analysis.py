from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.db import connections
from django.db.models import Q, Sum
from openpyxl import Workbook

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.matching.brand_coverage import AutoDbBrandCoverageAuditService
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolver
from apps.autodb.services.matching.constants import NON_TECDOC_BRAND_KEYS
from apps.autodb.services.matching.deterministic_brand_binding import DeterministicBrandNormalizer
from apps.autodb.services.matching.reports import write_report
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


INVALID_BRAND_VALUES = {
    "",
    "-",
    "--",
    "N/A",
    "NA",
    "NONE",
    "NULL",
    "UNKNOWN",
    "УДАЛЕННЫЕ",
    "УДАЛЕННЫЙ",
    "УДАЛЕН",
    "УДАЛЕНА",
    "УГОРЩИНА",
}

INVALID_BRAND_PATTERNS = (
    re.compile(r"^УДАЛ[ЕЁ]Н", re.IGNORECASE),
    re.compile(r"^REMOVED?$", re.IGNORECASE),
    re.compile(r"^DELETED?$", re.IGNORECASE),
)


class AutoDbBrandGapAnalysisService:
    def __init__(self):
        self.out = Path("/tmp")
        self.normalizer = DeterministicBrandNormalizer()
        self.resolver = AutoDbBrandResolver()

    def run(self) -> dict[str, Any]:
        before = self._integrity_snapshot()

        coverage_rows = [asdict(item) for item in AutoDbBrandCoverageAuditService().audit(supplier_code="", limit=0)]
        suppliers, by_variant = self._load_suppliers()

        blocked_needs_alias_rows = self._analyze_blocked_needs_alias(coverage_rows, suppliers, by_variant)
        self._export_blocked_needs_alias(blocked_needs_alias_rows)

        correction_rows = self._build_blocked_needs_alias_decision_dry_run(blocked_needs_alias_rows)
        self._export_blocked_decision_dry_run(correction_rows)

        prioritized_rows = self._build_missing_prioritized(coverage_rows, suppliers, by_variant)
        self._export_missing_prioritized(prioritized_rows)

        shortlist_rows = self._build_shortlist(prioritized_rows)
        self._export_shortlist(shortlist_rows)

        unsafe_rows = self._build_unsafe_ambiguous_review(coverage_rows)
        self._export_unsafe_review(unsafe_rows)

        summary_md = self._build_next_steps_summary(
            blocked_rows=blocked_needs_alias_rows,
            prioritized_rows=prioritized_rows,
            unsafe_rows=unsafe_rows,
            coverage_rows=coverage_rows,
        )
        (self.out / "autodb_service_brand_gap_next_steps_summary.md").write_text(summary_md, encoding="utf-8")

        after = self._integrity_snapshot()
        integrity_rows = self._integrity_rows(before, after)
        self._export_integrity(integrity_rows)

        return {
            "coverage_rows": coverage_rows,
            "blocked_rows": blocked_needs_alias_rows,
            "prioritized_rows": prioritized_rows,
            "unsafe_rows": unsafe_rows,
            "before": before,
            "after": after,
        }

    def _load_suppliers(self) -> tuple[dict[int, dict[str, Any]], dict[str, set[int]]]:
        with connections["auto_db_pro"].cursor() as cur:
            cur.execute("SELECT id, description, COALESCE(matchcode, ''), COALESCE(nbrofarticles, 0) FROM suppliers")
            raw_rows = cur.fetchall()

        suppliers: dict[int, dict[str, Any]] = {}
        by_variant: dict[str, set[int]] = defaultdict(set)
        for sid, description, matchcode, nbrofarticles in raw_rows:
            try:
                supplier_id = int(sid)
            except Exception:
                continue
            supplier_name = str(description or "").strip()
            supplier_matchcode = str(matchcode or "").strip()
            if not supplier_name:
                continue
            variants = set(self.normalizer.variants(supplier_name))
            variants.update(self.normalizer.variants(supplier_matchcode))
            if not variants:
                continue
            suppliers[supplier_id] = {
                "supplier_id": supplier_id,
                "description": supplier_name,
                "matchcode": supplier_matchcode,
                "nbrofarticles": int(nbrofarticles or 0),
                "variants": sorted(variants),
            }
            for variant in variants:
                by_variant[variant].add(supplier_id)
        return suppliers, by_variant

    def _analyze_blocked_needs_alias(
        self,
        coverage_rows: list[dict[str, Any]],
        suppliers: dict[int, dict[str, Any]],
        by_variant: dict[str, set[int]],
    ) -> list[dict[str, Any]]:
        target = {"УГОРЩИНА", "УДАЛЕННЫЕ"}
        out: list[dict[str, Any]] = []
        for row in coverage_rows:
            if str(row.get("decision") or "") != "needs_alias":
                continue
            raw_brand = str(row.get("raw_brand") or "").strip()
            normalized = str(row.get("normalized_raw_brand") or normalize_brand(raw_brand))
            if normalize_brand(raw_brand) not in target and normalize_brand(raw_brand.upper()) not in target:
                # Keep full needs_alias coverage, but still prioritize known two labels.
                pass

            supplier_code = str(row.get("supplier_code") or "").strip()
            sample_skus, sample_names = self._sample_products(raw_brand=raw_brand, supplier_code=supplier_code, limit=8)
            origin = self._source_origin(raw_brand=raw_brand, supplier_code=supplier_code, sample_limit=5)
            candidate_ids = self._supplier_candidates_from_variants(raw_brand, suppliers, by_variant)
            reason = "no deterministic supplier candidate in auto_db_pro.suppliers"
            if not normalized:
                reason = "raw brand normalizes to empty value; resolver falls into needs_alias"
            recommended_status = self._recommended_status_for_blocked(raw_brand=raw_brand, normalized=normalized, candidate_ids=candidate_ids)

            out.append(
                {
                    "supplier_code": supplier_code,
                    "raw_brand": raw_brand,
                    "normalized_raw_brand": normalized,
                    "product_count": int(row.get("product_count") or 0),
                    "stock_gt_0_count": int(row.get("stock_gt_0_count") or 0),
                    "product_price_count": int(row.get("product_price_count") or 0),
                    "sample_skus": sample_skus,
                    "sample_product_names": sample_names,
                    "source_import_origin": origin,
                    "service_current_decision": "needs_alias",
                    "why_service_classified_as_needs_alias": reason,
                    "recommended_reclassification": recommended_status,
                }
            )
        out.sort(key=lambda item: (item["raw_brand"] not in {"Угорщина", "Удаленные"}, item["supplier_code"], item["raw_brand"]))
        return out

    def _build_blocked_needs_alias_decision_dry_run(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            decision = str(row.get("recommended_reclassification") or "keep_unmapped_missing_supplier")
            dry_run_decision = {
                "non_tecdoc": "mark_non_tecdoc",
                "invalid_brand_value": "mark_invalid_brand_value",
                "keep_unmapped_missing_supplier": "keep_unmapped_missing_supplier",
                "needs_human_approval": "needs_human_approval",
            }.get(decision, "needs_human_approval")
            out.append(
                {
                    "supplier_code": row.get("supplier_code") or "",
                    "raw_brand": row.get("raw_brand") or "",
                    "normalized_raw_brand": row.get("normalized_raw_brand") or "",
                    "current_decision": "needs_alias",
                    "dry_run_decision": dry_run_decision,
                    "apply_mode": "staging_only_no_persistent_decision_layer",
                    "would_apply_now": "no",
                    "reason": "service has no persistent brand decision override table in this flow",
                }
            )
        return out

    def _build_missing_prioritized(
        self,
        coverage_rows: list[dict[str, Any]],
        suppliers: dict[int, dict[str, Any]],
        by_variant: dict[str, set[int]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in coverage_rows:
            if str(row.get("decision") or "") != "keep_unmapped_missing_supplier":
                continue
            raw_brand = str(row.get("raw_brand") or "").strip()
            normalized = str(row.get("normalized_raw_brand") or normalize_brand(raw_brand))
            supplier_code = str(row.get("supplier_code") or "").strip()
            product_count = int(row.get("product_count") or 0)
            stock_count = int(row.get("stock_gt_0_count") or 0)
            price_count = int(row.get("product_price_count") or 0)

            sample_skus, sample_names = self._sample_products(raw_brand=raw_brand, supplier_code=supplier_code, limit=5)
            candidate_ids = self._supplier_candidates_from_variants(raw_brand, suppliers, by_variant)
            candidate_str = self._candidate_str(candidate_ids, suppliers)

            likely_classification, recommended_action, confidence, reason = self._classify_missing_row(
                raw_brand=raw_brand,
                normalized=normalized,
                candidate_ids=candidate_ids,
                product_count=product_count,
                stock_count=stock_count,
                price_count=price_count,
            )

            out.append(
                {
                    "raw_brand": raw_brand,
                    "normalized_raw_brand": normalized,
                    "supplier_code": supplier_code,
                    "product_count": product_count,
                    "stock_gt_0_count": stock_count,
                    "product_price_count": price_count,
                    "sample_skus": sample_skus,
                    "sample_product_names": sample_names,
                    "possible_deterministic_supplier_candidate": candidate_str,
                    "likely_classification": likely_classification,
                    "recommended_action": recommended_action,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
        out.sort(key=lambda item: (-int(item["stock_gt_0_count"]), -int(item["product_count"]), item["raw_brand"]))
        return out

    def _build_shortlist(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tecdoc_only = [row for row in rows if row.get("likely_classification") == "tecdoc_likely"]
        top_product = sorted(tecdoc_only, key=lambda item: (-int(item["product_count"]), item["raw_brand"]))[:50]
        top_stock = sorted(tecdoc_only, key=lambda item: (-int(item["stock_gt_0_count"]), item["raw_brand"]))[:50]
        top_price = sorted(tecdoc_only, key=lambda item: (-int(item["product_price_count"]), item["raw_brand"]))[:50]

        keyed: dict[tuple[str, str], dict[str, Any]] = {}
        for bucket, data in (
            ("top_50_product_count", top_product),
            ("top_50_stock_gt_0_count", top_stock),
            ("top_50_product_price_count", top_price),
        ):
            for rank, row in enumerate(data, start=1):
                key = (str(row.get("supplier_code") or ""), str(row.get("raw_brand") or ""))
                if key not in keyed:
                    keyed[key] = dict(row)
                    keyed[key]["shortlist_buckets"] = bucket
                    keyed[key]["best_rank"] = rank
                else:
                    buckets = set(str(keyed[key].get("shortlist_buckets") or "").split("|"))
                    buckets.add(bucket)
                    keyed[key]["shortlist_buckets"] = "|".join(sorted(item for item in buckets if item))
                    keyed[key]["best_rank"] = min(int(keyed[key].get("best_rank") or rank), rank)
        shortlist = list(keyed.values())
        shortlist.sort(key=lambda item: (int(item.get("best_rank") or 9999), -int(item.get("stock_gt_0_count") or 0), item.get("raw_brand") or ""))
        return shortlist

    def _build_unsafe_ambiguous_review(self, coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in coverage_rows:
            if str(row.get("decision") or "") != "unsafe_ambiguous":
                continue
            raw_brand = str(row.get("raw_brand") or "")
            supplier_code = str(row.get("supplier_code") or "")
            resolution = self.resolver.resolve(raw_brand=raw_brand, supplier_code=supplier_code)
            candidates = list(resolution.candidates or [])
            names = [str(item.get("name") or "") for item in candidates]
            duplicate_names = len(names) != len(set(names))

            deterministic_dedupe = "no"
            if len(candidates) >= 2:
                top = int(candidates[0].get("nbrofarticles") or 0)
                nxt = int(candidates[1].get("nbrofarticles") or 0)
                if top > 0 and top >= (nxt * 2):
                    deterministic_dedupe = "possible"

            action = "manual approval"
            if duplicate_names:
                action = "manual supplier dedupe"
            elif deterministic_dedupe == "possible":
                action = "manual approval"
            elif normalize_brand(raw_brand) == "CTR":
                action = "split rule"
            else:
                action = "keep_blocked"

            out.append(
                {
                    "raw_brand": raw_brand,
                    "supplier_code": supplier_code,
                    "product_count": int(row.get("product_count") or 0),
                    "candidate_suppliers": "; ".join(
                        f"{item.get('supplier_id')}:{item.get('name')}({item.get('nbrofarticles')})" for item in candidates
                    ),
                    "why_ambiguous": resolution.reason or "multiple local candidates",
                    "duplicate_supplier_rows_exist": "yes" if duplicate_names else "no",
                    "deterministic_dedupe_possible": deterministic_dedupe,
                    "recommended_action": action,
                }
            )
        out.sort(key=lambda item: (-int(item["product_count"]), item["raw_brand"]))
        return out

    def _sample_products(self, *, raw_brand: str, supplier_code: str, limit: int = 5) -> tuple[str, str]:
        offers = (
            SupplierOffer.objects.select_related("product", "product__brand", "supplier")
            .filter(supplier__code=supplier_code)
            .filter(Q(product__display_brand_name=raw_brand) | Q(product__brand__name=raw_brand))
            .order_by("product__sku")
            [: max(1, int(limit))]
        )
        skus: list[str] = []
        names: list[str] = []
        for offer in offers:
            product = offer.product
            skus.append(str(product.svom_sku or product.sku or ""))
            names.append(str(product.name or ""))
        return ", ".join(skus), " | ".join(names)

    def _source_origin(self, *, raw_brand: str, supplier_code: str, sample_limit: int = 5) -> str:
        product_ids = list(
            SupplierOffer.objects.filter(supplier__code=supplier_code)
            .filter(Q(product__display_brand_name=raw_brand) | Q(product__brand__name=raw_brand))
            .values_list("product_id", flat=True)[:200]
        )
        if not product_ids:
            return ""
        rows = (
            SupplierRawOffer.objects.select_related("source", "run")
            .filter(supplier__code=supplier_code, matched_product_id__in=product_ids)
            .order_by("-updated_at")
            [: max(1, int(sample_limit))]
        )
        if not rows:
            return ""
        parts: list[str] = []
        for item in rows:
            parts.append(
                f"{item.source.code}:{item.source.parser_type}:run={item.run_id}:artifact={item.artifact_id or '-'}"
            )
        return "; ".join(parts)

    def _supplier_candidates_from_variants(
        self,
        raw_brand: str,
        suppliers: dict[int, dict[str, Any]],
        by_variant: dict[str, set[int]],
    ) -> set[int]:
        variants = self.normalizer.variants(raw_brand)
        candidate_ids: set[int] = set()
        for variant in variants:
            candidate_ids.update(by_variant.get(variant, set()))
        if candidate_ids:
            active = {sid for sid in candidate_ids if int(suppliers.get(sid, {}).get("nbrofarticles") or 0) > 0}
            if active:
                candidate_ids = active
        return candidate_ids

    def _candidate_str(self, candidate_ids: set[int], suppliers: dict[int, dict[str, Any]]) -> str:
        if not candidate_ids:
            return ""
        return "; ".join(
            f"{sid}:{suppliers.get(sid, {}).get('description', '')}({int(suppliers.get(sid, {}).get('nbrofarticles') or 0)})"
            for sid in sorted(candidate_ids)
        )

    def _recommended_status_for_blocked(self, *, raw_brand: str, normalized: str, candidate_ids: set[int]) -> str:
        raw_upper = str(raw_brand or "").strip().upper()
        if self._is_invalid_brand_value(raw_upper, normalized):
            return "invalid_brand_value"
        if normalized in {normalize_brand(item) for item in NON_TECDOC_BRAND_KEYS}:
            return "non_tecdoc"
        if candidate_ids:
            return "needs_human_approval"
        return "keep_unmapped_missing_supplier"

    def _classify_missing_row(
        self,
        *,
        raw_brand: str,
        normalized: str,
        candidate_ids: set[int],
        product_count: int,
        stock_count: int,
        price_count: int,
    ) -> tuple[str, str, str, str]:
        raw_upper = str(raw_brand or "").strip().upper()
        if self._is_invalid_brand_value(raw_upper, normalized):
            return "generic_or_invalid", "mark_invalid_brand_value", "0.99", "brand value appears invalid/placeholder"
        if normalized in {normalize_brand(item) for item in NON_TECDOC_BRAND_KEYS}:
            return "non_tecdoc_likely", "mark_non_tecdoc", "0.98", "brand falls into non-TecDoc keywords"
        if len(candidate_ids) == 1:
            return "tecdoc_likely", "add_alias_after_approval", "0.85", "single deterministic supplier candidate exists"
        if len(candidate_ids) > 1:
            return "unknown", "manual_research", "0.50", "multiple deterministic supplier candidates"
        if normalized and len(normalized) <= 2:
            return "private_label_or_supplier_brand", "manual_research", "0.70", "very short normalized brand key"
        if normalized and self._looks_like_tecdoc_brand(normalized):
            if stock_count > 0 or price_count > 0 or product_count >= 20:
                return "tecdoc_likely", "missing_local_supplier", "0.70", "brand token looks like TecDoc but absent in local suppliers"
            return "unknown", "keep_unmapped", "0.45", "insufficient signal for deterministic local mapping"
        return "unknown", "keep_unmapped", "0.40", "no deterministic supplier signal"

    def _is_invalid_brand_value(self, raw_upper: str, normalized: str) -> bool:
        if raw_upper in INVALID_BRAND_VALUES:
            return True
        if not normalized and raw_upper:
            if any(pattern.search(raw_upper) for pattern in INVALID_BRAND_PATTERNS):
                return True
            if any(token in raw_upper for token in ("УДАЛ", "DELET", "REMOV")):
                return True
            if raw_upper in {"УГОРЩИНА", "HUNGARY"}:
                return True
        return False

    def _looks_like_tecdoc_brand(self, normalized: str) -> bool:
        if not normalized:
            return False
        if normalized in {"AT", "OE", "OEM"}:
            return False
        return bool(re.match(r"^[A-Z0-9&+./ -]{3,}$", normalized))

    def _build_next_steps_summary(
        self,
        *,
        blocked_rows: list[dict[str, Any]],
        prioritized_rows: list[dict[str, Any]],
        unsafe_rows: list[dict[str, Any]],
        coverage_rows: list[dict[str, Any]],
    ) -> str:
        decision_counts = Counter(str(row.get("decision") or "") for row in coverage_rows)
        likely_tecdoc = [row for row in prioritized_rows if row.get("likely_classification") == "tecdoc_likely"]
        likely_tecdoc_top = sorted(likely_tecdoc, key=lambda item: (-int(item.get("stock_gt_0_count") or 0), -int(item.get("product_count") or 0)))[:15]

        lines = [
            "# Auto_DB Service Brand Gap Next Steps Summary",
            "",
            f"1. blocked needs_alias rows analyzed: {len(blocked_rows)}",
            "2. blocked rows recommendation:",
        ]
        for row in blocked_rows:
            lines.append(
                f"   - {row.get('supplier_code')} / {row.get('raw_brand')}: {row.get('recommended_reclassification')} ({row.get('why_service_classified_as_needs_alias')})"
            )
        lines.extend(
            [
                f"3. remaining missing supplier rows: {decision_counts.get('keep_unmapped_missing_supplier', 0)}",
                "4. top high-impact likely TecDoc gaps:",
            ]
        )
        for row in likely_tecdoc_top:
            lines.append(
                f"   - {row.get('raw_brand')} [{row.get('supplier_code')}] products={row.get('product_count')} stock_gt_0={row.get('stock_gt_0_count')} action={row.get('recommended_action')}"
            )
        lines.extend(
            [
                f"5. unsafe ambiguous rows: {len(unsafe_rows)}",
                "6. recommended next step: review shortlist + approval sheet, then apply only manually approved aliases through service command.",
                "",
            ]
        )
        return "\n".join(lines)

    def _integrity_snapshot(self) -> dict[str, Any]:
        return {
            "product_count": Product.objects.count(),
            "supplieroffer_count": SupplierOffer.objects.count(),
            "productprice_count": ProductPrice.objects.count(),
            "productattribute_count": ProductAttribute.objects.count(),
            "productfitment_count": ProductFitment.objects.count(),
            "productimage_count": ProductImage.objects.count(),
            "linked_by_key_count": Product.objects.exclude(autodb_article_key="").count(),
            "quality_trusted_count": AutoDbProductLinkQuality.objects.filter(status="trusted").count(),
            "autodb_supplier_brand_alias_count": AutoDbSupplierBrandAlias.objects.count(),
            "sum_supplier_stock_qty": SupplierOffer.objects.aggregate(v=Sum("stock_qty"))["v"] or 0,
            "sum_supplier_purchase_price": SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"] or 0,
            "sum_productprice_final_price": ProductPrice.objects.aggregate(v=Sum("final_price"))["v"] or 0,
            "utr_api_calls": 0,
        }

    def _integrity_rows(self, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            b = before.get(key)
            a = after.get(key)
            delta: Any = ""
            try:
                delta = (a or 0) - (b or 0)
            except Exception:
                delta = ""
            rows.append({"metric": key, "before": b, "after": a, "delta": delta, "changed": b != a})
        return rows

    def _export_blocked_needs_alias(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_blocked_needs_alias_analysis",
            run_id=None,
            rows=rows,
            title="Service blocked needs_alias rows analysis",
            summary={"rows": len(rows)},
            export_prefix="/tmp/autodb_service_blocked_needs_alias_analysis",
        )

    def _export_blocked_decision_dry_run(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_blocked_needs_alias_decision_dry_run",
            run_id=None,
            rows=rows,
            title="Service blocked needs_alias decision dry-run",
            summary={"rows": len(rows), "apply_mode": "staging_only_no_persistent_decision_layer"},
            export_prefix="/tmp/autodb_service_blocked_needs_alias_decision_dry_run",
        )

    def _export_missing_prioritized(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_remaining_414_missing_prioritized",
            run_id=None,
            rows=rows,
            title="Service remaining missing supplier prioritized review",
            summary={
                "rows": len(rows),
                "likely_classification": dict(Counter(str(item.get("likely_classification") or "") for item in rows)),
                "recommended_action": dict(Counter(str(item.get("recommended_action") or "") for item in rows)),
            },
            export_prefix="/tmp/autodb_service_remaining_414_missing_prioritized",
        )
        self._write_xlsx(Path("/tmp/autodb_service_remaining_414_missing_prioritized.xlsx"), rows)

    def _export_shortlist(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_remaining_brand_gap_shortlist",
            run_id=None,
            rows=rows,
            title="Service remaining brand gap shortlist",
            summary={"rows": len(rows)},
            export_prefix="/tmp/autodb_service_remaining_brand_gap_shortlist",
        )
        self._write_xlsx(Path("/tmp/autodb_service_remaining_brand_gap_shortlist.xlsx"), rows)

    def _export_unsafe_review(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_unsafe_ambiguous_2_review",
            run_id=None,
            rows=rows,
            title="Service unsafe ambiguous review",
            summary={"rows": len(rows)},
            export_prefix="/tmp/autodb_service_unsafe_ambiguous_2_review",
        )

    def _export_integrity(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="autodb_service_brand_gap_analysis_integrity",
            run_id=None,
            rows=rows,
            title="Service brand gap analysis integrity",
            summary={"rows": len(rows), "utr_api_calls": 0},
            export_prefix="/tmp/autodb_service_brand_gap_analysis_integrity",
        )

    def _write_xlsx(self, path: Path, rows: list[dict[str, Any]]) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "report"
        headers = list(rows[0].keys()) if rows else ["result"]
        ws.append(headers)
        for row in rows:
            ws.append([self._stringify(row.get(header)) for header in headers])
        wb.save(path)

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple, set)):
            return repr(value)
        return str(value)

    def export_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        headers = list(rows[0].keys()) if rows else ["result"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({header: self._stringify(row.get(header)) for header in headers})
