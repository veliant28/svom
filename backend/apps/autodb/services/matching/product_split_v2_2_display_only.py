from __future__ import annotations

import csv
import ast
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db import connections
from django.db.models import Sum
from openpyxl import Workbook

from apps.autodb.services.matching.deterministic_brand_binding import DeterministicBrandNormalizer
from apps.autodb.services.matching.product_split_v2_planner import AutoDbProductSplitV2Planner
from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class DisplayOnlyCandidate:
    product_id: str
    original_sku: str
    keep_group: str
    move_group: str
    move_brand: str
    move_brand_norm: str
    supplier_code: str
    moved_offer_ids: tuple[str, ...]


@dataclass(frozen=True)
class DisplayOnlyPlan:
    product_id: str
    original_sku: str
    keep_group: str
    move_group: str
    move_brand: str
    move_brand_norm: str
    supplier_code: str
    supplier_candidate_classification: str
    clean_display_only: bool
    blockers: tuple[str, ...]
    proposed_original_brand: str
    proposed_original_display_brand: str
    proposed_original_autodb_supplier_id: int | None
    proposed_new_brand: str
    proposed_new_display_brand: str
    proposed_new_autodb_supplier_id: int | None
    proposed_new_autodb_supplier_name: str
    proposed_new_brand_source: str
    moved_offer_ids: tuple[str, ...]
    moved_raw_offer_ids: tuple[str, ...]
    productprice_plan: str
    productprice_basis_status: str
    queue_state_after_split: str
    rollback_plan: tuple[str, ...]
    strict_v21_blockers_snapshot: tuple[str, ...]


