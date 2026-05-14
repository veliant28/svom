from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.catalog.models import Product
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class AutoDbSplitArtifactCleanupDryRun:
    product_id: str
    exists: bool
    sku: str
    svom_sku: str
    is_active: bool
    created_at: str
    updated_at: str
    supplier_offer_count: int
    raw_offer_count: int
    productprice_count: int
    productimage_count: int
    productattribute_count: int
    productfitment_count: int
    link_quality_count: int
    cart_item_count: int
    order_item_count: int
    service_job_count: int
    service_evidence_count: int
    other_dependency_count: int
    dependency_rows: tuple[str, ...]
    would_delete_product: bool
    would_keep_inactive_and_ignore: bool
    safety_blockers: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    clean: bool


@dataclass(frozen=True)
class AutoDbSplitArtifactCleanupApplyResult:
    product_id: str
    action: str
    deleted: bool
    ignored_marker_applied: bool
    service_job_id: str
    service_evidence_id: str


class AutoDbSplitArtifactCleanupService:
    QUARANTINE_SOURCE = "product_quality_quarantine"
    EVIDENCE_STAGE = "product_split_artifact_cleanup"

    def plan(self, *, product_id: str) -> AutoDbSplitArtifactCleanupDryRun:
        product = Product.objects.filter(id=product_id).first()
        if product is None:
            return AutoDbSplitArtifactCleanupDryRun(
                product_id=product_id,
                exists=False,
                sku="",
                svom_sku="",
                is_active=False,
                created_at="",
                updated_at="",
                supplier_offer_count=0,
                raw_offer_count=0,
                productprice_count=0,
                productimage_count=0,
                productattribute_count=0,
                productfitment_count=0,
                link_quality_count=0,
                cart_item_count=0,
                order_item_count=0,
                service_job_count=0,
                service_evidence_count=0,
                other_dependency_count=0,
                dependency_rows=tuple(),
                would_delete_product=False,
                would_keep_inactive_and_ignore=False,
                safety_blockers=("product_not_found",),
                rollback_steps=tuple(),
                clean=False,
            )

        supplier_offer_count = SupplierOffer.objects.filter(product=product).count()
        raw_offer_count = SupplierRawOffer.objects.filter(matched_product=product).count()
        productprice_count = ProductPrice.objects.filter(product=product).count()
        productimage_count = product.images.count()
        productattribute_count = product.product_attributes.count()
        productfitment_count = product.fitments.count()
        link_quality_count = product.autodb_link_qualities.count()

        cart_item_count = 0
        order_item_count = 0
        try:
            cart_item_count = product.cart_items.count()
        except Exception:
            cart_item_count = 0
        try:
            order_item_count = product.order_items.count()
        except Exception:
            order_item_count = 0

        service_jobs = list(
            AutoDbMatchJob.objects.filter(product=product).only("id", "supplier_offer_id")
        )
        service_job_count = len(service_jobs)
        service_evidence_count = AutoDbMatchEvidence.objects.filter(job__product=product).count()

        dependency_rows: list[str] = []
        def _add(name: str, count: int) -> None:
            if count > 0:
                dependency_rows.append(f"{name}:{count}")

        _add("supplier_offers", supplier_offer_count)
        _add("raw_supplier_offers", raw_offer_count)
        _add("product_prices", productprice_count)
        _add("product_images", productimage_count)
        _add("product_attributes", productattribute_count)
        _add("product_fitments", productfitment_count)
        _add("autodb_link_qualities", link_quality_count)
        _add("cart_items", cart_item_count)
        _add("order_items", order_item_count)

        non_service_dependency_count = (
            supplier_offer_count
            + raw_offer_count
            + productprice_count
            + productimage_count
            + productattribute_count
            + productfitment_count
            + link_quality_count
            + cart_item_count
            + order_item_count
        )

        would_delete = bool(
            (not product.is_active)
            and not str(product.svom_sku or "").strip()
            and non_service_dependency_count == 0
        )
        would_ignore = not would_delete

        blockers: list[str] = []
        if product.is_active:
            blockers.append("product_is_active")
        if str(product.svom_sku or "").strip():
            blockers.append("product_has_public_sku")
        if non_service_dependency_count > 0:
            blockers.append("dependent_rows_exist_for_hard_delete")

        # cleanup action is considered clean when either delete or ignore marker can be applied safely.
        clean = True
        rollback_steps = (
            "if_deleted_restore_from_backup_snapshot",
            "if_ignored_remove_split_artifact_cleanup_marker_from_service_job",
        )
        return AutoDbSplitArtifactCleanupDryRun(
            product_id=str(product.id),
            exists=True,
            sku=str(product.sku or ""),
            svom_sku=str(product.svom_sku or ""),
            is_active=bool(product.is_active),
            created_at=product.created_at.isoformat() if product.created_at else "",
            updated_at=product.updated_at.isoformat() if product.updated_at else "",
            supplier_offer_count=supplier_offer_count,
            raw_offer_count=raw_offer_count,
            productprice_count=productprice_count,
            productimage_count=productimage_count,
            productattribute_count=productattribute_count,
            productfitment_count=productfitment_count,
            link_quality_count=link_quality_count,
            cart_item_count=cart_item_count,
            order_item_count=order_item_count,
            service_job_count=service_job_count,
            service_evidence_count=service_evidence_count,
            other_dependency_count=non_service_dependency_count,
            dependency_rows=tuple(sorted(dependency_rows)),
            would_delete_product=would_delete,
            would_keep_inactive_and_ignore=would_ignore,
            safety_blockers=tuple(sorted(set(blockers))),
            rollback_steps=rollback_steps,
            clean=clean,
        )

    def apply(self, *, product_id: str) -> AutoDbSplitArtifactCleanupApplyResult:
        plan = self.plan(product_id=product_id)
        if not plan.exists:
            raise RuntimeError("cleanup target product not found")

        product = Product.objects.get(id=product_id)
        if plan.would_delete_product:
            with transaction.atomic():
                product.delete()
            return AutoDbSplitArtifactCleanupApplyResult(
                product_id=product_id,
                action="deleted",
                deleted=True,
                ignored_marker_applied=False,
                service_job_id="",
                service_evidence_id="",
            )

        # fallback: keep inactive and mark as ignored artifact in service state.
        with transaction.atomic():
            job = (
                AutoDbMatchJob.objects.filter(
                    product=product,
                    supplier_offer__isnull=True,
                    article_source_type=self.QUARANTINE_SOURCE,
                )
                .order_by("-updated_at", "-created_at")
                .first()
            )
            payload = {
                "split_artifact_cleanup": {
                    "ignore_as_artifact": True,
                    "reason": "orphan_inactive_split_product",
                }
            }
            if job is None:
                job = AutoDbMatchJob.objects.create(
                    product=product,
                    supplier_offer=None,
                    supplier_code="",
                    raw_brand=str(product.display_brand_name or ""),
                    normalized_brand=str(product.normalized_brand or ""),
                    resolved_supplier_id=int(product.autodb_supplier_id or 0) or None,
                    article_source_type=self.QUARANTINE_SOURCE,
                    article_value="",
                    canonical_article="",
                    status=AutoDbMatchJob.STATUS_NEEDS_REVIEW,
                    last_error="split_artifact_cleanup_ignored",
                    metadata_json=payload,
                )
            else:
                merged = dict(job.metadata_json or {}) if isinstance(job.metadata_json, dict) else {}
                merged.update(payload)
                job.metadata_json = merged
                job.last_error = "split_artifact_cleanup_ignored"
                job.save(update_fields=["metadata_json", "last_error", "updated_at"])

            evidence = AutoDbMatchEvidence.objects.create(
                job=job,
                stage=self.EVIDENCE_STAGE,
                source="matching_service",
                result="ignored_artifact",
                supplier_id=int(product.autodb_supplier_id or 0) or None,
                article_value="",
                canonical_article="",
                reason="orphan_inactive_split_product",
                payload_json={"product_id": str(product.id)},
            )
            return AutoDbSplitArtifactCleanupApplyResult(
                product_id=product_id,
                action="ignored_marker_applied",
                deleted=False,
                ignored_marker_applied=True,
                service_job_id=str(job.id),
                service_evidence_id=str(evidence.id),
            )
