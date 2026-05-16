from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.catalog.models import Product
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class AutoDbProductSplitRollbackDryRun:
    source_product_id: str
    split_product_id: str
    requested_moved_offer_ids: tuple[str, ...]
    moved_offer_ids_on_split: tuple[str, ...]
    moved_offer_ids_missing_on_split: tuple[str, ...]
    requested_moved_raw_offer_ids: tuple[str, ...]
    moved_raw_offer_ids_on_split: tuple[str, ...]
    moved_raw_offer_ids_missing_on_split: tuple[str, ...]
    split_product_offer_count_before: int
    split_product_offer_count_after_move: int
    source_product_raw_offer_count_before: int
    source_product_raw_offer_count_after_move: int
    split_product_raw_offer_count_before: int
    split_product_raw_offer_count_after_move: int
    requested_split_productprice_ids: tuple[str, ...]
    split_productprice_ids_on_split: tuple[str, ...]
    split_productprice_ids_missing_on_split: tuple[str, ...]
    split_product_productprice_count_after: int
    split_product_productprice_count: int
    split_product_image_count: int
    split_product_attribute_count: int
    split_product_fitment_count: int
    split_product_trusted_link_count: int
    source_product_offer_count_before: int
    source_product_offer_count_after_move: int
    split_product_has_svom_sku: bool
    delete_split_product_safe: bool
    recommended_split_product_action: str
    source_restore_brand_name: str
    source_restore_display_brand_name: str
    source_restore_autodb_supplier_id: int | None
    source_restore_autodb_supplier_name: str
    safety_blockers: tuple[str, ...]
    clean: bool


@dataclass(frozen=True)
class AutoDbProductSplitRollbackApplyResult:
    source_product_id: str
    split_product_id: str
    moved_offer_ids_restored: tuple[str, ...]
    moved_raw_offer_ids_restored: tuple[str, ...]
    split_productprice_ids_removed: tuple[str, ...]
    split_product_action: str
    source_display_brand_after: str
    source_autodb_supplier_id_after: int | None
    source_offer_count_after: int
    split_offer_count_after: int
    source_raw_offer_count_after: int
    split_raw_offer_count_after: int
    split_productprice_count_after: int
    source_quarantine_status: str
    split_quarantine_status: str