class AutoDbProductSplitV22DisplayOnlyPlanner:
    def __init__(self):
        self.strict = AutoDbProductSplitV2Planner()
        self.normalizer = DeterministicBrandNormalizer()
        self._supplier_variant_index, self._supplier_exact_index = self._load_supplier_indexes()

    def plan(self, candidate: DisplayOnlyCandidate, *, allow_exact_supplier_display_only: bool = False) -> DisplayOnlyPlan:
        strict = self.strict.plan(
            sku=candidate.original_sku,
            source_product_id=candidate.product_id,
            moved_offer_ids=list(candidate.moved_offer_ids),
            keep_group=candidate.keep_group,
            move_group=candidate.move_group,
        )
        source = Product.objects.select_related("brand").filter(id=candidate.product_id).first()

        blockers = set(strict.blockers)

        # display-only mode allows unresolved moved-group AutoDB supplier for new product
        blockers.discard("brand_display_conflict_unresolved_new_autodb_supplier")

        if source is None:
            blockers.add("source_product_not_found")

        move_brand_norm = candidate.move_brand_norm or normalize_brand(candidate.move_brand)
        if not move_brand_norm:
            blockers.add("display_only_invalid_move_brand")

        # route exact supplier matches through strict supplier binding path by default
        supplier_cls = self._classify_supplier(move_brand_norm)
        if supplier_cls == "exact_supplier_candidate" and not allow_exact_supplier_display_only:
            blockers.add("exact_supplier_requires_strict_binding_path")

        if supplier_cls == "invalid_brand_value":
            blockers.add("display_only_invalid_move_brand")

        # deterministic article and grouping checks
        if not strict.move_article_canonical:
            blockers.add("display_only_move_article_not_deterministic")
        if not strict.offers_to_move:
            blockers.add("display_only_missing_moved_offer_ids")
        if not strict.raw_offers_to_move:
            blockers.add("display_only_missing_moved_raw_offer_ids")

        # strict parser may keep move_brand_not_resolved if no catalog brand exists.
        # display-only still requires deterministic catalog/display brand value for later apply.
        if "move_brand_not_resolved" in blockers:
            blockers.add("display_only_move_brand_catalog_unresolved")

        # dependencies/trust safety gates
        if source is not None:
            if self._has_trusted_link(source):
                blockers.add("trusted_link_conflict")
            if ProductAttribute.objects.filter(product=source).exists():
                blockers.add("productattribute_dependency_block")
            if ProductFitment.objects.filter(product=source).exists():
                blockers.add("productfitment_dependency_block")
            if ProductImage.objects.filter(product=source).exists():
                blockers.add("productimage_dependency_block")

        # product price basis must be explicit/non-ambiguous
        pp_rows = list(ProductPrice.objects.filter(product_id=candidate.product_id).only("id", "purchase_price"))
        keep_offers = list(SupplierOffer.objects.filter(id__in=list(strict.offers_to_keep)).only("id", "purchase_price"))
        move_offers = list(SupplierOffer.objects.filter(id__in=list(strict.offers_to_move)).only("id", "purchase_price"))
        productprice_basis_status = "explicit"
        if len(pp_rows) > 1 or len(keep_offers) != 1 or len(move_offers) != 1:
            blockers.add("productprice_basis_ambiguous")
            productprice_basis_status = "ambiguous"

        # if original brand cannot be safely recalculated from keep group, block
        if "keep_brand_not_resolved" in blockers:
            blockers.add("display_only_source_brand_recalc_unresolved")

        # ensure proposed sku strategy does not leak SPLIT
        if "SPLIT" in str(strict.proposed_internal_sku or "").upper():
            blockers.add("visible_split_sku_not_allowed")

        if not strict.rollback_steps:
            blockers.add("rollback_plan_missing")

        clean = len(blockers) == 0
        return DisplayOnlyPlan(
            product_id=candidate.product_id,
            original_sku=candidate.original_sku,
            keep_group=candidate.keep_group,
            move_group=candidate.move_group,
            move_brand=candidate.move_brand,
            move_brand_norm=move_brand_norm,
            supplier_code=candidate.supplier_code,
            supplier_candidate_classification=supplier_cls,
            clean_display_only=clean,
            blockers=tuple(sorted(blockers)),
            proposed_original_brand=str(strict.source_brand_after or ""),
            proposed_original_display_brand=str(strict.source_display_brand_after or ""),
            proposed_original_autodb_supplier_id=strict.source_autodb_supplier_id_after,
            proposed_new_brand=str(strict.new_brand_after or candidate.move_brand),
            proposed_new_display_brand=str(strict.new_display_brand_after or candidate.move_brand),
            proposed_new_autodb_supplier_id=None,
            proposed_new_autodb_supplier_name="",
            proposed_new_brand_source="split_offer_brand",
            moved_offer_ids=strict.offers_to_move,
            moved_raw_offer_ids=strict.raw_offers_to_move,
            productprice_plan="source_reprice_from_keep;new_reprice_from_move;no_price_value_edit",
            productprice_basis_status=productprice_basis_status,
            queue_state_after_split="new_product_autodb_matching_excluded_unresolved_supplier",
            rollback_plan=strict.rollback_steps,
            strict_v21_blockers_snapshot=tuple(sorted(set(strict.blockers))),
        )

    def _load_supplier_indexes(self) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
        variant_index: dict[str, set[int]] = defaultdict(set)
        exact_index: dict[str, set[int]] = defaultdict(set)
        try:
            with connections["auto_db_pro"].cursor() as cursor:
                cursor.execute("SELECT id, description, COALESCE(matchcode, '') FROM suppliers")
                rows = cursor.fetchall()
        except Exception:
            return variant_index, exact_index

        for sid, desc, matchcode in rows:
            try:
                supplier_id = int(sid)
            except Exception:
                continue
            name = str(desc or "").strip()
            code = str(matchcode or "").strip()
            if not name:
                continue
            n_name = normalize_brand(name)
            n_code = normalize_brand(code)
            if n_name:
                exact_index[n_name].add(supplier_id)
            if n_code:
                exact_index[n_code].add(supplier_id)
            for variant in self.normalizer.variants(name):
                variant_index[variant].add(supplier_id)
            for variant in self.normalizer.variants(code):
                variant_index[variant].add(supplier_id)
        return variant_index, exact_index

    def _classify_supplier(self, move_brand_norm: str) -> str:
        if not move_brand_norm:
            return "invalid_brand_value"
        exact = self._supplier_exact_index.get(move_brand_norm, set())
        if len(exact) == 1:
            return "exact_supplier_candidate"
        if len(exact) > 1:
            return "ambiguous_supplier_candidate"
        variants = self._supplier_variant_index.get(move_brand_norm, set())
        if len(variants) == 1:
            return "clean_alias_candidate"
        if len(variants) > 1:
            return "ambiguous_supplier_candidate"
        return "no_supplier_candidate"

    def _has_trusted_link(self, product: Product) -> bool:
        if str(product.autodb_article_key or "").strip():
            return True
        return AutoDbProductLinkQuality.objects.filter(
            product=product,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()


class AutoDbProductSplitV22DisplayOnlyDryRunService:
    IN_GAP_ANALYSIS = Path("/tmp/product_quality_split_v2_1_moved_brand_gap_analysis.csv")
    IN_SUPPLIER_CANDIDATES = Path("/tmp/product_quality_split_v2_1_moved_brand_supplier_candidates.csv")
    IN_V21_SIM = Path("/tmp/product_quality_split_v2_1_validator_after_brand_resolution_simulation.csv")
    IN_V21_RECOMMEND = Path("/tmp/product_quality_split_v2_1_display_only_policy_recommendation.md")
    IN_V21_FINAL = Path("/tmp/product_quality_split_v2_1_moved_brand_gap_final_report.md")
    IN_BATCH = Path("/tmp/product_quality_split_v2_batch_candidates.csv")

    OUT_A_CSV = Path("/tmp/product_quality_split_v2_1_exact_supplier_nonclean_diagnosis.csv")
    OUT_A_MD = Path("/tmp/product_quality_split_v2_1_exact_supplier_nonclean_diagnosis.md")
    OUT_B_MD = Path("/tmp/product_quality_split_v2_2_display_only_rules.md")
    OUT_D_CSV = Path("/tmp/product_quality_split_v2_2_display_only_dry_run.csv")
    OUT_D_MD = Path("/tmp/product_quality_split_v2_2_display_only_dry_run.md")
    OUT_E_MD = Path("/tmp/product_quality_split_v2_2_display_only_comparison.md")
    OUT_F_CSV = Path("/tmp/product_quality_split_v2_2_display_only_apply_approval.csv")
    OUT_F_XLSX = Path("/tmp/product_quality_split_v2_2_display_only_apply_approval.xlsx")
    OUT_F_MD = Path("/tmp/product_quality_split_v2_2_display_only_apply_approval.md")
    OUT_H_CSV = Path("/tmp/product_quality_split_v2_2_display_only_integrity.csv")
    OUT_H_MD = Path("/tmp/product_quality_split_v2_2_display_only_integrity.md")
    OUT_I_MD = Path("/tmp/product_quality_split_v2_2_display_only_final_report.md")

    def __init__(self):
        self.planner = AutoDbProductSplitV22DisplayOnlyPlanner()

    def run(self) -> dict[str, Any]:
        before = self._integrity_snapshot()

        gap_rows = self._read_csv(self.IN_GAP_ANALYSIS)
        supplier_rows = self._read_csv(self.IN_SUPPLIER_CANDIDATES)
        v21_sim_rows = self._read_csv(self.IN_V21_SIM)
        batch_rows = self._read_csv(self.IN_BATCH)

        supplier_by_pid = {str(r.get("product_id") or "").strip(): r for r in supplier_rows}
        v21_by_pid = {str(r.get("product_id") or "").strip(): r for r in v21_sim_rows}
        batch_by_pid = {str(r.get("product_id") or "").strip(): r for r in batch_rows}

        exact_diag_rows = self._exact_supplier_nonclean_diagnosis(
            supplier_by_pid=supplier_by_pid,
            v21_by_pid=v21_by_pid,
            batch_by_pid=batch_by_pid,
        )
        self._export_exact_diag(exact_diag_rows)

        self._export_display_only_rules()

        candidates = self._build_candidates(gap_rows=gap_rows, batch_by_pid=batch_by_pid)
        dry_rows = [asdict(self.planner.plan(candidate)) for candidate in candidates]
        dry_summary = self._export_display_only_dry_run(dry_rows)

        self._export_comparison(v21_sim_rows=v21_sim_rows, v22_rows=dry_rows)

        approval_rows = self._build_approval_rows(dry_rows)
        self._export_approval(approval_rows)

        after = self._integrity_snapshot()
        integrity_rows = self._integrity_rows(before, after)
        self._export_integrity(integrity_rows)

        self._export_final_report(
            exact_diag_rows=exact_diag_rows,
            dry_rows=dry_rows,
            dry_summary=dry_summary,
            approval_rows=approval_rows,
            integrity_rows=integrity_rows,
        )

        return {
            "exact_diag_rows": exact_diag_rows,
            "dry_rows": dry_rows,
            "dry_summary": dry_summary,
            "approval_rows": approval_rows,
            "integrity_rows": integrity_rows,
        }

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]

    def _split_ids(self, raw: str) -> tuple[str, ...]:
        return tuple(sorted({x.strip() for x in str(raw or "").split(",") if x.strip()}))

    def _brand_from_group(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        left = text.split("|", 1)[0]
        return left.split("[", 1)[0].strip()

    def _build_candidates(self, *, gap_rows: list[dict[str, str]], batch_by_pid: dict[str, dict[str, str]]) -> list[DisplayOnlyCandidate]:
        candidates: list[DisplayOnlyCandidate] = []
        for row in gap_rows:
            product_id = str(row.get("product_id") or "").strip()
            batch = batch_by_pid.get(product_id, {})
            keep_group = str(batch.get("keep_group") or "").strip()
            move_group = str(batch.get("move_group") or row.get("move_group") or "").strip()
            moved_offer_ids = self._split_ids(str(batch.get("supplier_offer_ids_to_move") or ""))
            move_brand = str(row.get("inferred_move_brand") or self._brand_from_group(move_group)).strip()
            candidate = DisplayOnlyCandidate(
                product_id=product_id,
                original_sku=str(row.get("original_sku") or "").strip(),
                keep_group=keep_group,
                move_group=move_group,
                move_brand=move_brand,
                move_brand_norm=normalize_brand(str(row.get("normalized_move_brand") or move_brand)),
                supplier_code=str(row.get("supplier_code") or "").strip().lower(),
                moved_offer_ids=moved_offer_ids,
            )
            candidates.append(candidate)
        return candidates

    def _exact_supplier_nonclean_diagnosis(
        self,
        *,
        supplier_by_pid: dict[str, dict[str, str]],
        v21_by_pid: dict[str, dict[str, str]],
        batch_by_pid: dict[str, dict[str, str]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for pid, srow in supplier_by_pid.items():
            if str(srow.get("candidate_classification") or "") != "exact_supplier_candidate":
                continue
            v21 = v21_by_pid.get(pid, {})
            batch = batch_by_pid.get(pid, {})
            move_group = str(batch.get("move_group") or srow.get("move_group") or "")
            keep_group = str(batch.get("keep_group") or "")
            strict_plan = self.planner.strict.plan(
                sku=str(srow.get("original_sku") or ""),
                source_product_id=pid,
                moved_offer_ids=list(self._split_ids(str(batch.get("supplier_offer_ids_to_move") or ""))),
                keep_group=keep_group,
                move_group=move_group,
            )

            source_pp = list(ProductPrice.objects.filter(product_id=pid).only("purchase_price", "final_price"))
            source_pp_status = "explicit" if len(source_pp) == 1 else ("missing" if len(source_pp) == 0 else "ambiguous")
            pp_value = str(source_pp[0].purchase_price) if len(source_pp) == 1 else ""
            keep_offers = list(SupplierOffer.objects.filter(id__in=list(strict_plan.offers_to_keep)).only("purchase_price"))
            keep_pp = str(keep_offers[0].purchase_price) if len(keep_offers) == 1 else ""

            remaining_blockers = str(v21.get("simulated_remaining_blockers") or v21.get("current_blockers") or "")

            rec = "keep_blocked"
            if "source_productprice_basis_mismatch" in remaining_blockers or "old_price_basis_would_remain_on_source" in remaining_blockers:
                rec = "fix ProductPrice basis logic"
            elif "source_catalog_brand_mismatch_requires_update" in remaining_blockers or "source_display_brand_mismatch_requires_update" in remaining_blockers:
                rec = "fix catalog/display logic"
            elif "brand_display_conflict_unresolved_new_autodb_supplier" in remaining_blockers:
                rec = "display_only_candidate"

            rows.append(
                {
                    "original_sku": str(srow.get("original_sku") or ""),
                    "product_id": pid,
                    "move_group": move_group,
                    "inferred_move_brand": str(srow.get("inferred_move_brand") or ""),
                    "exact_autodb_supplier": str(srow.get("exact_match_candidates") or ""),
                    "expected_new_display_autodb_fields": f"new_display={self._brand_from_group(move_group)};new_autodb={str(srow.get('exact_match_candidates') or '').split(':',1)[0]}",
                    "remaining_blockers_after_exact_supplier_resolution": remaining_blockers,
                    "productprice_basis_status": source_pp_status,
                    "productprice_purchase_current": pp_value,
                    "productprice_purchase_expected_from_keep": keep_pp,
                    "catalog_display_status": f"source_brand_after={strict_plan.source_brand_after};source_display_after={strict_plan.source_display_brand_after};new_brand_after={strict_plan.new_brand_after}",
                    "supplieroffer_supplierrawoffer_grouping_status": f"offers_to_move={','.join(strict_plan.offers_to_move)};raw_to_move={','.join(strict_plan.raw_offers_to_move)}",
                    "recommended_action": rec,
                }
            )
        return rows

    def _export_exact_diag(self, rows: list[dict[str, Any]]) -> None:
        headers = [
            "original_sku",
            "product_id",
            "move_group",
            "inferred_move_brand",
            "exact_autodb_supplier",
            "expected_new_display_autodb_fields",
            "remaining_blockers_after_exact_supplier_resolution",
            "productprice_basis_status",
            "productprice_purchase_current",
            "productprice_purchase_expected_from_keep",
            "catalog_display_status",
            "supplieroffer_supplierrawoffer_grouping_status",
            "recommended_action",
        ]
        self._write_csv(self.OUT_A_CSV, rows, headers)

        lines = [
            "# Split v2.1 exact supplier non-clean diagnosis",
            "",
            f"- rows: {len(rows)}",
            "",
            "| sku | move_brand | exact_supplier | remaining_blockers | action |",
            "|---|---|---|---|---|",
        ]
        for row in rows:
            lines.append(
                f"| {row['original_sku']} | {row['inferred_move_brand']} | {row['exact_autodb_supplier']} | {row['remaining_blockers_after_exact_supplier_resolution']} | {row['recommended_action']} |"
            )
        self.OUT_A_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _export_display_only_rules(self) -> None:
        lines = [
            "# Split v2.2 display-only rules (dry-run only)",
            "",
            "Display-only split can be clean only when all gates pass:",
            "- deterministic move-group brand from keep/move grouping evidence",
            "- move brand non-empty/non-invalid",
            "- deterministic move article and explicit moved SupplierOffer ids",
            "- explicit moved SupplierRawOffer ids",
            "- ProductPrice basis explicit and non-ambiguous (single source row + deterministic keep/move sets)",
            "- no trusted link conflict",
            "- no ProductImage/ProductAttribute/ProductFitment dependency blockers",
            "- no orphan split artifact blocker",
            "- proposed internal SKU has no visible SPLIT token",
            "- rollback plan exists",
            "",
            "Display-only proposed state (dry-run):",
            "- new product brand/display from moved group evidence",
            "- new product autodb_supplier_id=NULL",
            "- new product autodb_supplier_name=''",
            "- brand_source=split_offer_brand",
            "- new product excluded from Auto_DB article/product matching until supplier resolved",
            "",
            "Source product proposed state after split (dry-run):",
            "- brand/display/autodb recalculated from keep group when deterministic",
            "- if keep-group brand resolution is not deterministic, candidate remains blocked",
            "",
            "Exact-supplier candidates default policy:",
            "- exact supplier moved-brand rows stay on strict supplier-binding path",
            "- display-only path blocks them by default (exact_supplier_requires_strict_binding_path)",
        ]
        self.OUT_B_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _export_display_only_dry_run(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        headers = [
            "product_id",
            "original_sku",
            "keep_group",
            "move_group",
            "move_brand",
            "move_brand_norm",
            "supplier_code",
            "supplier_candidate_classification",
            "clean_display_only",
            "blockers",
            "proposed_original_brand",
            "proposed_original_display_brand",
            "proposed_original_autodb_supplier_id",
            "proposed_new_brand",
            "proposed_new_display_brand",
            "proposed_new_autodb_supplier_id",
            "proposed_new_autodb_supplier_name",
            "proposed_new_brand_source",
            "moved_offer_ids",
            "moved_raw_offer_ids",
            "productprice_plan",
            "productprice_basis_status",
            "queue_state_after_split",
            "rollback_plan",
            "strict_v21_blockers_snapshot",
        ]
        self._write_csv(self.OUT_D_CSV, rows, headers)

        checked = len(rows)
        clean = sum(1 for row in rows if bool(row.get("clean_display_only")))
        blocked = checked - clean
        blockers_counter = Counter()
        no_supplier_clean = 0
        exact_supplier_blocked = 0
        for row in rows:
            blockers = self._tupleize(row.get("blockers"))
            for blocker in blockers:
                blockers_counter[blocker] += 1
            if str(row.get("supplier_candidate_classification") or "") == "no_supplier_candidate" and bool(row.get("clean_display_only")):
                no_supplier_clean += 1
            if str(row.get("supplier_candidate_classification") or "") == "exact_supplier_candidate" and not bool(row.get("clean_display_only")):
                exact_supplier_blocked += 1

        summary = {
            "checked": checked,
            "display_only_clean": clean,
            "blocked": blocked,
            "no_supplier_clean_count": no_supplier_clean,
            "exact_supplier_still_blocked_count": exact_supplier_blocked,
            "recommended_apply_batch_size_if_approved": min(clean, 5),
            "blockers_by_type": tuple(blockers_counter.most_common(20)),
        }

        lines = [
            "# Split v2.2 display-only dry-run",
            "",
            f"- checked: {checked}",
            f"- display_only_clean: {clean}",
            f"- blocked: {blocked}",
            f"- no_supplier clean count: {no_supplier_clean}",
            f"- exact_supplier still blocked count: {exact_supplier_blocked}",
            f"- recommended apply batch size if later approved: {summary['recommended_apply_batch_size_if_approved']}",
            "- blockers by type:",
        ]
        for blocker, count in blockers_counter.most_common(20):
            lines.append(f"  - {blocker}: {count}")
        self.OUT_D_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return summary

    def _export_comparison(self, *, v21_sim_rows: list[dict[str, str]], v22_rows: list[dict[str, Any]]) -> None:
        v21_clean = sum(1 for row in v21_sim_rows if str(row.get("simulated_status_after_proposed_aliases") or "") == "would_become_clean")
        v21_blocked = len(v21_sim_rows) - v21_clean
        v22_clean = sum(1 for row in v22_rows if bool(row.get("clean_display_only")))
        v22_blocked = len(v22_rows) - v22_clean

        lines = [
            "# Split v2.1 strict vs v2.2 display-only comparison",
            "",
            f"- v2.1 strict clean count: {v21_clean}",
            f"- v2.1 strict blocked count: {v21_blocked}",
            f"- v2.2 display-only clean count: {v22_clean}",
            f"- v2.2 display-only blocked count: {v22_blocked}",
            "",
            "Risks introduced by display-only:",
            "- new split products can remain unresolved for Auto_DB supplier and must stay excluded from matching",
            "- extra brand-gap manual review workload",
            "- strict guardrails needed to avoid mis-splits where dependencies/trusted links exist",
            "",
            "Safeguards required before any apply:",
            "- keep strict blocker set for trusted/dependency/ambiguous ProductPrice/raw-offer cases",
            "- enforce explicit rollback package for every candidate",
            "- apply in micro-batches only after user approval",
        ]
        self.OUT_E_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _build_approval_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            if not bool(row.get("clean_display_only")):
                continue
            moved_offer_ids = self._tupleize(row.get("moved_offer_ids"))
            moved_raw_ids = self._tupleize(row.get("moved_raw_offer_ids"))
            out.append(
                {
                    "original SKU": str(row.get("original_sku") or ""),
                    "product_id": str(row.get("product_id") or ""),
                    "keep group": str(row.get("keep_group") or ""),
                    "move group": str(row.get("move_group") or ""),
                    "move brand": str(row.get("move_brand") or ""),
                    "new display brand": str(row.get("proposed_new_display_brand") or ""),
                    "new autodb_supplier_id expected NULL": "NULL",
                    "SupplierOffer ids to move": ",".join(moved_offer_ids),
                    "SupplierRawOffer ids to move": ",".join(moved_raw_ids),
                    "ProductPrice handling": str(row.get("productprice_plan") or ""),
                    "expected Product count delta": "+1",
                    "expected ProductPrice count delta": "0_or_+1_per_plan",
                    "matching exclusion status": str(row.get("queue_state_after_split") or ""),
                    "brand gap review status": "required",
                    "rollback note": ";".join(self._tupleize(row.get("rollback_plan"))),
                    "user_approval": "",
                    "user_notes": "",
                }
            )
        return out

    def _export_approval(self, rows: list[dict[str, Any]]) -> None:
        headers = [
            "original SKU",
            "product_id",
            "keep group",
            "move group",
            "move brand",
            "new display brand",
            "new autodb_supplier_id expected NULL",
            "SupplierOffer ids to move",
            "SupplierRawOffer ids to move",
            "ProductPrice handling",
            "expected Product count delta",
            "expected ProductPrice count delta",
            "matching exclusion status",
            "brand gap review status",
            "rollback note",
            "user_approval",
            "user_notes",
        ]
        self._write_csv(self.OUT_F_CSV, rows, headers)

        wb = Workbook()
        ws = wb.active
        ws.title = "display_only_clean"
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h, "") for h in headers])
        wb.save(self.OUT_F_XLSX)

        lines = [
            "# Split v2.2 display-only apply approval package (no apply)",
            "",
            f"- clean rows: {len(rows)}",
            f"- csv: {self.OUT_F_CSV}",
            f"- xlsx: {self.OUT_F_XLSX}",
        ]
        self.OUT_F_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _integrity_snapshot(self) -> dict[str, Any]:
        stock_sum = SupplierOffer.objects.aggregate(v=Sum("stock_qty")).get("v") or 0
        price_sum = ProductPrice.objects.aggregate(v=Sum("final_price")).get("v")
        return {
            "Product": Product.objects.count(),
            "SupplierOffer": SupplierOffer.objects.count(),
            "SupplierRawOffer": SupplierRawOffer.objects.count(),
            "ProductPrice": ProductPrice.objects.count(),
            "ProductAttribute": ProductAttribute.objects.count(),
            "ProductFitment": ProductFitment.objects.count(),
            "ProductImage": ProductImage.objects.count(),
            "AutoDbSupplierBrandAlias": AutoDbSupplierBrandAlias.objects.count(),
            "linked_by_key": Product.objects.exclude(autodb_article_key__isnull=True).exclude(autodb_article_key="").count(),
            "quality_trusted": AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_TRUSTED).count(),
            "sum_supplier_stock_qty": int(stock_sum),
            "sum_productprice_final": str(price_sum if price_sum is not None else Decimal("0")),
            "UTR_API_calls": 0,
        }

    def _integrity_rows(self, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for key in before:
            b = before[key]
            a = after.get(key)
            try:
                delta = str(Decimal(str(a)) - Decimal(str(b)))
            except Exception:
                delta = "0" if a == b else f"{b}->{a}"
            rows.append({"metric": key, "before": str(b), "after": str(a), "delta": delta})
        return rows

    def _export_integrity(self, rows: list[dict[str, str]]) -> None:
        headers = ["metric", "before", "after", "delta"]
        self._write_csv(self.OUT_H_CSV, rows, headers)
        changed = [row for row in rows if not (row["before"] == row["after"] or row["delta"] in {"0", "0.00"})]
        lines = [
            "# Split v2.2 display-only integrity",
            "",
            f"- metrics_checked: {len(rows)}",
            f"- changed_metrics: {len(changed)}",
        ]
        if not changed:
            lines.append("- all tracked metrics unchanged")
        self.OUT_H_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _export_final_report(
        self,
        *,
        exact_diag_rows: list[dict[str, Any]],
        dry_rows: list[dict[str, Any]],
        dry_summary: dict[str, Any],
        approval_rows: list[dict[str, Any]],
        integrity_rows: list[dict[str, str]],
    ) -> None:
        blockers = Counter()
        for row in dry_rows:
            for blocker in self._tupleize(row.get("blockers")):
                blockers[blocker] += 1
        changed = [row for row in integrity_rows if not (row["before"] == row["after"] or row["delta"] in {"0", "0.00"})]

        lines = [
            "# Split v2.2 display-only final report",
            "",
            "1. Why 5 exact_supplier_candidate rows did not become clean.",
            f"- diagnosed rows: {len(exact_diag_rows)}",
            "- dominant reasons: strict unresolved-new-autodb blocker in v2.1 and/or ProductPrice basis mismatch on source product.",
            "",
            "2. Display-only rules implemented.",
            f"- rules doc: {self.OUT_B_MD}",
            "",
            "3. Display-only clean candidate count.",
            f"- {dry_summary.get('display_only_clean', 0)}",
            "",
            "4. Blocked count and blockers.",
            f"- blocked: {dry_summary.get('blocked', 0)}",
        ]
        for blocker, count in blockers.most_common(12):
            lines.append(f"- {blocker}: {count}")
        lines.extend(
            [
                "",
                "5. Approval package path.",
                f"- {self.OUT_F_CSV}",
                f"- {self.OUT_F_XLSX}",
                f"- {self.OUT_F_MD}",
                "",
                "6. Whether display-only apply is recommended.",
                "- recommended only for clean_display_only rows and only as micro-batch after explicit approval.",
                "",
                "7. Tests run.",
                "- see command output from this task run.",
                "",
                "8. Confirmation no writes.",
                "- yes" if not changed else "- verify integrity deltas",
            ]
        )
        self.OUT_I_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _tupleize(self, raw: Any) -> tuple[str, ...]:
        text = str(raw or "").strip()
        if not text:
            return tuple()
        if text.startswith("(") and text.endswith(")"):
            try:
                parsed = ast.literal_eval(text)
            except Exception:
                parsed = None
            if isinstance(parsed, (tuple, list, set)):
                return tuple(str(item).strip() for item in parsed if str(item).strip())
        return tuple(part.strip() for part in text.split(",") if part.strip())

    def _write_csv(self, path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({h: row.get(h, "") for h in headers})
