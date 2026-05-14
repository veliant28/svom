from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.catalog.models import Brand, Product
from apps.catalog.services import ensure_product_svom_sku, generate_unique_product_slug
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand

from .product_split_v2_planner import AutoDbProductSplitV2DryRunPlan, AutoDbProductSplitV2Planner


def _canonical_article(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


@dataclass(frozen=True)
class AutoDbProductSplitV2ApplyResult:
    source_product_id: str
    new_product_id: str
    new_product_sku: str
    new_product_svom_sku: str
    moved_offer_ids: tuple[str, ...]
    moved_raw_offer_ids: tuple[str, ...]
    source_productprice_ids: tuple[str, ...]
    new_productprice_id: str
    source_quarantine_job_id: str
    new_quarantine_job_id: str


class AutoDbProductSplitV2Service:
    QUARANTINE_SOURCE = "product_quality_quarantine"
    EVIDENCE_STAGE = "product_split_v2"

    def __init__(self) -> None:
        self.planner = AutoDbProductSplitV2Planner()

    def plan(
        self,
        *,
        sku: str,
        source_product_id: str,
        moved_offer_ids: list[str],
        keep_group: str,
        move_group: str,
    ) -> AutoDbProductSplitV2DryRunPlan:
        return self.planner.plan(
            sku=sku,
            source_product_id=source_product_id,
            moved_offer_ids=moved_offer_ids,
            keep_group=keep_group,
            move_group=move_group,
        )

    def apply(
        self,
        *,
        sku: str,
        source_product_id: str,
        moved_offer_ids: list[str],
        moved_raw_offer_ids: list[str],
        keep_group: str,
        move_group: str,
    ) -> AutoDbProductSplitV2ApplyResult:
        plan = self.plan(
            sku=sku,
            source_product_id=source_product_id,
            moved_offer_ids=moved_offer_ids,
            keep_group=keep_group,
            move_group=move_group,
        )
        if not plan.clean:
            raise RuntimeError(f"split v2 dry-run not clean: {list(plan.blockers)}")

        requested_raw = tuple(sorted(set(str(i or "").strip() for i in moved_raw_offer_ids if str(i or "").strip())))
        if tuple(sorted(plan.raw_offers_to_move)) != requested_raw:
            raise RuntimeError(
                f"moved_raw_offer_ids mismatch with clean plan: plan={list(plan.raw_offers_to_move)} requested={list(requested_raw)}"
            )

        source = Product.objects.select_related("brand", "category").get(id=plan.source_product_id)
        moved_offers = list(
            SupplierOffer.objects.select_related("supplier")
            .filter(product=source, id__in=list(plan.offers_to_move))
            .order_by("id")
        )
        if len(moved_offers) != len(plan.offers_to_move):
            raise RuntimeError("moved offers changed after dry-run")

        raw_rows = list(
            SupplierRawOffer.objects.filter(matched_product=source, id__in=list(plan.raw_offers_to_move))
            .order_by("id")
        )
        if len(raw_rows) != len(plan.raw_offers_to_move):
            raise RuntimeError("moved raw offers changed after dry-run")

        move_brand = self._resolve_catalog_brand(plan.new_brand_after)
        if move_brand is None:
            raise RuntimeError("move brand not resolved")

        source_key_before = str(source.autodb_article_key or "").strip()
        source_number_before = str(source.autodb_article_number or "").strip()
        moved_offer = moved_offers[0]
        new_name = self._resolve_new_product_name(raw_rows=raw_rows, fallback=source.name)
        new_article = self._resolve_new_product_article(raw_rows=raw_rows, fallback=plan.move_article_canonical)
        preferred_slug = f"{new_name} {plan.proposed_internal_sku}".strip()
        new_slug = generate_unique_product_slug(name=new_name, preferred_slug=preferred_slug)

        with transaction.atomic():
            new_product = Product.objects.create(
                sku=plan.proposed_internal_sku,
                svom_sku=None,
                article=new_article,
                name=new_name,
                slug=new_slug,
                brand=move_brand,
                category=source.category,
                short_description=source.short_description,
                description=source.description,
                is_active=True,
                published_at=source.published_at,
                is_featured=False,
                is_new=False,
                is_bestseller=False,
                display_brand_name=plan.new_display_brand_after,
                normalized_brand=normalize_brand(plan.new_display_brand_after),
                normalized_article=_canonical_article(new_article),
                brand_source=Product.BRAND_SOURCE_AUTODB_PRO if plan.new_autodb_supplier_id_after else Product.BRAND_SOURCE_SUPPLIER_FALLBACK,
                brand_source_hash=f"split_v2_new:{source.id}",
                brand_manually_locked=False,
                autodb_supplier_id=plan.new_autodb_supplier_id_after,
                autodb_supplier_name=plan.new_autodb_supplier_name_after,
                autodb_article_number=source_number_before if plan.new_autodb_supplier_id_after else "",
                autodb_article_key=source_key_before if plan.new_autodb_supplier_id_after else "",
                autodb_article_id=source.autodb_article_id if plan.new_autodb_supplier_id_after else None,
                available_stock_qty_cached=0,
            )
            ensure_product_svom_sku(new_product, save=True)

            for offer in moved_offers:
                offer.product = new_product
                offer.save(update_fields=["product", "updated_at"])

            for raw in raw_rows:
                raw.matched_product = new_product
                raw.save(update_fields=["matched_product", "updated_at"])

            # Source must be POLMO-side after split.
            source.display_brand_name = plan.source_display_brand_after
            source.normalized_brand = normalize_brand(plan.source_display_brand_after)
            source.brand_source = Product.BRAND_SOURCE_SUPPLIER_FALLBACK
            source.brand_source_hash = f"split_v2_source:{source.id}"
            source.autodb_supplier_id = plan.source_autodb_supplier_id_after
            source.autodb_supplier_name = plan.source_autodb_supplier_name_after
            source.autodb_article_key = ""
            source.autodb_article_number = ""
            source.autodb_article_id = None
            source.save(
                update_fields=[
                    "display_brand_name",
                    "normalized_brand",
                    "brand_source",
                    "brand_source_hash",
                    "autodb_supplier_id",
                    "autodb_supplier_name",
                    "autodb_article_key",
                    "autodb_article_number",
                    "autodb_article_id",
                    "updated_at",
                ]
            )

            # ProductPrice handling per v2 plan:
            # - keep source ProductPrice row (already bound to kept GPL side)
            # - create new ProductPrice for new split product from moved offer values
            landed = (Decimal(moved_offer.purchase_price or 0) + Decimal(moved_offer.logistics_cost or 0) + Decimal(moved_offer.extra_cost or 0))
            new_price = ProductPrice.objects.create(
                product=new_product,
                currency=str(moved_offer.currency or "UAH"),
                purchase_price=Decimal(moved_offer.purchase_price or 0),
                logistics_cost=Decimal(moved_offer.logistics_cost or 0),
                extra_cost=Decimal(moved_offer.extra_cost or 0),
                landed_cost=landed,
                raw_sale_price=landed,
                final_price=landed,
            )

            source_job = self._upsert_quarantine(
                product=source,
                status=AutoDbMatchJob.STATUS_NEEDS_REVIEW,
                reason=f"split_v2_applied_source:{keep_group}",
                payload={"keep_group": keep_group},
            )
            new_job = self._upsert_quarantine(
                product=new_product,
                status=AutoDbMatchJob.STATUS_NEEDS_REVIEW,
                reason=f"split_v2_applied_new:{move_group}",
                payload={"move_group": move_group},
            )
            self._append_evidence(
                job=source_job,
                product=source,
                result="source_retained",
                reason=f"keep_group={keep_group}",
                payload={
                    "source_product_id": str(source.id),
                    "new_product_id": str(new_product.id),
                    "moved_offer_ids": list(plan.offers_to_move),
                    "moved_raw_offer_ids": list(plan.raw_offers_to_move),
                },
            )
            self._append_evidence(
                job=new_job,
                product=new_product,
                result="new_product_created",
                reason=f"move_group={move_group}",
                payload={
                    "source_product_id": str(source.id),
                    "new_product_id": str(new_product.id),
                    "moved_offer_ids": list(plan.offers_to_move),
                    "moved_raw_offer_ids": list(plan.raw_offers_to_move),
                },
            )

            return AutoDbProductSplitV2ApplyResult(
                source_product_id=str(source.id),
                new_product_id=str(new_product.id),
                new_product_sku=str(new_product.sku or ""),
                new_product_svom_sku=str(new_product.svom_sku or ""),
                moved_offer_ids=plan.offers_to_move,
                moved_raw_offer_ids=plan.raw_offers_to_move,
                source_productprice_ids=plan.source_productprice_ids,
                new_productprice_id=str(new_price.id),
                source_quarantine_job_id=str(source_job.id),
                new_quarantine_job_id=str(new_job.id),
            )

    def _resolve_catalog_brand(self, name: str) -> Brand | None:
        clean = str(name or "").strip()
        if not clean:
            return None
        candidates = list(Brand.objects.filter(name__iexact=clean)[:2])
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _resolve_new_product_name(self, *, raw_rows: list[SupplierRawOffer], fallback: str) -> str:
        for row in raw_rows:
            value = str(row.product_name or "").strip()
            if value:
                return value
        return str(fallback or "").strip() or "Split product"

    def _resolve_new_product_article(self, *, raw_rows: list[SupplierRawOffer], fallback: str) -> str:
        for row in raw_rows:
            value = str(row.article or "").strip()
            if value:
                return value
        return str(fallback or "").strip()

    def _upsert_quarantine(self, *, product: Product, status: str, reason: str, payload: dict[str, Any]) -> AutoDbMatchJob:
        job = (
            AutoDbMatchJob.objects.filter(
                product=product,
                supplier_offer__isnull=True,
                article_source_type=self.QUARANTINE_SOURCE,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )
        meta = {
            "quarantine": {
                "active": True,
                "source": "product_split_v2",
                "status": status,
                "reason": reason,
            },
            "split_v2": payload,
        }
        if job is None:
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
                metadata_json=meta,
            )
        job.status = status
        job.last_error = reason
        job.metadata_json = meta
        job.save(update_fields=["status", "last_error", "metadata_json", "updated_at"])
        return job

    def _append_evidence(self, *, job: AutoDbMatchJob, product: Product, result: str, reason: str, payload: dict[str, Any]) -> None:
        AutoDbMatchEvidence.objects.create(
            job=job,
            stage=self.EVIDENCE_STAGE,
            source="matching_service",
            result=result,
            supplier_id=int(product.autodb_supplier_id or 0) or None,
            article_value="",
            canonical_article="",
            reason=reason,
            payload_json=payload,
        )