class AutoDbProductSplitRollbackService:
    """
    Service-backed rollback for one pilot split.

    Writes only:
    - SupplierOffer.product reassignment for explicitly provided offers
    - Product.is_active/published_at for split product
    - AutoDbMatchJob/AutoDbMatchEvidence service state
    """

    QUARANTINE_SOURCE = "product_quality_quarantine"
    EVIDENCE_STAGE = "product_split_pilot"
    EVIDENCE_SOURCE = "matching_service"

    def plan(
        self,
        *,
        source_product_id: str,
        split_product_id: str,
        moved_offer_ids: list[str],
        moved_raw_offer_ids: list[str] | None = None,
        split_productprice_ids: list[str] | None = None,
    ) -> AutoDbProductSplitRollbackDryRun:
        source = Product.objects.filter(id=source_product_id).first()
        split = Product.objects.filter(id=split_product_id).first()
        safety_blockers: list[str] = []
        if source is None:
            safety_blockers.append("source_product_not_found")
        if split is None:
            safety_blockers.append("split_product_not_found")

        requested_ids = tuple(sorted(set(str(item or "").strip() for item in moved_offer_ids if str(item or "").strip())))
        requested_raw_ids = tuple(sorted(set(str(item or "").strip() for item in (moved_raw_offer_ids or []) if str(item or "").strip())))
        requested_pp_ids = tuple(sorted(set(str(item or "").strip() for item in (split_productprice_ids or []) if str(item or "").strip())))
        if not requested_ids:
            safety_blockers.append("empty_moved_offer_ids")

        if source is None or split is None:
            return AutoDbProductSplitRollbackDryRun(
                source_product_id=source_product_id,
                split_product_id=split_product_id,
                requested_moved_offer_ids=requested_ids,
                moved_offer_ids_on_split=tuple(),
                moved_offer_ids_missing_on_split=requested_ids,
                requested_moved_raw_offer_ids=requested_raw_ids,
                moved_raw_offer_ids_on_split=tuple(),
                moved_raw_offer_ids_missing_on_split=requested_raw_ids,
                split_product_offer_count_before=0,
                split_product_offer_count_after_move=0,
                source_product_raw_offer_count_before=0,
                source_product_raw_offer_count_after_move=0,
                split_product_raw_offer_count_before=0,
                split_product_raw_offer_count_after_move=0,
                requested_split_productprice_ids=requested_pp_ids,
                split_productprice_ids_on_split=tuple(),
                split_productprice_ids_missing_on_split=requested_pp_ids,
                split_product_productprice_count_after=0,
                split_product_productprice_count=0,
                split_product_image_count=0,
                split_product_attribute_count=0,
                split_product_fitment_count=0,
                split_product_trusted_link_count=0,
                source_product_offer_count_before=0,
                source_product_offer_count_after_move=0,
                split_product_has_svom_sku=False,
                delete_split_product_safe=False,
                recommended_split_product_action="none",
                source_restore_brand_name="",
                source_restore_display_brand_name="",
                source_restore_autodb_supplier_id=None,
                source_restore_autodb_supplier_name="",
                safety_blockers=tuple(sorted(set(safety_blockers))),
                clean=False,
            )

        source_offer_count_before = SupplierOffer.objects.filter(product=source).count()
        split_offer_count_before = SupplierOffer.objects.filter(product=split).count()

        moved_ids_on_split = tuple(
            str(item.id)
            for item in SupplierOffer.objects.filter(product=split, id__in=requested_ids).only("id")
        )
        missing_ids = tuple(sorted(set(requested_ids) - set(moved_ids_on_split)))
        if missing_ids:
            safety_blockers.append("moved_offer_not_on_split")

        split_raw_count_before = SupplierRawOffer.objects.filter(matched_product=split).count()
        source_raw_count_before = SupplierRawOffer.objects.filter(matched_product=source).count()
        moved_raw_ids_on_split = tuple(
            str(item.id)
            for item in SupplierRawOffer.objects.filter(matched_product=split, id__in=requested_raw_ids).only("id")
        )
        missing_raw_ids = tuple(sorted(set(requested_raw_ids) - set(moved_raw_ids_on_split)))
        if requested_raw_ids and missing_raw_ids:
            safety_blockers.append("moved_raw_offer_not_on_split")

        split_productprice_ids_on_split = tuple(str(item.id) for item in ProductPrice.objects.filter(product=split).only("id"))
        if requested_pp_ids:
            pp_ids_on_split = tuple(i for i in split_productprice_ids_on_split if i in set(requested_pp_ids))
            missing_pp_ids = tuple(sorted(set(requested_pp_ids) - set(pp_ids_on_split)))
        else:
            pp_ids_on_split = split_productprice_ids_on_split
            missing_pp_ids = tuple()

        if requested_pp_ids and missing_pp_ids:
            safety_blockers.append("split_productprice_not_on_split")

        split_productprice_count = ProductPrice.objects.filter(product=split).count()
        split_image_count = split.images.count()
        split_attribute_count = split.product_attributes.count()
        split_fitment_count = split.fitments.count()
        split_trusted_count = split.autodb_link_qualities.count()
        if split_trusted_count > 0:
            safety_blockers.append("split_product_has_trusted_link_dependency")

        source_offer_count_after = source_offer_count_before + len(moved_ids_on_split)
        split_offer_count_after = split_offer_count_before - len(moved_ids_on_split)
        source_raw_count_after = source_raw_count_before + len(moved_raw_ids_on_split)
        split_raw_count_after = split_raw_count_before - len(moved_raw_ids_on_split)
        split_productprice_count_after = split_productprice_count - len(pp_ids_on_split)

        restore_brand_name = str(source.display_brand_name or source.autodb_supplier_name or "" if source.brand_id else "").strip()
        restore_display = restore_brand_name
        restore_autodb_id: int | None = None
        restore_autodb_name = ""
        split_brand_name = str(split.display_brand_name or split.autodb_supplier_name or "" if split.brand_id else "").strip()
        if restore_brand_name and split_brand_name and restore_brand_name.casefold() == split_brand_name.casefold():
            restore_autodb_id = int(split.autodb_supplier_id or 0) or None
            restore_autodb_name = str(split.autodb_supplier_name or "").strip()

        # Delete is only safe when split product becomes fully detached.
        delete_split_safe = (
            split_offer_count_after == 0
            and split_raw_count_after == 0
            and split_productprice_count_after == 0
            and split_image_count == 0
            and split_attribute_count == 0
            and split_fitment_count == 0
            and split_trusted_count == 0
            and not str(split.svom_sku or "").strip()
        )
        split_action = "delete" if delete_split_safe else "deactivate"

        clean = len(safety_blockers) == 0
        return AutoDbProductSplitRollbackDryRun(
            source_product_id=str(source.id),
            split_product_id=str(split.id),
            requested_moved_offer_ids=requested_ids,
            moved_offer_ids_on_split=moved_ids_on_split,
            moved_offer_ids_missing_on_split=missing_ids,
            requested_moved_raw_offer_ids=requested_raw_ids,
            moved_raw_offer_ids_on_split=moved_raw_ids_on_split,
            moved_raw_offer_ids_missing_on_split=missing_raw_ids,
            split_product_offer_count_before=split_offer_count_before,
            split_product_offer_count_after_move=split_offer_count_after,
            source_product_raw_offer_count_before=source_raw_count_before,
            source_product_raw_offer_count_after_move=source_raw_count_after,
            split_product_raw_offer_count_before=split_raw_count_before,
            split_product_raw_offer_count_after_move=split_raw_count_after,
            requested_split_productprice_ids=requested_pp_ids,
            split_productprice_ids_on_split=pp_ids_on_split,
            split_productprice_ids_missing_on_split=missing_pp_ids,
            split_product_productprice_count_after=split_productprice_count_after,
            split_product_productprice_count=split_productprice_count,
            split_product_image_count=split_image_count,
            split_product_attribute_count=split_attribute_count,
            split_product_fitment_count=split_fitment_count,
            split_product_trusted_link_count=split_trusted_count,
            source_product_offer_count_before=source_offer_count_before,
            source_product_offer_count_after_move=source_offer_count_after,
            split_product_has_svom_sku=bool(str(split.svom_sku or "").strip()),
            delete_split_product_safe=delete_split_safe,
            recommended_split_product_action=split_action,
            source_restore_brand_name=restore_brand_name,
            source_restore_display_brand_name=restore_display,
            source_restore_autodb_supplier_id=restore_autodb_id,
            source_restore_autodb_supplier_name=restore_autodb_name,
            safety_blockers=tuple(sorted(set(safety_blockers))),
            clean=clean,
        )

    def apply(
        self,
        *,
        source_product_id: str,
        split_product_id: str,
        moved_offer_ids: list[str],
        moved_raw_offer_ids: list[str] | None = None,
        split_productprice_ids: list[str] | None = None,
    ) -> AutoDbProductSplitRollbackApplyResult:
        plan = self.plan(
            source_product_id=source_product_id,
            split_product_id=split_product_id,
            moved_offer_ids=moved_offer_ids,
            moved_raw_offer_ids=moved_raw_offer_ids or [],
            split_productprice_ids=split_productprice_ids or [],
        )
        if not plan.clean:
            raise RuntimeError(f"rollback dry-run not clean: {list(plan.safety_blockers)}")

        source = Product.objects.get(id=plan.source_product_id)
        split = Product.objects.get(id=plan.split_product_id)
        moved_ids = list(plan.moved_offer_ids_on_split)
        moved_raw_ids = list(plan.moved_raw_offer_ids_on_split)
        split_pp_ids = list(plan.split_productprice_ids_on_split)

        with transaction.atomic():
            restored_ids: list[str] = []
            offers = list(SupplierOffer.objects.filter(product=split, id__in=moved_ids).only("id", "product_id"))
            for offer in offers:
                offer.product_id = source.id
                offer.save(update_fields=["product", "updated_at"])
                restored_ids.append(str(offer.id))

            restored_raw_ids: list[str] = []
            raw_rows = list(SupplierRawOffer.objects.filter(matched_product=split, id__in=moved_raw_ids).only("id", "matched_product_id"))
            for raw in raw_rows:
                raw.matched_product_id = source.id
                raw.save(update_fields=["matched_product", "updated_at"])
                restored_raw_ids.append(str(raw.id))

            removed_pp_ids: list[str] = []
            pp_rows = list(ProductPrice.objects.filter(product=split, id__in=split_pp_ids).only("id"))
            for pp in pp_rows:
                removed_pp_ids.append(str(pp.id))
                pp.delete()

            source.display_brand_name = plan.source_restore_display_brand_name
            source.normalized_brand = normalize_brand(plan.source_restore_display_brand_name)
            source.brand_source = Product.BRAND_SOURCE_AUTODB_PRO if plan.source_restore_autodb_supplier_id else Product.BRAND_SOURCE_SUPPLIER_FALLBACK
            source.brand_source_hash = f"split_rollback_source:{source.id}"
            source.autodb_supplier_id = plan.source_restore_autodb_supplier_id
            source.autodb_supplier_name = plan.source_restore_autodb_supplier_name
            source.save(
                update_fields=[
                    "display_brand_name",
                    "normalized_brand",
                    "brand_source",
                    "brand_source_hash",
                    "autodb_supplier_id",
                    "autodb_supplier_name",
                    "updated_at",
                ]
            )

            split_action = plan.recommended_split_product_action
            if split_action == "delete":
                split.delete()
            else:
                split.is_active = False
                split.save(update_fields=["is_active", "updated_at"])

            source_status = "skipped_split_product_candidate"
            split_status = "needs_review"
            self._upsert_quarantine_job(
                product=source,
                status=source_status,
                reason=f"split_rollback_applied:restored_offers={len(restored_ids)} restored_raw_offers={len(restored_raw_ids)} removed_productprices={len(removed_pp_ids)}",
            )
            if split_action != "delete":
                self._upsert_quarantine_job(
                    product=split,
                    status=split_status,
                    reason="split_rollback_applied:split_product_deactivated",
                )
            self._append_evidence(
                product=source,
                result="rollback_restored_source",
                reason=f"restored_offer_ids={restored_ids} restored_raw_offer_ids={restored_raw_ids}",
                payload={
                    "source_product_id": str(source.id),
                    "split_product_id": str(split.id),
                    "moved_offer_ids": restored_ids,
                    "moved_raw_offer_ids": restored_raw_ids,
                    "removed_split_productprice_ids": removed_pp_ids,
                },
            )
            if split_action != "delete":
                self._append_evidence(
                    product=split,
                    result="rollback_split_deactivated",
                    reason="split_product_deactivated",
                    payload={
                        "source_product_id": str(source.id),
                        "split_product_id": str(split.id),
                        "moved_offer_ids": restored_ids,
                        "moved_raw_offer_ids": restored_raw_ids,
                        "removed_split_productprice_ids": removed_pp_ids,
                    },
                )

            return AutoDbProductSplitRollbackApplyResult(
                source_product_id=str(source.id),
                split_product_id=str(split.id),
                moved_offer_ids_restored=tuple(restored_ids),
                moved_raw_offer_ids_restored=tuple(restored_raw_ids),
                split_productprice_ids_removed=tuple(removed_pp_ids),
                split_product_action=split_action,
                source_display_brand_after=str(source.display_brand_name or ""),
                source_autodb_supplier_id_after=int(source.autodb_supplier_id or 0) or None,
                source_offer_count_after=SupplierOffer.objects.filter(product=source).count(),
                split_offer_count_after=SupplierOffer.objects.filter(product_id=plan.split_product_id).count(),
                source_raw_offer_count_after=SupplierRawOffer.objects.filter(matched_product=source).count(),
                split_raw_offer_count_after=SupplierRawOffer.objects.filter(matched_product_id=plan.split_product_id).count(),
                split_productprice_count_after=ProductPrice.objects.filter(product_id=plan.split_product_id).count(),
                source_quarantine_status=source_status,
                split_quarantine_status=split_status if split_action != "delete" else "deleted",
            )

    def _upsert_quarantine_job(self, *, product: Product, status: str, reason: str) -> AutoDbMatchJob:
        existing = (
            AutoDbMatchJob.objects.filter(
                product=product,
                supplier_offer__isnull=True,
                article_source_type=self.QUARANTINE_SOURCE,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )
        payload = {
            "quarantine": {
                "active": True,
                "source": "product_split_rollback",
                "status": status,
                "reason": reason,
            }
        }
        if existing is None:
            return AutoDbMatchJob.objects.create(
                product=product,
                supplier_offer=None,
                supplier_code="",
                raw_brand=str(product.display_brand_name or ""),
                normalized_brand=str(product.normalized_brand or ""),
                resolved_supplier_id=int(product.autodb_supplier_id or 0) or None,
                article_source_type=self.QUARANTINE_SOURCE,
                article_value="",
                canonical_article="",
                status=status,
                last_error=reason,
                metadata_json=payload,
            )
        existing.status = status
        existing.last_error = reason
        existing.metadata_json = payload
        existing.save(update_fields=["status", "last_error", "metadata_json", "updated_at"])
        return existing

    def _append_evidence(self, *, product: Product, result: str, reason: str, payload: dict[str, Any]) -> None:
        job = (
            AutoDbMatchJob.objects.filter(
                product=product,
                supplier_offer__isnull=True,
                article_source_type=self.QUARANTINE_SOURCE,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )
        if job is None:
            return
        AutoDbMatchEvidence.objects.create(
            job=job,
            stage=self.EVIDENCE_STAGE,
            source=self.EVIDENCE_SOURCE,
            result=result,
            supplier_id=int(product.autodb_supplier_id or 0) or None,
            article_value="",
            canonical_article="",
            reason=reason,
            payload_json=payload,
        )
