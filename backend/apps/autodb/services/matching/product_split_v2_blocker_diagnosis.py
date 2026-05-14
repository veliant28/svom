from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import connections
from django.db.models import Count, Q, Sum
from openpyxl import Workbook

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolver
from apps.autodb.services.matching.deterministic_brand_binding import DeterministicBrandNormalizer
from apps.autodb.services.matching.product_split_v2_planner import AutoDbProductSplitV2Planner
from apps.autodb.services.matching.reports import write_report
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


GROUP_RE = re.compile(r"^\s*(?P<label>.+?)\[(?P<count>\d+)\]:(?P<ids>.+?)\s*$")


@dataclass(frozen=True)
class SplitGroup:
    raw: str
    label: str
    brand_raw: str
    brand_norm: str
    article_canonical: str
    count: int
    offer_ids: tuple[str, ...]


class AutoDbProductSplitV2BlockerDiagnosisService:
    def __init__(self):
        self.out = Path("/tmp")
        self.planner = AutoDbProductSplitV2Planner()
        self.resolver = AutoDbBrandResolver()
        self.normalizer = DeterministicBrandNormalizer()

        self.batch_dry_run_path = Path("/tmp/product_quality_split_v2_batch_dry_run.csv")
        self.batch_candidates_path = Path("/tmp/product_quality_split_v2_batch_candidates.csv")
        self.split_candidates_path = Path("/tmp/product_quality_split_candidates_dry_run.csv")
        self.bucket_path = Path("/tmp/product_quality_multioffer_correction_buckets.csv")

    def run(self, *, max_batch_size: int = 20) -> dict[str, Any]:
        before = self._integrity_snapshot()

        batch_dry_rows = self._read_csv(self.batch_dry_run_path)
        batch_candidate_rows = self._read_csv(self.batch_candidates_path)
        source_rows = self._read_csv(self.split_candidates_path)
        bucket_rows = self._read_csv(self.bucket_path)
        bucket_map = {str(row.get("product_id") or "").strip(): row for row in bucket_rows if str(row.get("product_id") or "").strip()}

        blocked_rows = [row for row in batch_dry_rows if not self._as_bool(row.get("clean"))]
        blocked_ids = [str(row.get("product_id") or "").strip() for row in blocked_rows if str(row.get("product_id") or "").strip()]
        db_state = self._load_state_maps(product_ids=blocked_ids)
        local_supplier_map, supplier_variant_index = self._load_local_suppliers()

        blocked_diag_rows = self._diagnose_blocked_batch(
            blocked_rows=blocked_rows,
            candidate_rows=batch_candidate_rows,
            db_state=db_state,
            local_supplier_map=local_supplier_map,
            supplier_variant_index=supplier_variant_index,
        )
        self._export_blocked_diagnosis(blocked_diag_rows)

        search_rows = self._scan_resolved_brand_candidates(
            source_rows=source_rows,
            bucket_map=bucket_map,
            local_supplier_map=local_supplier_map,
            supplier_variant_index=supplier_variant_index,
            max_batch_size=max_batch_size,
        )
        self._export_search_rows(search_rows)

        best_rows = [row for row in search_rows if str(row.get("search_decision") or "") == "selected_for_resolved_batch"]
        dry_rows, dry_summary = self._run_resolved_batch_dry_run(best_rows=best_rows, max_batch_size=max_batch_size)
        self._export_resolved_dry_run(dry_rows=dry_rows, summary=dry_summary)

        approval_rows = self._build_approval_rows(dry_rows=dry_rows)
        self._export_approval_rows(approval_rows=approval_rows, summary=dry_summary)

        policy_text = self._display_only_policy(blocked_rows=blocked_diag_rows, search_rows=search_rows)
        (self.out / "product_quality_split_v2_display_only_brand_policy.md").write_text(policy_text, encoding="utf-8")

        after = self._integrity_snapshot()
        integrity_rows = self._integrity_rows(before=before, after=after)
        self._export_integrity(integrity_rows)

        self._export_final_report(
            blocked_rows=blocked_diag_rows,
            search_rows=search_rows,
            dry_summary=dry_summary,
            approval_count=len(approval_rows),
        )
        return {
            "blocked_rows": blocked_diag_rows,
            "search_rows": search_rows,
            "dry_rows": dry_rows,
            "dry_summary": dry_summary,
            "approval_rows": approval_rows,
        }

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def _load_state_maps(self, *, product_ids: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "products": {},
            "attr_counts": {},
            "fitment_counts": {},
            "image_counts": {},
            "trusted_products": set(),
            "offer_map": defaultdict(set),
            "raw_map": defaultdict(set),
            "supplier_code_map": {},
        }
        if not product_ids:
            return out

        products = Product.objects.select_related("brand").filter(id__in=product_ids)
        out["products"] = {str(item.id): item for item in products}

        attr_rows = ProductAttribute.objects.filter(product_id__in=product_ids).values("product_id").annotate(c=Count("id"))
        out["attr_counts"] = {str(item["product_id"]): int(item["c"] or 0) for item in attr_rows}
        fitment_rows = ProductFitment.objects.filter(product_id__in=product_ids).values("product_id").annotate(c=Count("id"))
        out["fitment_counts"] = {str(item["product_id"]): int(item["c"] or 0) for item in fitment_rows}
        image_rows = ProductImage.objects.filter(product_id__in=product_ids).values("product_id").annotate(c=Count("id"))
        out["image_counts"] = {str(item["product_id"]): int(item["c"] or 0) for item in image_rows}

        trusted = set(
            str(item)
            for item in AutoDbProductLinkQuality.objects.filter(
                product_id__in=product_ids,
                status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            ).values_list("product_id", flat=True)
        )
        linked_by_key = set(str(item.id) for item in products if str(item.autodb_article_key or "").strip())
        out["trusted_products"] = trusted | linked_by_key

        offers = SupplierOffer.objects.filter(product_id__in=product_ids).select_related("supplier")
        supplier_ids: set[int] = set()
        for offer in offers:
            pid = str(offer.product_id)
            oid = str(offer.id)
            out["offer_map"][pid].add(oid)
            supplier_ids.add(int(offer.supplier_id))
            out["supplier_code_map"][oid] = str(getattr(offer.supplier, "code", "") or "").strip().lower()

        raws = SupplierRawOffer.objects.filter(matched_product_id__in=product_ids)
        for row in raws:
            out["raw_map"][str(row.matched_product_id)].add(str(row.id))

        if supplier_ids:
            out["supplier_name_map"] = {
                int(item.id): str(item.name or "")
                for item in Supplier.objects.filter(id__in=list(supplier_ids)).only("id", "name")
            }
        else:
            out["supplier_name_map"] = {}

        return out

    def _load_local_suppliers(self) -> tuple[dict[int, dict[str, Any]], dict[str, set[int]]]:
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute("SELECT id, description, COALESCE(matchcode, ''), COALESCE(nbrofarticles, 0) FROM suppliers")
            rows = cursor.fetchall()
        supplier_map: dict[int, dict[str, Any]] = {}
        variant_index: dict[str, set[int]] = defaultdict(set)
        for sid, description, matchcode, nbrofarticles in rows:
            try:
                supplier_id = int(sid)
            except Exception:
                continue
            name = str(description or "").strip()
            code = str(matchcode or "").strip()
            if not name:
                continue
            variants = set(self.normalizer.variants(name))
            variants.update(self.normalizer.variants(code))
            if not variants:
                continue
            payload = {
                "supplier_id": supplier_id,
                "description": name,
                "matchcode": code,
                "nbrofarticles": int(nbrofarticles or 0),
                "variants": tuple(sorted(variants)),
            }
            supplier_map[supplier_id] = payload
            for variant in variants:
                variant_index[variant].add(supplier_id)
        return supplier_map, variant_index

    def _diagnose_blocked_batch(
        self,
        *,
        blocked_rows: list[dict[str, str]],
        candidate_rows: list[dict[str, str]],
        db_state: dict[str, Any],
        local_supplier_map: dict[int, dict[str, Any]],
        supplier_variant_index: dict[str, set[int]],
    ) -> list[dict[str, Any]]:
        candidate_map = {str(item.get("product_id") or "").strip(): item for item in candidate_rows}
        brand_name_by_norm = self._brand_name_by_norm()
        out: list[dict[str, Any]] = []
        for row in blocked_rows:
            product_id = str(row.get("product_id") or "").strip()
            candidate = candidate_map.get(product_id, {})
            product = db_state["products"].get(product_id)
            keep_group = str(row.get("keep_group") or candidate.get("keep_group") or "")
            move_group = str(row.get("move_group") or candidate.get("move_group") or "")
            keep_parsed = self._first_group(keep_group)
            move_parsed = self._first_group(move_group)
            move_offer_ids = self._split_ids(str(row.get("supplier_offer_ids_to_move") or candidate.get("supplier_offer_ids_to_move") or ""))
            move_offer_codes = sorted(
                {
                    str(db_state["supplier_code_map"].get(oid, "") or "").strip().lower()
                    for oid in move_offer_ids
                    if str(db_state["supplier_code_map"].get(oid, "") or "").strip()
                }
            )
            supplier_code = move_offer_codes[0] if len(move_offer_codes) == 1 else ""
            product_bound_supplier = int(getattr(product, "autodb_supplier_id", 0) or 0) if product is not None else 0
            resolution = self.resolver.resolve(
                raw_brand=move_parsed.brand_raw if move_parsed else "",
                supplier_code=supplier_code,
                product_autodb_supplier_id=product_bound_supplier or None,
            )

            deterministic_supplier_ids: set[int] = set()
            if move_parsed:
                for variant in self.normalizer.variants(move_parsed.brand_raw):
                    deterministic_supplier_ids.update(supplier_variant_index.get(variant, set()))

            catalog_exists = bool(move_parsed and move_parsed.brand_norm in brand_name_by_norm)
            raw_exists = bool(move_parsed and move_parsed.brand_raw.strip())
            deterministic_exists = len(deterministic_supplier_ids) == 1
            can_display_only = bool(move_parsed and move_parsed.brand_raw.strip() and resolution.decision != "unsafe_ambiguous")

            blockers = self._split_tags(str(row.get("blockers") or ""))
            if "brand_display_conflict_unresolved_new_autodb_supplier" in blockers and can_display_only:
                action = "retry_with_display_only_brand"
            elif resolution.decision == "keep_unmapped_missing_supplier":
                action = "needs_brand_gap_resolution"
            elif resolution.decision in {"unsafe_ambiguous", "needs_human_approval"}:
                action = "manual_review"
            else:
                action = "keep_blocked"

            reason_bits = [
                f"resolver_decision={resolution.decision}",
                f"resolver_source={resolution.resolver_source}",
                f"resolver_reason={resolution.reason}",
                f"deterministic_candidates={';'.join(str(item) for item in sorted(deterministic_supplier_ids))}",
            ]
            out.append(
                {
                    "product_id": product_id,
                    "sku": str(row.get("original_sku") or candidate.get("original_sku") or ""),
                    "product_name": str(getattr(product, "name", "") or candidate.get("product_name") or ""),
                    "current_catalog_brand": str(getattr(getattr(product, "brand", None), "name", "") or candidate.get("current_brand") or ""),
                    "current_display_brand": str(getattr(product, "display_brand_name", "") or candidate.get("current_display_brand") or ""),
                    "current_autodb_supplier_id": int(getattr(product, "autodb_supplier_id", 0) or 0),
                    "keep_group": keep_group,
                    "move_group": move_group,
                    "keep_group_inferred_brand": keep_parsed.brand_raw if keep_parsed else "",
                    "move_group_inferred_brand": move_parsed.brand_raw if move_parsed else "",
                    "keep_group_article": keep_parsed.article_canonical if keep_parsed else "",
                    "move_group_article": move_parsed.article_canonical if move_parsed else "",
                    "supplier_offer_ids_to_move": ",".join(move_offer_ids),
                    "supplier_raw_offer_ids_to_move": str(row.get("supplier_raw_offer_ids_to_move") or ""),
                    "productprice_plan": str(row.get("productprice_plan") or ""),
                    "exact_blockers": ";".join(blockers),
                    "why_new_autodb_supplier_unresolved": " | ".join(reason_bits),
                    "raw_brand_exists": raw_exists,
                    "catalog_brand_exists": catalog_exists,
                    "candidate_autodb_supplier_exists": bool(resolution.supplier_id or deterministic_exists),
                    "brand_can_be_display_only_without_autodb_supplier": can_display_only,
                    "recommended_next_action": action,
                }
            )
        return out

    def _scan_resolved_brand_candidates(
        self,
        *,
        source_rows: list[dict[str, str]],
        bucket_map: dict[str, dict[str, str]],
        local_supplier_map: dict[int, dict[str, Any]],
        supplier_variant_index: dict[str, set[int]],
        max_batch_size: int,
    ) -> list[dict[str, Any]]:
        product_ids = [str(row.get("product_id") or "").strip() for row in source_rows if str(row.get("product_id") or "").strip()]
        product_map = {str(item.id): item for item in Product.objects.select_related("brand").filter(id__in=product_ids)}
        attr_counts = self._count_by_product(ProductAttribute.objects.filter(product_id__in=product_ids).values("product_id").annotate(c=Count("id")))
        fitment_counts = self._count_by_product(ProductFitment.objects.filter(product_id__in=product_ids).values("product_id").annotate(c=Count("id")))
        image_counts = self._count_by_product(ProductImage.objects.filter(product_id__in=product_ids).values("product_id").annotate(c=Count("id")))
        trusted_products = set(
            str(item)
            for item in AutoDbProductLinkQuality.objects.filter(
                product_id__in=product_ids, status=AutoDbProductLinkQuality.STATUS_TRUSTED
            ).values_list("product_id", flat=True)
        )
        trusted_products.update(str(item.id) for item in product_map.values() if str(item.autodb_article_key or "").strip())
        linked_products = set(str(item.id) for item in product_map.values() if str(item.autodb_article_key or "").strip())

        offers = SupplierOffer.objects.filter(product_id__in=product_ids).select_related("supplier")
        offer_ids_by_product: dict[str, set[str]] = defaultdict(set)
        supplier_code_by_offer: dict[str, str] = {}
        for offer in offers:
            pid = str(offer.product_id)
            oid = str(offer.id)
            offer_ids_by_product[pid].add(oid)
            supplier_code_by_offer[oid] = str(getattr(offer.supplier, "code", "") or "").strip().lower()

        raw_ids_by_product: dict[str, set[str]] = defaultdict(set)
        for raw in SupplierRawOffer.objects.filter(matched_product_id__in=product_ids).only("id", "matched_product_id"):
            raw_ids_by_product[str(raw.matched_product_id)].add(str(raw.id))

        top_candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        out_rows: list[dict[str, Any]] = []

        for row in source_rows:
            product_id = str(row.get("product_id") or "").strip()
            if not product_id:
                continue
            product = product_map.get(product_id)
            if product is None:
                continue
            if str(row.get("recommended_action") or "").strip() not in {"split_product_candidate", "split_product_after_manual_review"}:
                continue

            groups = self._parse_groups(str(row.get("proposed_split_groups") or ""))
            group_count = len(groups)
            two_groups = group_count == 2
            if not two_groups:
                decision = "blocked_not_two_groups"
            else:
                decision = "candidate"
            keep_group, move_group = self._pick_keep_move(
                groups=groups,
                product=product,
                bucket_row=bucket_map.get(product_id) or {},
            )
            if keep_group is None or move_group is None:
                decision = "blocked_group_parse"

            blockers: list[str] = []
            if decision.startswith("blocked"):
                blockers.append(decision)
            if product_id in trusted_products:
                blockers.append("trusted_link_conflict")
            if attr_counts.get(product_id, 0) > 0:
                blockers.append("productattribute_blocker")
            if fitment_counts.get(product_id, 0) > 0:
                blockers.append("productfitment_blocker")
            if image_counts.get(product_id, 0) > 0:
                blockers.append("productimage_blocker")

            raw_blockers = [item for item in self._split_tags(str(row.get("safety_blockers") or "")) if item]
            if raw_blockers:
                blockers.extend(f"source_{item}" for item in raw_blockers)

            move_offer_ids = move_group.offer_ids if move_group else tuple()
            offer_set = offer_ids_by_product.get(product_id, set())
            if not move_offer_ids:
                blockers.append("empty_move_offer_set")
            elif not set(move_offer_ids).issubset(offer_set):
                blockers.append("move_offers_not_subset")

            source_codes = sorted({supplier_code_by_offer.get(oid, "") for oid in move_offer_ids if supplier_code_by_offer.get(oid, "")})
            move_supplier_code = source_codes[0] if len(source_codes) == 1 else ""
            bound_supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0)
            resolution = self.resolver.resolve(
                raw_brand=move_group.brand_raw if move_group else "",
                supplier_code=move_supplier_code,
                product_autodb_supplier_id=bound_supplier_id or None,
            )
            deterministic_ids: set[int] = set()
            if move_group:
                for variant in self.normalizer.variants(move_group.brand_raw):
                    deterministic_ids.update(supplier_variant_index.get(variant, set()))

            resolved_supplier_id = 0
            resolved_source = ""
            if int(resolution.supplier_id or 0) > 0:
                resolved_supplier_id = int(resolution.supplier_id or 0)
                resolved_source = str(resolution.resolver_source or "")
            elif len(deterministic_ids) == 1:
                resolved_supplier_id = int(next(iter(deterministic_ids)))
                resolved_source = "deterministic_normalization"
            if resolved_supplier_id <= 0:
                blockers.append("move_brand_unresolved")

            if str(product.sku or "").upper().find("SPLIT") >= 0:
                blockers.append("already_split")

            price_ratio = self._as_float(row.get("price_ratio"))
            planner_clean = ""
            planner_blockers = ""
            if not blockers and keep_group and move_group:
                plan = self.planner.plan(
                    sku=str(product.svom_sku or product.sku or ""),
                    source_product_id=product_id,
                    moved_offer_ids=list(move_offer_ids),
                    keep_group=keep_group.raw,
                    move_group=move_group.raw,
                )
                planner_clean = str(bool(plan.clean))
                planner_blockers = ";".join(plan.blockers)
                if not plan.clean:
                    blockers.extend(f"planner_{item}" for item in plan.blockers)

            search_decision = "blocked"
            if not blockers:
                search_decision = "selected_for_resolved_batch"
            elif "move_brand_unresolved" in blockers:
                search_decision = "needs_brand_resolution"

            row_payload = {
                "product_id": product_id,
                "sku": str(product.svom_sku or product.sku or ""),
                "product_name": str(product.name or ""),
                "current_catalog_brand": str(getattr(product.brand, "name", "") or ""),
                "current_display_brand": str(product.display_brand_name or ""),
                "current_autodb_supplier_id": int(getattr(product, "autodb_supplier_id", 0) or 0),
                "group_count": group_count,
                "keep_group": keep_group.raw if keep_group else "",
                "move_group": move_group.raw if move_group else "",
                "keep_brand_norm": keep_group.brand_norm if keep_group else "",
                "move_brand_norm": move_group.brand_norm if move_group else "",
                "keep_article": keep_group.article_canonical if keep_group else "",
                "move_article": move_group.article_canonical if move_group else "",
                "move_offer_ids": ",".join(move_offer_ids),
                "raw_offer_unambiguous": bool(raw_ids_by_product.get(product_id)),
                "offer_unambiguous": bool(move_offer_ids and set(move_offer_ids).issubset(offer_set)),
                "resolved_move_supplier_id": resolved_supplier_id,
                "resolved_move_supplier_name": str(local_supplier_map.get(resolved_supplier_id, {}).get("description", "")),
                "resolver_source": resolved_source,
                "resolver_decision": str(resolution.decision or ""),
                "resolver_reason": str(resolution.reason or ""),
                "planner_clean_preview": planner_clean,
                "planner_blockers_preview": planner_blockers,
                "price_ratio": f"{price_ratio:.4f}" if price_ratio else "",
                "trusted_link_conflict": product_id in trusted_products,
                "gpl_utr_conflict": len(source_codes) > 1 or ("gpl" in source_codes and "utr" in source_codes),
                "productattribute_count": int(attr_counts.get(product_id, 0)),
                "productfitment_count": int(fitment_counts.get(product_id, 0)),
                "productimage_count": int(image_counts.get(product_id, 0)),
                "search_decision": search_decision,
                "search_blockers": ";".join(sorted(set(blockers))),
            }
            out_rows.append(row_payload)

            if search_decision == "selected_for_resolved_batch":
                rank = (
                    0 if resolved_source in {"product_autodb_supplier_id", "alias", "exact_supplier", "normalized_supplier"} else 1,
                    0 if (len(source_codes) > 1 or ("gpl" in source_codes and "utr" in source_codes)) else 1,
                    0 if price_ratio >= 3.0 else 1,
                    len(move_offer_ids),
                    -price_ratio,
                )
                top_candidates.append((rank, row_payload))

        top_candidates.sort(key=lambda item: item[0])
        selected_ids = {row["product_id"] for _, row in top_candidates[: max(1, int(max_batch_size or 20))]}
        for row in out_rows:
            if row.get("search_decision") == "selected_for_resolved_batch" and row.get("product_id") not in selected_ids:
                row["search_decision"] = "candidate_not_in_top_batch"
                row["search_blockers"] = "batch_limit"
        return out_rows

    def _run_resolved_batch_dry_run(self, *, best_rows: list[dict[str, Any]], max_batch_size: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        blocker_counter = Counter()
        for row in best_rows[: max(1, int(max_batch_size or 20))]:
            plan = self.planner.plan(
                sku=str(row.get("sku") or ""),
                source_product_id=str(row.get("product_id") or ""),
                moved_offer_ids=self._split_ids(str(row.get("move_offer_ids") or "")),
                keep_group=str(row.get("keep_group") or ""),
                move_group=str(row.get("move_group") or ""),
            )
            payload = {
                "product_id": str(row.get("product_id") or ""),
                "original_sku": str(row.get("sku") or ""),
                "current_brand_display": f"{row.get('current_catalog_brand','')} / {row.get('current_display_brand','')}",
                "keep_group": str(row.get("keep_group") or ""),
                "move_group": str(row.get("move_group") or ""),
                "supplier_offer_ids_to_move": str(row.get("move_offer_ids") or ""),
                "supplier_raw_offer_ids_to_move": ",".join(plan.raw_offers_to_move),
                "proposed_new_internal_sku": plan.proposed_internal_sku,
                "proposed_new_public_sku_strategy": plan.proposed_public_sku_strategy,
                "proposed_original_brand_after_split": f"{plan.source_brand_after} / {plan.source_display_brand_after}",
                "proposed_new_brand_after_split": f"{plan.new_brand_after} / {plan.new_display_brand_after}",
                "new_autodb_supplier_id_if_resolved": int(plan.new_autodb_supplier_id_after or 0),
                "productprice_plan": plan.productprice_strategy,
                "productprice_actions": ";".join(plan.productprice_actions),
                "clean": bool(plan.clean),
                "blockers": ";".join(plan.blockers),
            }
            rows.append(payload)
            for blocker in plan.blockers:
                blocker_counter[blocker] += 1

        clean_rows = [row for row in rows if self._as_bool(row.get("clean"))]
        summary = {
            "checked": len(rows),
            "clean": len(clean_rows),
            "blocked": len(rows) - len(clean_rows),
            "blockers_by_type": dict(blocker_counter),
            "recommended_first_apply_batch_size": min(len(clean_rows), 10) if clean_rows else 0,
            "top_10_clean_candidates": [row.get("product_id") for row in clean_rows[:10]],
        }
        return rows, summary

    def _build_approval_rows(self, *, dry_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in dry_rows:
            if not self._as_bool(row.get("clean")):
                continue
            out.append(
                {
                    "product_id": row.get("product_id") or "",
                    "original_sku": row.get("original_sku") or "",
                    "proposed_new_internal_sku": row.get("proposed_new_internal_sku") or "",
                    "proposed_public_sku_strategy": row.get("proposed_new_public_sku_strategy") or "",
                    "keep_group": row.get("keep_group") or "",
                    "move_group": row.get("move_group") or "",
                    "keep_brand_display_after_split": row.get("proposed_original_brand_after_split") or "",
                    "new_brand_display_after_split": row.get("proposed_new_brand_after_split") or "",
                    "new_autodb_supplier_id_if_resolved": row.get("new_autodb_supplier_id_if_resolved") or "",
                    "supplier_offer_ids_to_move": row.get("supplier_offer_ids_to_move") or "",
                    "supplier_raw_offer_ids_to_move": row.get("supplier_raw_offer_ids_to_move") or "",
                    "productprice_handling": row.get("productprice_plan") or "",
                    "expected_product_count_delta": 1,
                    "expected_productprice_count_delta": 0,
                    "rollback_note": "move offers/raw offers back, restore source brand fields, deactivate new product, rerun reprice",
                    "user_approval": "",
                    "user_notes": "",
                }
            )
        return out

    def _display_only_policy(self, *, blocked_rows: list[dict[str, Any]], search_rows: list[dict[str, Any]]) -> str:
        unresolved_blocked = [
            row for row in blocked_rows if str(row.get("recommended_next_action") or "") == "retry_with_display_only_brand"
        ]
        unresolved_search = [row for row in search_rows if "move_brand_unresolved" in str(row.get("search_blockers") or "")]
        lines = [
            "# Product split v2 display-only brand policy (proposal, no apply)",
            "",
            f"- blocked_due_unresolved_new_autodb_supplier_in_latest_batch: {len(unresolved_blocked)}",
            f"- unresolved_move_brand_candidates_in_full_search: {len(unresolved_search)}",
            "- policy_scope: split v2 only, for products where move-group brand is deterministic but local Auto_DB supplier unresolved",
            "",
            "## Proposed Safe Rules",
            "- allow new product brand/display from deterministic move-group offer brand",
            "- set `autodb_supplier_id = NULL` and `autodb_supplier_name = ''` on new split product",
            "- set `brand_source = product_quality_split` (or `offer_split` if introduced as enum)",
            "- set `brand_source_hash = split_v2_display_only:<source_product_id>`",
            "- mark state flag `brand_unresolved_for_autodb = true` (new flag or equivalent metadata marker)",
            "- do not create Auto_DB supplier binding/alias as side effect",
            "- do not route such products into Auto_DB article/product matching until brand gap resolved",
            "- route into brand-gap review queue",
            "",
            "## Safeguards",
            "- keep current restrictions: no trusted-link products, no ambiguous moved offers/raw offers, no orphan split artifacts",
            "- no Product links/enrichment/images in split apply",
            "- no price/stock value override",
            "",
            "## Decision",
            "- implementation deferred; diagnostic recommendation only",
            "",
        ]
        return "\n".join(lines)

    def _export_blocked_diagnosis(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="product_quality_split_v2_blocked_batch_diagnosis",
            run_id=None,
            rows=rows,
            title="Product quality split v2 blocked batch diagnosis",
            summary={
                "blocked_rows": len(rows),
                "actions": dict(Counter(str(row.get("recommended_next_action") or "") for row in rows)),
            },
            export_prefix="/tmp/product_quality_split_v2_blocked_batch_diagnosis",
        )

    def _export_search_rows(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="product_quality_split_v2_resolved_brand_candidate_search",
            run_id=None,
            rows=rows,
            title="Product quality split v2 resolved-brand candidate search",
            summary={
                "rows": len(rows),
                "search_decision": dict(Counter(str(row.get("search_decision") or "") for row in rows)),
                "resolver_source": dict(Counter(str(row.get("resolver_source") or "") for row in rows)),
            },
            export_prefix="/tmp/product_quality_split_v2_resolved_brand_candidate_search",
        )

    def _export_resolved_dry_run(self, *, dry_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        write_report(
            command_name="product_quality_split_v2_resolved_brand_batch_dry_run",
            run_id=None,
            rows=dry_rows,
            title="Product quality split v2 resolved-brand batch dry-run",
            summary=summary,
            export_prefix="/tmp/product_quality_split_v2_resolved_brand_batch_dry_run",
        )

    def _export_approval_rows(self, *, approval_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        headers = [
            "product_id",
            "original_sku",
            "proposed_new_internal_sku",
            "proposed_public_sku_strategy",
            "keep_group",
            "move_group",
            "keep_brand_display_after_split",
            "new_brand_display_after_split",
            "new_autodb_supplier_id_if_resolved",
            "supplier_offer_ids_to_move",
            "supplier_raw_offer_ids_to_move",
            "productprice_handling",
            "expected_product_count_delta",
            "expected_productprice_count_delta",
            "rollback_note",
            "user_approval",
            "user_notes",
        ]
        csv_path = self.out / "product_quality_split_v2_resolved_brand_apply_approval.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in approval_rows:
                writer.writerow({header: row.get(header, "") for header in headers})

        wb = Workbook()
        ws = wb.active
        ws.title = "approval"
        ws.append(headers)
        for row in approval_rows:
            ws.append([row.get(header, "") for header in headers])
        wb.save(self.out / "product_quality_split_v2_resolved_brand_apply_approval.xlsx")

        lines = [
            "# Product quality split v2 resolved-brand apply approval package",
            "",
            f"- CSV: `{csv_path}`",
            f"- Rows: {len(approval_rows)}",
            f"- clean_candidates: {summary.get('clean', 0)}",
            f"- recommended_first_apply_batch_size: {summary.get('recommended_first_apply_batch_size', 0)}",
            "",
        ]
        (self.out / "product_quality_split_v2_resolved_brand_apply_approval.md").write_text("\n".join(lines), encoding="utf-8")

    def _export_integrity(self, rows: list[dict[str, Any]]) -> None:
        write_report(
            command_name="product_quality_split_v2_blocker_diagnosis_integrity",
            run_id=None,
            rows=rows,
            title="Product quality split v2 blocker diagnosis integrity",
            summary={"utr_api_calls": 0, "writes_expected": 0},
            export_prefix="/tmp/product_quality_split_v2_blocker_diagnosis_integrity",
        )

    def _export_final_report(
        self,
        *,
        blocked_rows: list[dict[str, Any]],
        search_rows: list[dict[str, Any]],
        dry_summary: dict[str, Any],
        approval_count: int,
    ) -> None:
        search_decisions = Counter(str(item.get("search_decision") or "") for item in search_rows)
        first_batch_blockers = Counter()
        for item in blocked_rows:
            for blocker in self._split_tags(str(item.get("exact_blockers") or "")):
                first_batch_blockers[blocker] += 1
        lines = [
            "# Product quality split v2 blocker diagnosis final report",
            "",
            "1. Why first batch had 0 clean candidates:",
            f"   - blocker distribution in first batch dry-run: {dict(first_batch_blockers)}",
            "   - dominant blocker: unresolved new Auto_DB supplier for move brand (brand_display_conflict_unresolved_new_autodb_supplier).",
            f"2. Resolved-brand clean candidates among all source rows: {search_decisions.get('selected_for_resolved_batch', 0)} pre-dry candidates.",
            f"3. Clean candidates after resolved-brand dry-run: {dry_summary.get('clean', 0)}",
            f"4. Recommended first apply batch size: {dry_summary.get('recommended_first_apply_batch_size', 0)}",
            f"5. Display-only brand policy needed: {'yes' if search_decisions.get('needs_brand_resolution', 0) > 0 else 'optional'}",
            f"6. Approval package path: /tmp/product_quality_split_v2_resolved_brand_apply_approval.csv (+.xlsx/.md), rows={approval_count}",
            "7. Confirmation no writes: yes (read-only diagnostics/dry-run only).",
            "",
            "## Diagnostics Counts",
            f"- blocked_batch_rows_diagnosed: {len(blocked_rows)}",
            f"- search_decisions: {dict(search_decisions)}",
            "",
        ]
        (self.out / "product_quality_split_v2_blocker_diagnosis_final_report.md").write_text("\n".join(lines), encoding="utf-8")

    def _parse_groups(self, raw: str) -> list[SplitGroup]:
        groups: list[SplitGroup] = []
        for chunk in [item.strip() for item in str(raw or "").split(";") if item.strip()]:
            match = GROUP_RE.match(chunk)
            if not match:
                continue
            label = str(match.group("label") or "").strip()
            if "|" in label:
                brand_raw, article = label.split("|", 1)
            else:
                brand_raw, article = label, ""
            ids = tuple(sorted({item.strip() for item in str(match.group("ids") or "").split(",") if item.strip()}))
            groups.append(
                SplitGroup(
                    raw=chunk,
                    label=label,
                    brand_raw=str(brand_raw or "").strip(),
                    brand_norm=normalize_brand(str(brand_raw or "")),
                    article_canonical=self._canonical_article(article),
                    count=int(match.group("count") or 0),
                    offer_ids=ids,
                )
            )
        return groups

    def _pick_keep_move(self, *, groups: list[SplitGroup], product: Product, bucket_row: dict[str, str]) -> tuple[SplitGroup | None, SplitGroup | None]:
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
                rest = [item for item in groups if item != keep]
                if rest:
                    move = sorted(rest, key=lambda item: (item.count, len(item.offer_ids)))[0]

        outliers = set(self._split_ids(str(bucket_row.get("outlier_offer_ids") or "")))
        if outliers:
            ranked = sorted(
                groups,
                key=lambda item: len(outliers.intersection(set(item.offer_ids))),
                reverse=True,
            )
            if ranked and len(outliers.intersection(set(ranked[0].offer_ids))) > 0:
                move = ranked[0]
                rest = [item for item in groups if item != move]
                if rest:
                    keep = sorted(rest, key=lambda item: (item.count, len(item.offer_ids)), reverse=True)[0]
        if keep == move:
            return None, None
        return keep, move

    def _brand_name_by_norm(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in Brand.objects.all().only("name"):
            norm = normalize_brand(str(row.name or ""))
            if norm and norm not in out:
                out[norm] = str(row.name or "")
        return out

    def _first_group(self, value: str) -> SplitGroup | None:
        rows = self._parse_groups(value)
        if rows:
            return rows[0]
        return None

    def _count_by_product(self, rows: Any) -> dict[str, int]:
        return {str(item["product_id"]): int(item["c"] or 0) for item in rows}

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
        out: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            b = before.get(key)
            a = after.get(key)
            delta: Any = ""
            try:
                delta = (a or 0) - (b or 0)
            except Exception:
                delta = ""
            out.append({"metric": key, "before": b, "after": a, "delta": delta, "changed": b != a})
        return out

    def _split_ids(self, value: str) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    def _split_tags(self, value: str) -> list[str]:
        return [item.strip() for item in str(value or "").split(";") if item.strip()]

    def _canonical_article(self, value: str) -> str:
        return "".join(ch for ch in str(value or "").upper() if ch.isalnum())

    def _as_bool(self, value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}

    def _as_float(self, value: Any) -> float:
        try:
            return float(str(value or "").strip() or "0")
        except Exception:
            return 0.0
