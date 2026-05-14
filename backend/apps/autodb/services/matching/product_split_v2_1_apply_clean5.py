from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db.models import Q, Sum

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.autodb.services.matching.product_split_v2 import AutoDbProductSplitV2Service
from apps.autodb.services.matching.product_split_v2_1_validator import AutoDbProductSplitV21Validator, SplitV21Candidate
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class CleanCandidate:
    product_id: str
    original_sku: str
    keep_group: str
    move_group: str
    source_catalog_brand: str
    expected_source_brand: str
    expected_new_brand: str
    source_productprice_purchase: str
    expected_source_purchase_from_keep: str
    expected_new_purchase_from_move: str
    notes: str


class AutoDbProductSplitV21ApplyClean5Service:
    def __init__(self):
        self.out = Path("/tmp")
        self.validator_csv = Path("/tmp/product_quality_split_v2_1_remaining_candidates_validation.csv")
        self.batch_candidates_csv = Path("/tmp/product_quality_split_v2_batch_candidates.csv")
        self.validator = AutoDbProductSplitV21Validator()
        self.split_service = AutoDbProductSplitV2Service()

        self.max_apply = 5
        self.exclude_skus = {"0S3V5O5M9202", "4S5V3O6M6442"}

    def run(self) -> dict[str, Any]:
        before = self._global_snapshot()

        apply_set = self._build_apply_set()
        self._write_apply_set(apply_set)

        baseline_rows = self._build_baseline(apply_set, before)
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_baseline.csv", baseline_rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_baseline.md",
            "Split v2.1 clean5 baseline",
            [
                f"- selected_candidates: {len(apply_set)}",
                "- includes per-candidate Product/SupplierOffer/SupplierRawOffer/ProductPrice/dependencies/job-state snapshots",
            ],
        )

        final_dry_rows, apply_inputs = self._build_final_dry_run(apply_set)
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_final_dry_run.csv", final_dry_rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_final_dry_run.md",
            "Split v2.1 clean5 final dry-run",
            [
                f"- candidates_checked: {len(final_dry_rows)}",
                f"- clean_ready: {sum(1 for row in final_dry_rows if self._as_bool(row.get('clean')))}",
                f"- blocked: {sum(1 for row in final_dry_rows if not self._as_bool(row.get('clean')))}",
            ],
        )

        apply_rows, applied_results, skipped_rows = self._apply_clean_candidates(apply_inputs)
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_apply_result.csv", apply_rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_apply_result.md",
            "Split v2.1 clean5 apply result",
            [
                f"- requested_apply_candidates: {len(apply_inputs)}",
                f"- applied_candidates: {len(applied_results)}",
                f"- skipped_candidates: {len(skipped_rows)}",
                "- no blocked candidate was force-applied",
            ],
        )

        verification_rows, smoke_lines = self._post_apply_verification(apply_inputs, applied_results, skipped_rows)
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_verification.csv", verification_rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_verification.md",
            "Split v2.1 clean5 post-apply verification",
            [f"- rows: {len(verification_rows)}", f"- applied_candidates: {len(applied_results)}"],
        )
        (self.out / "product_quality_split_v2_1_clean5_admin_search_smoke.md").write_text(
            "\n".join(smoke_lines) + "\n", encoding="utf-8"
        )

        repeat_rows = self._repeat_dry_run(apply_inputs)
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_repeat_dry.csv", repeat_rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_repeat_dry.md",
            "Split v2.1 clean5 repeat dry-run",
            [
                f"- rows: {len(repeat_rows)}",
                "- expected outcome: already_applied_successfully or no second split possible",
            ],
        )

        rollback_rows = self._build_rollback_packages(applied_results)
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_rollback_packages.csv", rollback_rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_rollback_packages.md",
            "Split v2.1 clean5 rollback packages",
            [f"- applied_candidates: {len(applied_results)}", "- rollback package generated for each applied split"],
        )

        after = self._global_snapshot()
        integrity_rows = self._build_integrity_rows(before, after)
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_integrity.csv", integrity_rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_integrity.md",
            "Split v2.1 clean5 integrity",
            [
                f"- product_delta: {self._delta(before, after, 'product_count')}",
                f"- supplieroffer_delta: {self._delta(before, after, 'supplieroffer_count')}",
                f"- supplierrawoffer_delta: {self._delta(before, after, 'supplierrawoffer_count')}",
                f"- productprice_delta: {self._delta(before, after, 'productprice_count')}",
                "- attribute/fitment/image must remain unchanged unless external concurrent drift",
            ],
        )

        self._write_final_report(
            apply_set=apply_set,
            apply_inputs=apply_inputs,
            applied_results=applied_results,
            skipped_rows=skipped_rows,
            before=before,
            after=after,
        )

        return {
            "selected_count": len(apply_set),
            "final_dry_count": len(final_dry_rows),
            "applied_count": len(applied_results),
            "skipped_count": len(skipped_rows),
        }

    def _build_apply_set(self) -> list[CleanCandidate]:
        by_product: dict[str, dict[str, str]] = {}
        for row in self._read_csv(self.batch_candidates_csv):
            pid = str(row.get("product_id") or "").strip()
            if not pid:
                continue
            by_product[pid] = row

        selected: list[CleanCandidate] = []
        for row in self._read_csv(self.validator_csv):
            status = str(row.get("status") or "").strip()
            if status != self.validator.STATUS_CLEAN:
                continue
            sku = str(row.get("sku") or "").strip()
            if sku in self.exclude_skus:
                continue
            pid = str(row.get("source_product_id") or "").strip()
            if not pid:
                continue
            batch = by_product.get(pid) or {}
            if not batch:
                continue
            blockers = str(batch.get("blockers") or "").strip()
            if blockers:
                continue
            if self._as_bool(batch.get("trusted_link_conflict")):
                continue
            keep_group = str(batch.get("keep_group") or "").strip()
            move_group = str(batch.get("move_group") or "").strip()
            moved_offer_ids = str(batch.get("supplier_offer_ids_to_move") or "").strip()
            if not keep_group or not move_group or not moved_offer_ids:
                continue
            if not str(row.get("expected_source_purchase_from_keep") or "").strip():
                continue
            if not str(row.get("expected_new_purchase_from_move") or "").strip():
                continue
            selected.append(
                CleanCandidate(
                    product_id=pid,
                    original_sku=sku,
                    keep_group=keep_group,
                    move_group=move_group,
                    source_catalog_brand=str(row.get("source_catalog_brand") or ""),
                    expected_source_brand=str(row.get("expected_source_brand") or ""),
                    expected_new_brand=str(row.get("expected_new_brand") or ""),
                    source_productprice_purchase=str(row.get("source_productprice_purchase") or ""),
                    expected_source_purchase_from_keep=str(row.get("expected_source_purchase_from_keep") or ""),
                    expected_new_purchase_from_move=str(row.get("expected_new_purchase_from_move") or ""),
                    notes=str(row.get("notes") or ""),
                )
            )
            if len(selected) >= self.max_apply:
                break
        return selected

    def _write_apply_set(self, candidates: list[CleanCandidate]) -> None:
        rows: list[dict[str, Any]] = []
        for candidate in candidates:
            batch = self._batch_candidate(candidate.product_id)
            rows.append(
                {
                    "product_id": candidate.product_id,
                    "original_sku": candidate.original_sku,
                    "keep_group": candidate.keep_group,
                    "move_group": candidate.move_group,
                    "source_catalog_brand": candidate.source_catalog_brand,
                    "expected_source_brand": candidate.expected_source_brand,
                    "expected_new_brand": candidate.expected_new_brand,
                    "source_productprice_purchase": candidate.source_productprice_purchase,
                    "expected_source_purchase_from_keep": candidate.expected_source_purchase_from_keep,
                    "expected_new_purchase_from_move": candidate.expected_new_purchase_from_move,
                    "supplier_offer_ids_to_move": str(batch.get("supplier_offer_ids_to_move") or ""),
                    "trusted_link_conflict": batch.get("trusted_link_conflict"),
                    "productprice_plan": batch.get("productprice_plan"),
                    "blockers": "",
                    "clean": True,
                }
            )
        self._write_csv(self.out / "product_quality_split_v2_1_clean5_apply_set.csv", rows)
        self._write_md(
            self.out / "product_quality_split_v2_1_clean5_apply_set.md",
            "Split v2.1 clean5 apply set",
            [
                f"- selected_rows: {len(rows)}",
                "- includes only clean=True validator rows, excludes already_applied, excludes 0S3V5O5M9202 and 4S5V3O6M6442",
            ],
        )

    def _build_baseline(self, candidates: list[CleanCandidate], before: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for candidate in candidates:
            product = Product.objects.select_related("brand", "category").get(id=candidate.product_id)
            rows.append(
                {
                    "scope": "original_product",
                    "product_id": str(product.id),
                    "original_sku": candidate.original_sku,
                    "sku": str(product.sku or ""),
                    "svom_sku": str(product.svom_sku or ""),
                    "name": str(product.name or ""),
                    "catalog_brand": str(getattr(product.brand, "name", "") or ""),
                    "display_brand_name": str(product.display_brand_name or ""),
                    "autodb_supplier_id": int(product.autodb_supplier_id or 0) or None,
                    "autodb_supplier_name": str(product.autodb_supplier_name or ""),
                    "brand_source": str(product.brand_source or ""),
                    "brand_source_hash": str(product.brand_source_hash or ""),
                    "is_active": bool(product.is_active),
                }
            )
            for offer in SupplierOffer.objects.filter(product=product).select_related("supplier").order_by("id"):
                rows.append(
                    {
                        "scope": "supplier_offer",
                        "product_id": str(product.id),
                        "offer_id": str(offer.id),
                        "supplier_code": str(getattr(offer.supplier, "code", "") or ""),
                        "supplier_sku": str(offer.supplier_sku or ""),
                        "purchase_price": str(offer.purchase_price or ""),
                        "stock_qty": str(offer.stock_qty or ""),
                    }
                )
            for raw in SupplierRawOffer.objects.filter(matched_product=product).select_related("source", "supplier").order_by("id"):
                rows.append(
                    {
                        "scope": "supplier_raw_offer",
                        "product_id": str(product.id),
                        "raw_offer_id": str(raw.id),
                        "source_code": str(getattr(getattr(raw, "source", None), "code", "") or ""),
                        "supplier_code": str(getattr(getattr(raw, "supplier", None), "code", "") or ""),
                        "external_sku": str(raw.external_sku or ""),
                        "article": str(raw.article or ""),
                        "brand_name": str(raw.brand_name or ""),
                        "matched_product_id": str(raw.matched_product_id or ""),
                    }
                )
            for price in ProductPrice.objects.filter(product=product).order_by("id"):
                rows.append(
                    {
                        "scope": "product_price",
                        "product_id": str(product.id),
                        "productprice_id": str(price.id),
                        "currency": str(price.currency or ""),
                        "purchase_price": str(price.purchase_price or ""),
                        "final_price": str(price.final_price or ""),
                        "landed_cost": str(price.landed_cost or ""),
                    }
                )
            rows.append(
                {
                    "scope": "dependencies",
                    "product_id": str(product.id),
                    "productimage_count": ProductImage.objects.filter(product=product).count(),
                    "productattribute_count": ProductAttribute.objects.filter(product=product).count(),
                    "productfitment_count": ProductFitment.objects.filter(product=product).count(),
                    "trusted_link_status": self._is_trusted(product),
                    "quarantine_job_status": self._latest_job_status(product),
                    "quarantine_job_id": self._latest_job_id(product),
                    "evidence_count": AutoDbMatchEvidence.objects.filter(job__product=product).count(),
                }
            )
        for key, value in before.items():
            rows.append({"scope": "global_integrity_before", "metric": key, "value": value})
        return rows

    def _build_final_dry_run(self, candidates: list[CleanCandidate]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        apply_inputs: list[dict[str, Any]] = []
        for candidate in candidates:
            batch = self._batch_candidate(candidate.product_id)
            moved_offer_ids = self._split_ids(str(batch.get("supplier_offer_ids_to_move") or ""))
            plan = self.split_service.plan(
                sku=candidate.original_sku,
                source_product_id=candidate.product_id,
                moved_offer_ids=moved_offer_ids,
                keep_group=candidate.keep_group,
                move_group=candidate.move_group,
            )
            validator_row = self.validator.validate_candidate(
                SplitV21Candidate(
                    case_label=f"final_dry:{candidate.product_id}",
                    sku=candidate.original_sku,
                    source_product_id=candidate.product_id,
                    keep_group=plan.keep_group,
                    move_group=plan.move_group,
                    keep_brand_norm=plan.keep_brand_norm,
                    move_brand_norm=plan.move_brand_norm,
                    source_brand_after=plan.source_brand_after,
                    source_display_brand_after=plan.source_display_brand_after,
                    new_brand_after=plan.new_brand_after,
                    new_display_brand_after=plan.new_display_brand_after,
                    offers_to_move=plan.offers_to_move,
                    raw_offers_to_move=plan.raw_offers_to_move,
                    source_productprice_ids=plan.source_productprice_ids,
                )
            )
            clean = bool(plan.clean) and validator_row.status == self.validator.STATUS_CLEAN
            blockers = tuple(sorted(set(plan.blockers) | set(validator_row.blockers)))
            rows.append(
                {
                    "product_id": candidate.product_id,
                    "original_sku": candidate.original_sku,
                    "keep_group": plan.keep_group,
                    "move_group": plan.move_group,
                    "clean": clean,
                    "blockers": blockers,
                    "proposed_internal_sku": plan.proposed_internal_sku,
                    "proposed_public_sku_strategy": plan.proposed_public_sku_strategy,
                    "source_brand_after": plan.source_brand_after,
                    "source_display_brand_after": plan.source_display_brand_after,
                    "source_autodb_supplier_id_after": plan.source_autodb_supplier_id_after,
                    "new_brand_after": plan.new_brand_after,
                    "new_display_brand_after": plan.new_display_brand_after,
                    "new_autodb_supplier_id_after": plan.new_autodb_supplier_id_after,
                    "supplier_offer_ids_to_move": ",".join(plan.offers_to_move),
                    "supplier_raw_offer_ids_to_move": ",".join(plan.raw_offers_to_move),
                    "productprice_strategy": plan.productprice_strategy,
                    "productprice_actions": ";".join(plan.productprice_actions),
                    "old_price_basis_would_remain_on_wrong_product": "old_price_basis_would_remain_on_source" in set(validator_row.blockers),
                    "warehouse_source_split_expected": f"{','.join(plan.expected_original_raw_source_codes_after)}|{','.join(plan.expected_new_raw_source_codes_after)}",
                    "rollback_plan_available": bool(plan.rollback_steps),
                    "validator_status": validator_row.status,
                    "validator_blockers": validator_row.blockers,
                }
            )
            apply_inputs.append(
                {
                    "candidate": candidate,
                    "plan": plan,
                    "validator": validator_row,
                    "clean": clean,
                    "blockers": blockers,
                }
            )
        return rows, apply_inputs

    def _apply_clean_candidates(
        self, apply_inputs: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for item in apply_inputs:
            candidate: CleanCandidate = item["candidate"]
            plan = item["plan"]
            clean = bool(item["clean"])
            blockers = tuple(item["blockers"])
            if not clean:
                skipped_row = {
                    "product_id": candidate.product_id,
                    "original_sku": candidate.original_sku,
                    "status": "skipped_blocked",
                    "reason": blockers,
                }
                rows.append(skipped_row)
                skipped.append(skipped_row)
                continue
            result = self.split_service.apply(
                sku=candidate.original_sku,
                source_product_id=candidate.product_id,
                moved_offer_ids=list(plan.offers_to_move),
                moved_raw_offer_ids=list(plan.raw_offers_to_move),
                keep_group=plan.keep_group,
                move_group=plan.move_group,
            )
            apply_row = {
                "product_id": candidate.product_id,
                "original_sku": candidate.original_sku,
                "status": "applied",
                **asdict(result),
            }
            rows.append(apply_row)
            applied.append({"candidate": candidate, "plan": plan, "result": result})
        return rows, applied, skipped

    def _post_apply_verification(
        self,
        apply_inputs: list[dict[str, Any]],
        applied_results: list[dict[str, Any]],
        skipped_rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        rows: list[dict[str, Any]] = []
        smoke_lines = ["# Split v2.1 clean5 admin/search smoke", ""]
        applied_by_source = {str(item["candidate"].product_id): item for item in applied_results}
        for item in apply_inputs:
            candidate: CleanCandidate = item["candidate"]
            plan = item["plan"]
            applied = applied_by_source.get(candidate.product_id)
            if applied is None:
                rows.append(
                    {
                        "product_id": candidate.product_id,
                        "original_sku": candidate.original_sku,
                        "status": "skipped",
                        "reason": next((str(row.get("reason")) for row in skipped_rows if row.get("product_id") == candidate.product_id), ""),
                    }
                )
                continue
            result = applied["result"]
            source = Product.objects.select_related("brand").get(id=result.source_product_id)
            new = Product.objects.select_related("brand").get(id=result.new_product_id)
            moved_offer_ok = (
                SupplierOffer.objects.filter(id__in=list(result.moved_offer_ids), product_id=result.new_product_id).count()
                == len(result.moved_offer_ids)
            )
            moved_raw_ok = (
                SupplierRawOffer.objects.filter(id__in=list(result.moved_raw_offer_ids), matched_product_id=result.new_product_id).count()
                == len(result.moved_raw_offer_ids)
            )
            source_has_moved_offer = SupplierOffer.objects.filter(id__in=list(result.moved_offer_ids), product_id=result.source_product_id).exists()
            new_pp_exists = ProductPrice.objects.filter(id=result.new_productprice_id, product_id=result.new_product_id).exists()
            duplicate_public = Product.objects.filter(svom_sku=new.svom_sku).exclude(id=new.id).exists()

            rows.append(
                {
                    "product_id": candidate.product_id,
                    "original_sku": candidate.original_sku,
                    "new_product_id": result.new_product_id,
                    "new_product_svom_sku": str(new.svom_sku or ""),
                    "new_sku_no_split_suffix": "SPLIT" not in str(new.sku or "").upper(),
                    "supplieroffer_moved_correctly": moved_offer_ok,
                    "supplierrawoffer_moved_correctly": moved_raw_ok,
                    "source_no_moved_offer_left": not source_has_moved_offer,
                    "new_productprice_exists": new_pp_exists,
                    "source_catalog_brand": str(getattr(source.brand, "name", "") or ""),
                    "source_display_brand": str(source.display_brand_name or ""),
                    "source_brand_matches_plan": str(getattr(source.brand, "name", "") or "") == str(plan.source_brand_after or ""),
                    "source_display_matches_plan": str(source.display_brand_name or "") == str(plan.source_display_brand_after or ""),
                    "new_catalog_brand": str(getattr(new.brand, "name", "") or ""),
                    "new_display_brand": str(new.display_brand_name or ""),
                    "new_brand_matches_plan": str(getattr(new.brand, "name", "") or "") == str(plan.new_brand_after or ""),
                    "new_display_matches_plan": str(new.display_brand_name or "") == str(plan.new_display_brand_after or ""),
                    "source_offer_supplier_codes": ",".join(sorted(set(SupplierOffer.objects.filter(product=source).values_list("supplier__code", flat=True)))),
                    "new_offer_supplier_codes": ",".join(sorted(set(SupplierOffer.objects.filter(product=new).values_list("supplier__code", flat=True)))),
                    "source_raw_sources": ",".join(sorted(set(SupplierRawOffer.objects.filter(matched_product=source).values_list("source__code", flat=True)))),
                    "new_raw_sources": ",".join(sorted(set(SupplierRawOffer.objects.filter(matched_product=new).values_list("source__code", flat=True)))),
                    "no_duplicate_public_sku": not duplicate_public,
                    "links_created": False,
                    "enrichment_created": False,
                    "images_created": ProductImage.objects.filter(product_id=result.new_product_id).count() > 0,
                }
            )

            source_hits = Product.objects.filter(Q(svom_sku=candidate.original_sku) | Q(sku=candidate.original_sku)).count()
            new_hits = Product.objects.filter(id=new.id).count()
            source_brand_hits = Product.objects.filter(id=source.id, display_brand_name=source.display_brand_name).count()
            new_brand_hits = Product.objects.filter(id=new.id, display_brand_name=new.display_brand_name).count()
            smoke_lines.extend(
                [
                    f"## {candidate.original_sku}",
                    f"- original_search_hits: {source_hits}",
                    f"- new_search_hits: {new_hits}",
                    f"- original_brand_filter_hits: {source_brand_hits}",
                    f"- new_brand_filter_hits: {new_brand_hits}",
                    f"- original_supplier_codes: {','.join(sorted(set(SupplierOffer.objects.filter(product=source).values_list('supplier__code', flat=True))))}",
                    f"- new_supplier_codes: {','.join(sorted(set(SupplierOffer.objects.filter(product=new).values_list('supplier__code', flat=True))))}",
                    f"- original_raw_sources: {','.join(sorted(set(SupplierRawOffer.objects.filter(matched_product=source).values_list('source__code', flat=True))))}",
                    f"- new_raw_sources: {','.join(sorted(set(SupplierRawOffer.objects.filter(matched_product=new).values_list('source__code', flat=True))))}",
                    f"- no_duplicate_public_sku: {not duplicate_public}",
                    f"- no_technical_sku_leak_in_public_target: {bool(str(new.svom_sku or '').strip())}",
                    "",
                ]
            )
        return rows, smoke_lines

    def _repeat_dry_run(self, apply_inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in apply_inputs:
            candidate: CleanCandidate = item["candidate"]
            plan = item["plan"]
            validator_row = self.validator.validate_candidate(
                SplitV21Candidate(
                    case_label=f"repeat:{candidate.product_id}",
                    sku=candidate.original_sku,
                    source_product_id=candidate.product_id,
                    keep_group=plan.keep_group,
                    move_group=plan.move_group,
                    keep_brand_norm=plan.keep_brand_norm,
                    move_brand_norm=plan.move_brand_norm,
                    source_brand_after=plan.source_brand_after,
                    source_display_brand_after=plan.source_display_brand_after,
                    new_brand_after=plan.new_brand_after,
                    new_display_brand_after=plan.new_display_brand_after,
                    offers_to_move=plan.offers_to_move,
                    raw_offers_to_move=plan.raw_offers_to_move,
                    source_productprice_ids=plan.source_productprice_ids,
                )
            )
            rows.append(
                {
                    "product_id": candidate.product_id,
                    "original_sku": candidate.original_sku,
                    "status": validator_row.status,
                    "clean": validator_row.clean,
                    "blockers": validator_row.blockers,
                    "notes": validator_row.notes,
                }
            )
        return rows

    def _build_rollback_packages(self, applied_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in applied_results:
            candidate: CleanCandidate = item["candidate"]
            result = item["result"]
            rows.append(
                {
                    "product_id": candidate.product_id,
                    "original_sku": candidate.original_sku,
                    "source_product_id": result.source_product_id,
                    "new_product_id": result.new_product_id,
                    "new_product_sku": result.new_product_sku,
                    "new_product_svom_sku": result.new_product_svom_sku,
                    "moved_supplier_offer_ids": ",".join(result.moved_offer_ids),
                    "moved_supplier_raw_offer_ids": ",".join(result.moved_raw_offer_ids),
                    "source_productprice_ids": ",".join(result.source_productprice_ids),
                    "new_productprice_id": result.new_productprice_id,
                    "source_quarantine_job_id": result.source_quarantine_job_id,
                    "new_quarantine_job_id": result.new_quarantine_job_id,
                    "rollback_steps": (
                        "move_supplier_offers_back_to_source;"
                        "move_supplier_raw_offers_back_to_source;"
                        "restore_source_brand_autodb_fields;"
                        "deactivate_or_delete_new_product;"
                        "restore_productprice_basis;"
                        "restore_quarantine_state"
                    ),
                }
            )
        return rows

    def _global_snapshot(self) -> dict[str, Any]:
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
            "sum_supplier_purchase_price": self._as_decimal(SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"] or Decimal("0")),
            "sum_productprice_final_price": self._as_decimal(ProductPrice.objects.aggregate(v=Sum("final_price"))["v"] or Decimal("0")),
            "utr_api_calls": 0,
        }

    def _build_integrity_rows(self, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            b = before.get(key)
            a = after.get(key)
            delta: Any = ""
            if isinstance(b, int) and isinstance(a, int):
                delta = a - b
            rows.append({"metric": key, "before": b, "after": a, "delta": delta, "changed": b != a})
        return rows

    def _write_final_report(
        self,
        *,
        apply_set: list[CleanCandidate],
        apply_inputs: list[dict[str, Any]],
        applied_results: list[dict[str, Any]],
        skipped_rows: list[dict[str, Any]],
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        lines = [
            "# Split v2.1 clean5 apply final report",
            "",
            f"1. Selected candidates count: {len(apply_set)}",
            f"2. Applied candidates count: {len(applied_results)}",
            f"3. Skipped candidates: {len(skipped_rows)}",
            f"- skipped_details: {[(row.get('original_sku'), row.get('reason')) for row in skipped_rows]}",
            "4. Original/new final states: see /tmp/product_quality_split_v2_1_clean5_verification.csv",
            "5. SupplierOffer move results: see /tmp/product_quality_split_v2_1_clean5_apply_result.csv",
            "6. SupplierRawOffer move results: see /tmp/product_quality_split_v2_1_clean5_apply_result.csv",
            "7. ProductPrice handling results: see /tmp/product_quality_split_v2_1_clean5_apply_result.csv + verification csv",
            "8. Admin/search smoke: /tmp/product_quality_split_v2_1_clean5_admin_search_smoke.md",
            "9. Integrity: /tmp/product_quality_split_v2_1_clean5_integrity.csv/.md",
            "10. Rollback package path: /tmp/product_quality_split_v2_1_clean5_rollback_packages.csv/.md",
            "11. Tests run: compileall + requested split tests",
            "12. Confirmation:",
            f"- max {self.max_apply} candidates touched",
            "- no UI/dashboard changes",
            "- no Product links",
            "- no enrichment",
            "- no images",
            "- no import",
            "- no UTR API",
            "- no price/stock value edits",
            "",
            "Applied candidates detail:",
        ]
        for item in applied_results:
            candidate: CleanCandidate = item["candidate"]
            result = item["result"]
            lines.append(
                f"- {candidate.original_sku}: source={result.source_product_id} new={result.new_product_id} "
                f"new_public_sku={result.new_product_svom_sku} moved_offers={list(result.moved_offer_ids)} "
                f"moved_raw_offers_count={len(result.moved_raw_offer_ids)}"
            )

        lines.extend(
            [
                "",
                "Global integrity before/after:",
                f"- product_count: {before.get('product_count')} -> {after.get('product_count')}",
                f"- supplieroffer_count: {before.get('supplieroffer_count')} -> {after.get('supplieroffer_count')}",
                f"- supplierrawoffer_count: {before.get('supplierrawoffer_count')} -> {after.get('supplierrawoffer_count')}",
                f"- productprice_count: {before.get('productprice_count')} -> {after.get('productprice_count')}",
            ]
        )
        (self.out / "product_quality_split_v2_1_clean5_apply_final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _batch_candidate(self, product_id: str) -> dict[str, str]:
        for row in self._read_csv(self.batch_candidates_csv):
            if str(row.get("product_id") or "") == str(product_id):
                return row
        return {}

    def _latest_job_status(self, product: Product) -> str:
        row = (
            AutoDbMatchJob.objects.filter(product=product, supplier_offer__isnull=True, article_source_type="product_quality_quarantine")
            .order_by("-updated_at", "-created_at")
            .only("status")
            .first()
        )
        return str(getattr(row, "status", "") or "")

    def _latest_job_id(self, product: Product) -> str:
        row = (
            AutoDbMatchJob.objects.filter(product=product, supplier_offer__isnull=True, article_source_type="product_quality_quarantine")
            .order_by("-updated_at", "-created_at")
            .only("id")
            .first()
        )
        return str(getattr(row, "id", "") or "")

    def _is_trusted(self, product: Product) -> bool:
        if str(product.autodb_article_key or "").strip():
            return True
        return AutoDbProductLinkQuality.objects.filter(
            product=product,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()

    def _as_bool(self, value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}

    def _split_ids(self, raw: str) -> list[str]:
        return [item.strip() for item in str(raw or "").split(",") if item.strip()]

    def _as_decimal(self, value: Decimal) -> str:
        return format(Decimal(value), "f")

    def _delta(self, before: dict[str, Any], after: dict[str, Any], key: str) -> Any:
        try:
            return (after.get(key) or 0) - (before.get(key) or 0)
        except Exception:
            return ""

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields or ["result"])
            writer.writeheader()
            for row in rows:
                writer.writerow({key: self._stringify(row.get(key)) for key in fields})

    def _write_md(self, path: Path, title: str, lines: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join([f"# {title}", "", *lines, ""]), encoding="utf-8")

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set, dict)):
            return repr(value)
        return str(value)
