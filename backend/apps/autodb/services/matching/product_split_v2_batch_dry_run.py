from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.db.models import Sum
from openpyxl import Workbook

from apps.autodb.services.matching.product_split_v2_planner import AutoDbProductSplitV2Planner
from apps.autodb.services.matching.reports import write_report
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


GROUP_RE = re.compile(r"^\s*(?P<group>.+?)\[(?P<count>\d+)\]:(?P<offer_ids>.+?)\s*$")


@dataclass(frozen=True)
class SplitGroup:
    raw: str
    label: str
    brand_norm: str
    article_canonical: str
    count: int
    offer_ids: tuple[str, ...]


class AutoDbProductSplitV2BatchDryRunService:
    def __init__(self):
        self.planner = AutoDbProductSplitV2Planner()
        self.out = Path("/tmp")
        self.split_candidates_path = Path("/tmp/product_quality_split_candidates_dry_run.csv")
        self.bucket_path = Path("/tmp/product_quality_multioffer_correction_buckets.csv")
        self.blocked_matching_path = Path("/tmp/autodb_service_multioffer_blocked_matching_review.csv")

    def run(self, *, max_candidates: int = 20, prefer_top: int = 10) -> dict[str, Any]:
        before = self._integrity_snapshot()
        bucket_map = self._load_bucket_map()
        blocked_map = self._load_blocked_map()
        source_rows = self._load_csv(self.split_candidates_path)

        selection_rows, selected = self._build_selection(
            source_rows=source_rows,
            bucket_map=bucket_map,
            blocked_map=blocked_map,
            max_candidates=max(1, int(max_candidates or 20)),
        )
        self._export_selection(
            selected_rows=selected,
            all_rows=selection_rows,
        )

        dry_rows = self._run_planner_dry(selected, prefer_top=max(1, int(prefer_top or 10)))
        self._export_dry_run(dry_rows)

        readiness = self._build_readiness(selection_rows=selection_rows, dry_rows=dry_rows)
        self._export_readiness(readiness)

        approval_rows = self._build_approval_rows(dry_rows)
        self._export_approval(approval_rows=approval_rows, readiness=readiness)

        after = self._integrity_snapshot()
        integrity_rows = self._integrity_rows(before=before, after=after)
        self._export_integrity(integrity_rows)

        self._export_final_report(readiness=readiness, clean_rows=approval_rows)
        return {
            "selection_rows": selection_rows,
            "selected_rows": selected,
            "dry_rows": dry_rows,
            "readiness": readiness,
            "approval_rows": approval_rows,
        }

    def _load_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def _load_bucket_map(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in self._load_csv(self.bucket_path):
            product_id = str(row.get("product_id") or "").strip()
            if not product_id:
                continue
            out[product_id] = row
        return out

    def _load_blocked_map(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = defaultdict(dict)
        for row in self._load_csv(self.blocked_matching_path):
            product_id = str(row.get("product_id") or "").strip()
            if not product_id:
                continue
            flags = out.setdefault(product_id, {})
            for key in (
                "supplier_code_conflict_gpl_utr",
                "price_ratio_extreme",
                "split_product_candidate",
                "trusted_link_conflict",
                "brand_conflict_between_offers",
                "article_conflict_between_offers",
            ):
                if self._as_bool(row.get(key)):
                    flags[key] = True
        return out

    def _build_selection(
        self,
        *,
        source_rows: list[dict[str, str]],
        bucket_map: dict[str, dict[str, Any]],
        blocked_map: dict[str, dict[str, Any]],
        max_candidates: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        ranked: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        audit_rows: list[dict[str, Any]] = []
        for row in source_rows:
            product_id = str(row.get("product_id") or "").strip()
            sku = str(row.get("SKU") or "").strip()
            recommended_action = str(row.get("recommended_action") or "").strip()
            if recommended_action not in {"split_product_candidate", "split_product_after_manual_review"}:
                continue

            groups = self._parse_groups(str(row.get("proposed_split_groups") or ""))
            if len(groups) < 2:
                audit_rows.append(
                    {
                        "product_id": product_id,
                        "original_sku": sku,
                        "decision": "blocked",
                        "blocker": "invalid_or_single_group",
                        "recommended_action": recommended_action,
                    }
                )
                continue
            if not self._is_obvious_group_shape(groups):
                audit_rows.append(
                    {
                        "product_id": product_id,
                        "original_sku": sku,
                        "decision": "blocked",
                        "blocker": "group_shape_not_obvious",
                        "recommended_action": recommended_action,
                    }
                )
                continue

            product = Product.objects.filter(id=product_id).select_related("brand").first()
            if product is None:
                audit_rows.append(
                    {
                        "product_id": product_id,
                        "original_sku": sku,
                        "decision": "blocked",
                        "blocker": "product_not_found",
                        "recommended_action": recommended_action,
                    }
                )
                continue
            blockers: list[str] = []
            if "SPLIT" in str(product.sku or "").upper():
                blockers.append("already_split_sku")
            if bool(product.brand_manually_locked):
                blockers.append("brand_manually_locked")
            trusted_conflict = self._has_trusted_link(product)
            if trusted_conflict:
                blockers.append("trusted_link_conflict")
            attr_count = ProductAttribute.objects.filter(product=product).count()
            fitment_count = ProductFitment.objects.filter(product=product).count()
            image_count = ProductImage.objects.filter(product=product).count()

            keep_group, move_group = self._pick_groups(
                groups=groups,
                product=product,
                bucket_row=bucket_map.get(product_id) or {},
            )
            if keep_group is None or move_group is None:
                blockers.append("failed_group_selection")
            else:
                present_offer_ids = {
                    str(item)
                    for item in SupplierOffer.objects.filter(product=product, id__in=move_group.offer_ids).values_list("id", flat=True)
                }
                missing_offers = set(move_group.offer_ids) - set(
                    present_offer_ids
                )
                if missing_offers:
                    blockers.append("moved_offer_ids_not_on_product")

            parsed_blockers = str(row.get("safety_blockers") or "").strip()
            if parsed_blockers:
                blockers.append(f"source_safety_blockers:{parsed_blockers}")

            quality_flags = blocked_map.get(product_id, {})
            price_ratio = self._as_float(row.get("price_ratio"))
            priority_key = (
                0 if quality_flags.get("price_ratio_extreme") else 1,
                0 if quality_flags.get("brand_conflict_between_offers") else 1,
                0 if self._clear_grouping(groups) else 1,
                0 if quality_flags.get("supplier_code_conflict_gpl_utr") else 1,
                len(move_group.offer_ids) if move_group else 999,
                int(row.get("offer_count") or 0),
                -price_ratio,
            )

            decision = "selected_candidate" if not blockers else "blocked"
            output = {
                "product_id": product_id,
                "original_sku": str(product.svom_sku or product.sku or sku),
                "product_sku_internal": str(product.sku or ""),
                "product_name": str(product.name or ""),
                "current_brand": str(getattr(product.brand, "name", "") or ""),
                "current_display_brand": str(product.display_brand_name or ""),
                "recommended_action": recommended_action,
                "confidence": str(row.get("confidence") or ""),
                "price_ratio": f"{price_ratio:.4f}" if price_ratio else "",
                "offer_count": int(row.get("offer_count") or 0),
                "group_count": len(groups),
                "keep_group": keep_group.raw if keep_group else "",
                "move_group": move_group.raw if move_group else "",
                "supplier_offer_ids_to_move": ",".join(move_group.offer_ids) if move_group else "",
                "trusted_link_conflict": trusted_conflict,
                "gpl_utr_conflict": bool(quality_flags.get("supplier_code_conflict_gpl_utr")),
                "price_ratio_extreme": bool(quality_flags.get("price_ratio_extreme")),
                "productattribute_count": attr_count,
                "productfitment_count": fitment_count,
                "productimage_count": image_count,
                "decision": decision,
                "blockers": ";".join(sorted(set(blockers))),
            }
            audit_rows.append(output)
            if decision == "selected_candidate":
                ranked.append((priority_key, output))

        ranked.sort(key=lambda item: item[0])
        selected = [row for _, row in ranked[:max_candidates]]
        selected_ids = {row["product_id"] for row in selected}
        for row in audit_rows:
            if row.get("decision") == "selected_candidate" and row.get("product_id") not in selected_ids:
                row["decision"] = "not_selected_by_limit"
                row["blockers"] = "batch_limit"
        return audit_rows, selected

    def _run_planner_dry(self, selected_rows: list[dict[str, Any]], *, prefer_top: int) -> list[dict[str, Any]]:
        dry_rows: list[dict[str, Any]] = []
        for selected in selected_rows:
            plan = self.planner.plan(
                sku=str(selected.get("original_sku") or ""),
                source_product_id=str(selected.get("product_id") or ""),
                moved_offer_ids=self._split_ids(str(selected.get("supplier_offer_ids_to_move") or "")),
                keep_group=str(selected.get("keep_group") or ""),
                move_group=str(selected.get("move_group") or ""),
            )
            source = Product.objects.filter(id=str(selected.get("product_id") or "")).first()
            visibility = self.planner.preview_visibility(source_product=source, plan=plan) if source else {}
            row = {
                "product_id": str(selected.get("product_id") or ""),
                "original_sku": str(selected.get("original_sku") or ""),
                "current_brand_display": f"{selected.get('current_brand','')} / {selected.get('current_display_brand','')}",
                "keep_group": plan.keep_group,
                "move_group": plan.move_group,
                "supplier_offer_ids_to_move": ",".join(plan.offers_to_move),
                "supplier_raw_offer_ids_to_move": ",".join(plan.raw_offers_to_move),
                "proposed_new_internal_sku": plan.proposed_internal_sku,
                "proposed_new_public_sku_strategy": plan.proposed_public_sku_strategy,
                "proposed_original_brand_after_split": f"{plan.source_brand_after} / {plan.source_display_brand_after}",
                "proposed_new_brand_after_split": f"{plan.new_brand_after} / {plan.new_display_brand_after}",
                "productprice_plan": plan.productprice_strategy,
                "productprice_actions": ";".join(plan.productprice_actions),
                "warehouse_source_split_plan": f"offers:{','.join(plan.expected_original_supplier_codes_after)} || {','.join(plan.expected_new_supplier_codes_after)}",
                "admin_visibility_expected": str(visibility),
                "rollback_plan_exists": bool(plan.rollback_steps),
                "clean": bool(plan.clean),
                "blockers": ";".join(plan.blockers),
                "price_ratio_extreme": selected.get("price_ratio_extreme"),
                "gpl_utr_conflict": selected.get("gpl_utr_conflict"),
            }
            dry_rows.append(row)

        clean_count = sum(1 for row in dry_rows if bool(row.get("clean")))
        if clean_count < max(1, (len(dry_rows) // 2)) and len(dry_rows) > prefer_top:
            dry_rows = dry_rows[:prefer_top]
        return dry_rows

    def _build_readiness(self, *, selection_rows: list[dict[str, Any]], dry_rows: list[dict[str, Any]]) -> dict[str, Any]:
        selected_for_batch = [row for row in selection_rows if row.get("decision") == "selected_candidate"]
        planned = dry_rows
        clean = [row for row in planned if bool(row.get("clean"))]
        blocked_after_plan = [row for row in planned if not bool(row.get("clean"))]

        blocker_counter = Counter()
        mapped = {
            "unknown_safe_sku_strategy": "sku_strategy_blocker",
            "raw_offer_relation_ambiguous": "raw_offer_ambiguous",
            "ambiguous_productprice_relation": "productprice_ambiguous",
            "productprice_relation_ambiguous_existing_split_product": "productprice_ambiguous",
            "trusted_link_conflict": "trusted_link_conflict",
            "existing_inactive_split_product_cleanup_needed": "existing_orphan_artifact",
            "brand_display_conflict_unresolved_new_autodb_supplier": "brand_display_conflict",
            "price_stock_plan_not_safe": "price_stock_plan_blocker",
        }
        for row in blocked_after_plan:
            raw = self._split_tags(str(row.get("blockers") or ""))
            for item in raw:
                blocker_counter[mapped.get(item, item)] += 1

        recommended_apply_size = min(len(clean), 10 if len(blocked_after_plan) > len(clean) else 20)
        return {
            "input_candidates": len(selection_rows),
            "selected_candidates": len(selected_for_batch),
            "dry_run_checked": len(planned),
            "deferred_due_mixed_quality": max(0, len(selected_for_batch) - len(planned)),
            "clean_candidates": len(clean),
            "blocked_candidates": len(blocked_after_plan),
            "blockers_by_type": dict(blocker_counter),
            "recommended_apply_batch_size": recommended_apply_size,
            "top_blockers": blocker_counter.most_common(8),
        }

    def _build_approval_rows(self, dry_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in dry_rows:
            if not bool(row.get("clean")):
                continue
            move_offer_ids = self._split_ids(str(row.get("supplier_offer_ids_to_move") or ""))
            move_raw_ids = self._split_ids(str(row.get("supplier_raw_offer_ids_to_move") or ""))
            rows.append(
                {
                    "product_id": row.get("product_id") or "",
                    "original_sku": row.get("original_sku") or "",
                    "proposed_new_internal_sku": row.get("proposed_new_internal_sku") or "",
                    "proposed_new_public_sku_strategy": row.get("proposed_new_public_sku_strategy") or "",
                    "keep_group": row.get("keep_group") or "",
                    "move_group": row.get("move_group") or "",
                    "offer_ids_to_move": ",".join(move_offer_ids),
                    "raw_offer_ids_to_move": ",".join(move_raw_ids),
                    "productprice_handling": row.get("productprice_plan") or "",
                    "expected_product_count_delta": 1,
                    "expected_productprice_count_delta": 0,
                    "expected_unchanged_metrics": "price_stock_sums,links,attributes,fitments,images",
                    "rollback_note": "move offers/raw offers back, restore source brand fields, deactivate new product, rerun reprice",
                    "user_approval": "",
                    "user_notes": "",
                }
            )
        return rows

    def _export_selection(self, *, selected_rows: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> None:
        summary = {
            "source_rows": len(all_rows),
            "selected_candidates": len(selected_rows),
            "blocked_rows": sum(1 for row in all_rows if row.get("decision") == "blocked"),
            "not_selected_by_limit": sum(1 for row in all_rows if row.get("decision") == "not_selected_by_limit"),
        }
        write_report(
            command_name="product_quality_split_v2_batch_candidates",
            run_id=None,
            rows=selected_rows,
            title="Product quality split v2 batch candidates",
            summary=summary,
            export_prefix="/tmp/product_quality_split_v2_batch_candidates",
        )

    def _export_dry_run(self, rows: list[dict[str, Any]]) -> None:
        summary = {
            "checked": len(rows),
            "clean": sum(1 for row in rows if bool(row.get("clean"))),
            "blocked": sum(1 for row in rows if not bool(row.get("clean"))),
        }
        write_report(
            command_name="product_quality_split_v2_batch_dry_run",
            run_id=None,
            rows=rows,
            title="Product quality split v2 batch dry-run",
            summary=summary,
            export_prefix="/tmp/product_quality_split_v2_batch_dry_run",
        )

    def _export_readiness(self, readiness: dict[str, Any]) -> None:
        lines = [
            "# Product quality split v2 batch readiness summary",
            "",
            f"- input_candidates: {readiness.get('input_candidates', 0)}",
            f"- selected_candidates: {readiness.get('selected_candidates', 0)}",
            f"- clean_candidates: {readiness.get('clean_candidates', 0)}",
            f"- blocked_candidates: {readiness.get('blocked_candidates', 0)}",
            f"- blockers_by_type: {readiness.get('blockers_by_type', {})}",
            f"- top_blockers: {readiness.get('top_blockers', [])}",
            f"- recommended_apply_batch_size: {readiness.get('recommended_apply_batch_size', 0)}",
            "",
        ]
        (self.out / "product_quality_split_v2_batch_readiness_summary.md").write_text("\n".join(lines), encoding="utf-8")

    def _export_approval(self, *, approval_rows: list[dict[str, Any]], readiness: dict[str, Any]) -> None:
        csv_path = self.out / "product_quality_split_v2_batch_apply_approval.csv"
        md_path = self.out / "product_quality_split_v2_batch_apply_approval.md"
        headers = [
            "product_id",
            "original_sku",
            "proposed_new_internal_sku",
            "proposed_new_public_sku_strategy",
            "keep_group",
            "move_group",
            "offer_ids_to_move",
            "raw_offer_ids_to_move",
            "productprice_handling",
            "expected_product_count_delta",
            "expected_productprice_count_delta",
            "expected_unchanged_metrics",
            "rollback_note",
            "user_approval",
            "user_notes",
        ]
        self._write_csv_with_headers(csv_path, headers=headers, rows=approval_rows)

        wb = Workbook()
        ws = wb.active
        ws.title = "approval"
        ws.append(headers)
        for row in approval_rows:
            ws.append([row.get(header, "") for header in headers])
        wb.save("/tmp/product_quality_split_v2_batch_apply_approval.xlsx")

        lines = [
            "# Product quality split v2 batch apply approval package",
            "",
            f"- CSV: `{csv_path}`",
            f"- Rows: {len(approval_rows)}",
            f"- clean_rows: {len(approval_rows)}",
            f"- expected_product_delta_total: {len(approval_rows)}",
            "- expected_productprice_delta_total: 0",
            f"- recommended_apply_batch_size: {readiness.get('recommended_apply_batch_size', 0)}",
            "",
        ]
        md_path.write_text("\n".join(lines), encoding="utf-8")

    def _export_integrity(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="product_quality_split_v2_batch_dry_run_integrity",
            run_id=None,
            rows=rows,
            title="Product quality split v2 batch dry-run integrity",
            summary={"utr_api_calls": 0, "writes_expected": 0},
            export_prefix="/tmp/product_quality_split_v2_batch_dry_run_integrity",
        )

    def _export_final_report(self, *, readiness: dict[str, Any], clean_rows: list[dict[str, Any]]) -> None:
        lines = [
            "# Product quality split v2 batch dry-run final report",
            "",
            f"1. Batch candidates selected: {readiness.get('selected_candidates', 0)}",
            f"2. Clean dry-run count: {readiness.get('clean_candidates', 0)}",
            f"3. Blocked count: {readiness.get('blocked_candidates', 0)}",
            f"4. Top blockers: {readiness.get('top_blockers', [])}",
            f"5. Recommended first apply batch size: {readiness.get('recommended_apply_batch_size', 0)}",
            "6. Approval package path: /tmp/product_quality_split_v2_batch_apply_approval.csv + .xlsx + .md",
            "7. Confirmation no writes: yes (dry-run only)",
            "",
        ]
        (self.out / "product_quality_split_v2_batch_dry_run_final_report.md").write_text("\n".join(lines), encoding="utf-8")

    def _parse_groups(self, raw: str) -> list[SplitGroup]:
        groups: list[SplitGroup] = []
        for chunk in [item.strip() for item in str(raw or "").split(";") if item.strip()]:
            match = GROUP_RE.match(chunk)
            if not match:
                continue
            label = str(match.group("group") or "").strip()
            offer_ids = tuple(sorted({item.strip() for item in str(match.group("offer_ids") or "").split(",") if item.strip()}))
            if "|" in label:
                brand, article = label.split("|", 1)
            else:
                brand, article = label, ""
            groups.append(
                SplitGroup(
                    raw=chunk,
                    label=label,
                    brand_norm=normalize_brand(str(brand or "")),
                    article_canonical=self._canonical_article(article),
                    count=int(match.group("count") or 0),
                    offer_ids=offer_ids,
                )
            )
        return groups

    def _pick_groups(self, *, groups: list[SplitGroup], product: Product, bucket_row: dict[str, Any]) -> tuple[SplitGroup | None, SplitGroup | None]:
        if not groups:
            return None, None
        sorted_groups = sorted(groups, key=lambda item: (item.count, len(item.offer_ids)), reverse=True)
        keep = sorted_groups[0]
        move = sorted_groups[-1]

        dominant_brand = normalize_brand(str(bucket_row.get("dominant_brand_norm") or ""))
        dominant_article = self._canonical_article(str(bucket_row.get("dominant_article_canonical") or ""))
        if dominant_brand:
            matched = [item for item in groups if item.brand_norm == dominant_brand]
            if dominant_article:
                matched = [item for item in matched if item.article_canonical == dominant_article] or matched
            if len(matched) == 1:
                keep = matched[0]
                remainder = [item for item in groups if item != keep]
                if remainder:
                    move = sorted(remainder, key=lambda item: (item.count, len(item.offer_ids)))[0]

        outlier_ids = self._split_ids(str(bucket_row.get("outlier_offer_ids") or ""))
        if outlier_ids:
            outlier_set = set(outlier_ids)
            ranked = sorted(
                groups,
                key=lambda item: len(outlier_set.intersection(set(item.offer_ids))),
                reverse=True,
            )
            if ranked and len(outlier_set.intersection(set(ranked[0].offer_ids))) > 0:
                move = ranked[0]
                remainder = [item for item in groups if item != move]
                if remainder:
                    keep = sorted(remainder, key=lambda item: (item.count, len(item.offer_ids)), reverse=True)[0]

        if keep == move:
            return None, None
        return keep, move

    def _is_obvious_group_shape(self, groups: list[SplitGroup]) -> bool:
        if len(groups) == 2:
            return True
        counts = sorted((item.count for item in groups), reverse=True)
        return bool(counts and counts[0] >= 2 and all(item == 1 for item in counts[1:]))

    def _clear_grouping(self, groups: list[SplitGroup]) -> bool:
        return all(bool(item.brand_norm and item.article_canonical and item.offer_ids) for item in groups)

    def _has_trusted_link(self, product: Product) -> bool:
        if str(product.autodb_article_key or "").strip():
            return True
        return AutoDbProductLinkQuality.objects.filter(
            product=product,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()

    def _integrity_snapshot(self) -> dict[str, Any]:
        return {
            "product_count": Product.objects.count(),
            "supplieroffer_count": SupplierOffer.objects.count(),
            "supplierrawoffer_count": SupplierRawOffer.objects.count(),
            "productprice_count": ProductPrice.objects.count(),
            "productattribute_count": ProductAttribute.objects.count(),
            "productfitment_count": ProductFitment.objects.count(),
            "productimage_count": ProductImage.objects.count(),
            "linked_by_key_count": Product.objects.exclude(autodb_article_key="").count(),
            "quality_trusted_count": AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_TRUSTED).count(),
            "sum_supplier_stock_qty": SupplierOffer.objects.aggregate(v=Sum("stock_qty"))["v"] or 0,
            "sum_supplier_purchase_price": SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"] or 0,
            "sum_productprice_final_price": ProductPrice.objects.aggregate(v=Sum("final_price"))["v"] or 0,
            "utr_api_calls": 0,
        }

    def _integrity_rows(self, *, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
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

    def _split_tags(self, value: str) -> list[str]:
        return [item.strip() for item in str(value or "").split(";") if item.strip()]

    def _split_ids(self, value: str) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    def _canonical_article(self, value: str) -> str:
        return "".join(ch for ch in str(value or "").upper() if ch.isalnum())

    def _as_bool(self, value: Any) -> bool:
        token = str(value or "").strip().lower()
        return token in {"1", "true", "yes", "y", "on"}

    def _as_float(self, value: Any) -> float:
        try:
            return float(str(value or "").strip() or "0")
        except Exception:
            return 0.0

    def _write_csv_with_headers(self, path: Path, *, headers: list[str], rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({header: row.get(header, "") for header in headers})
