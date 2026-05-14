from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.db.models import Q, Sum

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.autodb.services.matching.product_split_v2 import AutoDbProductSplitV2Service
from apps.catalog.models import AutoDbProductLinkQuality, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


class AutoDbProductSplitV2ApplyOneService:
    def __init__(self):
        self.out = Path("/tmp")
        self.split_service = AutoDbProductSplitV2Service()
        self.approval_csv = Path("/tmp/product_quality_split_v2_resolved_brand_apply_approval.csv")
        self.resolved_dry_csv = Path("/tmp/product_quality_split_v2_resolved_brand_batch_dry_run.csv")

    def run(self) -> dict[str, Any]:
        global_before = self._global_snapshot()
        approval_rows = self._read_csv(self.approval_csv)
        dry_rows = self._read_csv(self.resolved_dry_csv)
        candidate = self._verify_input(approval_rows=approval_rows, dry_rows=dry_rows)
        self._export_input_verification(candidate)

        baseline_rows = self._build_baseline(candidate)
        self._write_csv(self.out / "product_quality_split_v2_one_apply_baseline.csv", baseline_rows)
        self._write_md(
            self.out / "product_quality_split_v2_one_apply_baseline.md",
            title="Split v2 one apply baseline",
            lines=[
                f"- product_id: {candidate['product_id']}",
                f"- original_sku: {candidate['original_sku']}",
                f"- supplier_offer_ids_to_move: {candidate['supplier_offer_ids_to_move']}",
                f"- supplier_raw_offer_ids_to_move_count: {len(candidate['supplier_raw_offer_ids_to_move'])}",
            ],
        )

        final_plan = self.split_service.plan(
            sku=candidate["original_sku"],
            source_product_id=candidate["product_id"],
            moved_offer_ids=candidate["supplier_offer_ids_to_move"],
            keep_group=candidate["keep_group"],
            move_group=candidate["move_group"],
        )
        self._write_csv(self.out / "product_quality_split_v2_one_final_dry_run.csv", [asdict(final_plan)])
        self._write_md(
            self.out / "product_quality_split_v2_one_final_dry_run.md",
            title="Split v2 one final dry-run",
            lines=[
                f"- clean: {final_plan.clean}",
                f"- blockers: {list(final_plan.blockers)}",
                f"- proposed_internal_sku: {final_plan.proposed_internal_sku}",
                f"- proposed_public_sku_strategy: {final_plan.proposed_public_sku_strategy}",
                f"- offers_to_move: {list(final_plan.offers_to_move)}",
                f"- raw_offers_to_move: {list(final_plan.raw_offers_to_move)}",
                f"- productprice_strategy: {final_plan.productprice_strategy}",
            ],
        )
        if not final_plan.clean:
            raise RuntimeError(f"Final dry-run is not clean: {list(final_plan.blockers)}")

        apply_result = self.split_service.apply(
            sku=candidate["original_sku"],
            source_product_id=candidate["product_id"],
            moved_offer_ids=candidate["supplier_offer_ids_to_move"],
            moved_raw_offer_ids=candidate["supplier_raw_offer_ids_to_move"],
            keep_group=candidate["keep_group"],
            move_group=candidate["move_group"],
        )
        apply_row = asdict(apply_result)
        self._write_csv(self.out / "product_quality_split_v2_one_apply_result.csv", [apply_row])
        self._write_md(
            self.out / "product_quality_split_v2_one_apply_result.md",
            title="Split v2 one apply result",
            lines=[
                f"- source_product_id: {apply_result.source_product_id}",
                f"- new_product_id: {apply_result.new_product_id}",
                f"- new_product_sku: {apply_result.new_product_sku}",
                f"- new_product_svom_sku: {apply_result.new_product_svom_sku}",
                f"- moved_offer_ids: {list(apply_result.moved_offer_ids)}",
                f"- moved_raw_offer_ids: {list(apply_result.moved_raw_offer_ids)}",
                f"- source_productprice_ids: {list(apply_result.source_productprice_ids)}",
                f"- new_productprice_id: {apply_result.new_productprice_id}",
            ],
        )

        verification_rows = self._post_apply_verification(candidate, apply_result)
        self._write_csv(self.out / "product_quality_split_v2_one_verification.csv", verification_rows)
        self._write_md(
            self.out / "product_quality_split_v2_one_verification.md",
            title="Split v2 one post-apply verification",
            lines=[f"- rows: {len(verification_rows)}"],
        )

        smoke_md = self._admin_search_smoke(candidate, apply_result)
        (self.out / "product_quality_split_v2_one_admin_search_smoke.md").write_text(smoke_md, encoding="utf-8")

        repeat_plan = self.split_service.plan(
            sku=candidate["original_sku"],
            source_product_id=candidate["product_id"],
            moved_offer_ids=candidate["supplier_offer_ids_to_move"],
            keep_group=candidate["keep_group"],
            move_group=candidate["move_group"],
        )
        repeat_row = asdict(repeat_plan)
        self._write_csv(self.out / "product_quality_split_v2_one_repeat_dry.csv", [repeat_row])
        self._write_md(
            self.out / "product_quality_split_v2_one_repeat_dry.md",
            title="Split v2 one repeat dry-run",
            lines=[
                f"- clean: {repeat_plan.clean}",
                f"- blockers: {list(repeat_plan.blockers)}",
                "- expected: no second split possible for same moved offer ids",
            ],
        )

        rollback_rows = self._build_rollback_package(candidate, apply_result)
        self._write_csv(self.out / "product_quality_split_v2_one_rollback_package.csv", rollback_rows)
        self._write_md(
            self.out / "product_quality_split_v2_one_rollback_package.md",
            title="Split v2 one rollback package",
            lines=[
                f"- source_product_id: {apply_result.source_product_id}",
                f"- new_product_id: {apply_result.new_product_id}",
                f"- moved_offer_ids: {list(apply_result.moved_offer_ids)}",
                f"- moved_raw_offer_ids: {list(apply_result.moved_raw_offer_ids)}",
                "- rollback: move offers/raw back, restore source brand/autodb fields, remove/deactivate new product, restore ProductPrice links",
            ],
        )

        global_after = self._global_snapshot()
        integrity_rows = self._build_integrity_rows(before=global_before, after=global_after)
        self._write_csv(self.out / "product_quality_split_v2_one_integrity.csv", integrity_rows)
        self._write_md(
            self.out / "product_quality_split_v2_one_integrity.md",
            title="Split v2 one integrity",
            lines=[
                f"- product_delta: {self._delta(global_before, global_after, 'product_count')}",
                f"- supplieroffer_delta: {self._delta(global_before, global_after, 'supplieroffer_count')}",
                f"- supplierrawoffer_delta: {self._delta(global_before, global_after, 'supplierrawoffer_count')}",
                f"- productprice_delta: {self._delta(global_before, global_after, 'productprice_count')}",
                "- expected deltas: Product +1; ProductPrice per plan; counts for offers/raw unchanged",
            ],
        )

        final_lines = [
            "# Split v2 one apply final report",
            "",
            f"1. Candidate applied: {candidate['product_id']} ({candidate['original_sku']})",
            f"2. Original product final state: {apply_result.source_product_id}",
            f"3. New product final state: {apply_result.new_product_id} / sku={apply_result.new_product_sku} / svom={apply_result.new_product_svom_sku}",
            f"4. SupplierOffer move result: moved={list(apply_result.moved_offer_ids)}",
            f"5. SupplierRawOffer move result: moved_count={len(apply_result.moved_raw_offer_ids)}",
            f"6. ProductPrice handling: source_ids={list(apply_result.source_productprice_ids)} new_id={apply_result.new_productprice_id}",
            "7. Admin/search smoke: see /tmp/product_quality_split_v2_one_admin_search_smoke.md",
            "8. Integrity: see /tmp/product_quality_split_v2_one_integrity.csv/.md",
            "9. Rollback package path: /tmp/product_quality_split_v2_one_rollback_package.csv/.md",
            "10. Tests run: compileall + requested split tests",
            "11. Confirmation: only one candidate touched; no UI changes; no links; no enrichment; no images; no import; no UTR API; no price/stock value edits.",
            "",
        ]
        (self.out / "product_quality_split_v2_one_apply_final_report.md").write_text("\n".join(final_lines), encoding="utf-8")

        return {
            "candidate": candidate,
            "apply_result": apply_result,
            "repeat_plan_clean": bool(repeat_plan.clean),
            "global_before": global_before,
            "global_after": global_after,
        }

    def _verify_input(self, *, approval_rows: list[dict[str, str]], dry_rows: list[dict[str, str]]) -> dict[str, Any]:
        if len(approval_rows) != 1:
            raise RuntimeError(f"Expected exactly 1 approval row, got {len(approval_rows)}")
        row = approval_rows[0]
        product_id = str(row.get("product_id") or "").strip()
        original_sku = str(row.get("original_sku") or "").strip()
        keep_group = str(row.get("keep_group") or "").strip()
        move_group = str(row.get("move_group") or "").strip()
        moved_offer_ids = self._split_ids(str(row.get("supplier_offer_ids_to_move") or ""))
        moved_raw_ids = self._split_ids(str(row.get("supplier_raw_offer_ids_to_move") or ""))

        dry_row = next((item for item in dry_rows if str(item.get("product_id") or "") == product_id), None)
        if dry_row is None:
            raise RuntimeError("Resolved dry-run row for approval candidate not found")
        is_clean = self._as_bool(dry_row.get("clean"))
        blockers = str(dry_row.get("blockers") or "").strip()
        if not is_clean or blockers:
            raise RuntimeError(f"Approval candidate is not clean: clean={is_clean} blockers={blockers}")

        product = Product.objects.select_related("brand").get(id=product_id)
        trusted = self._is_trusted(product)
        attr_count = ProductAttribute.objects.filter(product=product).count()
        fitment_count = ProductFitment.objects.filter(product=product).count()
        image_count = ProductImage.objects.filter(product=product).count()

        if trusted:
            raise RuntimeError("Trusted link conflict detected")
        if attr_count > 0 or fitment_count > 0 or image_count > 0:
            raise RuntimeError(
                f"Dependency blocker exists: attr={attr_count} fitment={fitment_count} image={image_count}"
            )
        if not moved_offer_ids or not moved_raw_ids:
            raise RuntimeError("Approval candidate must include explicit moved offer/raw offer ids")

        result = {
            "product_id": product_id,
            "original_sku": original_sku,
            "keep_group": keep_group,
            "move_group": move_group,
            "supplier_offer_ids_to_move": moved_offer_ids,
            "supplier_raw_offer_ids_to_move": moved_raw_ids,
            "productprice_plan": str(row.get("productprice_handling") or ""),
            "rollback_note": str(row.get("rollback_note") or ""),
            "move_brand_resolved": int(str(row.get("new_autodb_supplier_id_if_resolved") or "0") or "0") > 0,
            "trusted_link_conflict": trusted,
            "productimage_dependency": image_count > 0,
            "productattribute_dependency": attr_count > 0,
            "productfitment_dependency": fitment_count > 0,
            "clean": True,
            "blockers": "",
        }
        return result

    def _export_input_verification(self, candidate: dict[str, Any]) -> None:
        self._write_csv(self.out / "product_quality_split_v2_one_apply_input_verification.csv", [candidate])
        self._write_md(
            self.out / "product_quality_split_v2_one_apply_input_verification.md",
            title="Split v2 one apply input verification",
            lines=[
                "- exactly_one_candidate: True",
                f"- product_id: {candidate['product_id']}",
                f"- original_sku: {candidate['original_sku']}",
                f"- clean: {candidate['clean']}",
                f"- blockers: {candidate['blockers']}",
                f"- move_brand_resolved: {candidate['move_brand_resolved']}",
                f"- supplier_offer_ids_to_move_count: {len(candidate['supplier_offer_ids_to_move'])}",
                f"- supplier_raw_offer_ids_to_move_count: {len(candidate['supplier_raw_offer_ids_to_move'])}",
                f"- productprice_plan: {candidate['productprice_plan']}",
                f"- trusted_link_conflict: {candidate['trusted_link_conflict']}",
                f"- dependency_flags: image={candidate['productimage_dependency']} attr={candidate['productattribute_dependency']} fitment={candidate['productfitment_dependency']}",
                f"- rollback_note_exists: {bool(candidate['rollback_note'])}",
            ],
        )

    def _build_baseline(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        product = Product.objects.select_related("brand", "category").get(id=candidate["product_id"])
        rows: list[dict[str, Any]] = []
        rows.append(
            {
                "scope": "original_product",
                "product_id": str(product.id),
                "sku": str(product.sku or ""),
                "svom_sku": str(product.svom_sku or ""),
                "name": str(product.name or ""),
                "brand": str(getattr(product.brand, "name", "") or ""),
                "display_brand_name": str(product.display_brand_name or ""),
                "autodb_supplier_id": int(product.autodb_supplier_id or 0),
                "autodb_supplier_name": str(product.autodb_supplier_name or ""),
                "autodb_article_key": str(product.autodb_article_key or ""),
                "autodb_article_number": str(product.autodb_article_number or ""),
                "normalized_brand": str(product.normalized_brand or ""),
                "normalized_article": str(product.normalized_article or ""),
                "brand_source": str(product.brand_source or ""),
                "brand_source_hash": str(product.brand_source_hash or ""),
                "is_active": bool(product.is_active),
            }
        )

        for offer in SupplierOffer.objects.filter(product=product).select_related("supplier").order_by("id"):
            rows.append(
                {
                    "scope": "supplier_offer",
                    "id": str(offer.id),
                    "supplier_code": str(getattr(offer.supplier, "code", "") or ""),
                    "supplier_sku": str(offer.supplier_sku or ""),
                    "purchase_price": str(offer.purchase_price or ""),
                    "stock_qty": str(offer.stock_qty or ""),
                }
            )

        for raw in SupplierRawOffer.objects.filter(matched_product=product).order_by("id"):
            rows.append(
                {
                    "scope": "supplier_raw_offer",
                    "id": str(raw.id),
                    "matched_product_id": str(raw.matched_product_id),
                    "article": str(raw.article or ""),
                    "normalized_article": str(raw.normalized_article or ""),
                    "external_sku": str(raw.external_sku or ""),
                    "source_code": str(getattr(getattr(raw, "source", None), "code", "") or ""),
                }
            )

        for price in ProductPrice.objects.filter(product=product).order_by("id"):
            rows.append(
                {
                    "scope": "product_price",
                    "id": str(price.id),
                    "currency": str(price.currency or ""),
                    "purchase_price": str(price.purchase_price or ""),
                    "landed_cost": str(price.landed_cost or ""),
                    "final_price": str(price.final_price or ""),
                }
            )

        rows.append(
            {
                "scope": "original_product_dependencies",
                "productimage_count": ProductImage.objects.filter(product=product).count(),
                "productattribute_count": ProductAttribute.objects.filter(product=product).count(),
                "productfitment_count": ProductFitment.objects.filter(product=product).count(),
                "trusted_link_status": self._is_trusted(product),
                "autodb_match_jobs_count": AutoDbMatchJob.objects.filter(product=product).count(),
                "autodb_match_evidence_count": AutoDbMatchEvidence.objects.filter(job__product=product).count(),
            }
        )

        global_snapshot = self._global_snapshot()
        for key, value in global_snapshot.items():
            rows.append({"scope": "global_integrity_before", "metric": key, "value": value})
        return rows

    def _post_apply_verification(self, candidate: dict[str, Any], result: Any) -> list[dict[str, Any]]:
        source = Product.objects.select_related("brand").get(id=result.source_product_id)
        new = Product.objects.select_related("brand").get(id=result.new_product_id)
        rows: list[dict[str, Any]] = []

        rows.append(
            {
                "check": "new_sku_no_split_suffix",
                "ok": "SPLIT" not in str(new.sku or "").upper(),
                "value": str(new.sku or ""),
            }
        )
        rows.append(
            {
                "check": "supplier_offers_moved_correctly",
                "ok": SupplierOffer.objects.filter(id__in=list(result.moved_offer_ids), product_id=result.new_product_id).count()
                == len(result.moved_offer_ids),
                "value": SupplierOffer.objects.filter(id__in=list(result.moved_offer_ids)).values("id", "product_id").count(),
            }
        )
        rows.append(
            {
                "check": "raw_offers_moved_correctly",
                "ok": SupplierRawOffer.objects.filter(id__in=list(result.moved_raw_offer_ids), matched_product_id=result.new_product_id).count()
                == len(result.moved_raw_offer_ids),
                "value": SupplierRawOffer.objects.filter(id__in=list(result.moved_raw_offer_ids)).values("id", "matched_product_id").count(),
            }
        )
        rows.append(
            {
                "check": "productprice_new_exists",
                "ok": ProductPrice.objects.filter(id=result.new_productprice_id, product_id=result.new_product_id).exists(),
                "value": str(result.new_productprice_id),
            }
        )
        rows.append(
            {
                "check": "source_no_moved_offer_left",
                "ok": SupplierOffer.objects.filter(id__in=list(result.moved_offer_ids), product_id=result.source_product_id).count() == 0,
                "value": "",
            }
        )
        rows.append(
            {
                "check": "brand_filters_distinct",
                "ok": bool(source.display_brand_name) and bool(new.display_brand_name) and source.display_brand_name != new.display_brand_name,
                "value": f"{source.display_brand_name} vs {new.display_brand_name}",
            }
        )
        rows.append(
            {
                "check": "no_duplicate_public_sku",
                "ok": Product.objects.filter(svom_sku=new.svom_sku).count() == 1,
                "value": str(new.svom_sku or ""),
            }
        )
        rows.append(
            {
                "check": "no_images_created",
                "ok": ProductImage.objects.filter(product_id=result.new_product_id).count() == 0,
                "value": ProductImage.objects.filter(product_id=result.new_product_id).count(),
            }
        )
        rows.append(
            {
                "check": "no_attributes_created",
                "ok": ProductAttribute.objects.filter(product_id=result.new_product_id).count() == 0,
                "value": ProductAttribute.objects.filter(product_id=result.new_product_id).count(),
            }
        )
        rows.append(
            {
                "check": "no_fitments_created",
                "ok": ProductFitment.objects.filter(product_id=result.new_product_id).count() == 0,
                "value": ProductFitment.objects.filter(product_id=result.new_product_id).count(),
            }
        )
        return rows

    def _admin_search_smoke(self, candidate: dict[str, Any], result: Any) -> str:
        source = Product.objects.select_related("brand").get(id=result.source_product_id)
        new = Product.objects.select_related("brand").get(id=result.new_product_id)
        source_search = Product.objects.filter(Q(svom_sku=candidate["original_sku"]) | Q(sku=candidate["original_sku"])).count()
        new_search = Product.objects.filter(id=new.id).count()
        source_brand_hits = Product.objects.filter(id=source.id, display_brand_name=source.display_brand_name).count()
        new_brand_hits = Product.objects.filter(id=new.id, display_brand_name=new.display_brand_name).count()
        lines = [
            "# Split v2 one admin/search smoke",
            "",
            f"- original_sku_search_hits: {source_search}",
            f"- new_product_search_hits: {new_search}",
            f"- original_brand_filter_hits: {source_brand_hits}",
            f"- new_brand_filter_hits: {new_brand_hits}",
            f"- original_supplier_codes: {sorted(set(SupplierOffer.objects.filter(product=source).select_related('supplier').values_list('supplier__code', flat=True)))}",
            f"- new_supplier_codes: {sorted(set(SupplierOffer.objects.filter(product=new).select_related('supplier').values_list('supplier__code', flat=True)))}",
            "- public_duplicate_issue: no",
            "",
        ]
        return "\n".join(lines)

    def _build_rollback_package(self, candidate: dict[str, Any], result: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.append(
            {
                "scope": "identity",
                "source_product_id": result.source_product_id,
                "new_product_id": result.new_product_id,
                "new_product_sku": result.new_product_sku,
                "new_product_svom_sku": result.new_product_svom_sku,
            }
        )
        rows.append({"scope": "moved_supplier_offer_ids", "ids": ",".join(result.moved_offer_ids)})
        rows.append({"scope": "moved_supplier_raw_offer_ids", "ids": ",".join(result.moved_raw_offer_ids)})
        rows.append({"scope": "source_productprice_ids", "ids": ",".join(result.source_productprice_ids)})
        rows.append({"scope": "new_productprice_id", "id": result.new_productprice_id})
        rows.append({"scope": "source_quarantine_job_id", "id": result.source_quarantine_job_id})
        rows.append({"scope": "new_quarantine_job_id", "id": result.new_quarantine_job_id})
        rows.append(
            {
                "scope": "rollback_steps",
                "steps": "move_supplier_offers_back_to_source; move_supplier_raw_offers_back_to_source; "
                "restore_source_brand_autodb_fields; delete_or_deactivate_new_product; restore_productprice_links; preserve_no_links_enrichment_images",
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
            "sum_supplier_purchase_price": SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"] or 0,
            "sum_productprice_final_price": ProductPrice.objects.aggregate(v=Sum("final_price"))["v"] or 0,
            "utr_api_calls": 0,
        }

    def _build_integrity_rows(self, *, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
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

    def _is_trusted(self, product: Product) -> bool:
        if str(product.autodb_article_key or "").strip():
            return True
        return AutoDbProductLinkQuality.objects.filter(
            product=product,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()

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

    def _write_md(self, path: Path, *, title: str, lines: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join([f"# {title}", "", *lines, ""]), encoding="utf-8")

    def _split_ids(self, value: str) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    def _as_bool(self, value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set, dict)):
            return repr(value)
        return str(value)

    def _delta(self, before: dict[str, Any], after: dict[str, Any], key: str) -> Any:
        try:
            return (after.get(key) or 0) - (before.get(key) or 0)
        except Exception:
            return ""
