from __future__ import annotations

from django.db import transaction

from apps.catalog.models import Brand, Product
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.selectors import get_import_source_by_code

from . import diagnostics, images, publish, reporting, repricing, selection
from .types import PublishCounters, SupplierMappedPublishResult


class SupplierMappedOffersPublishService:
    def publish_for_supplier(
        self,
        *,
        supplier_code: str,
        run_id: str | None = None,
        include_needs_review: bool = False,
        dry_run: bool = False,
        reprice_after_publish: bool = True,
    ) -> SupplierMappedPublishResult:
        source = get_import_source_by_code(supplier_code)
        supplier = source.supplier

        if dry_run:
            with transaction.atomic():
                result = self._publish(
                    supplier=supplier,
                    supplier_code=supplier_code,
                    run_id=run_id,
                    include_needs_review=include_needs_review,
                    reprice_after_publish=reprice_after_publish,
                )
                transaction.set_rollback(True)
                return result

        return self._publish(
            supplier=supplier,
            supplier_code=supplier_code,
            run_id=run_id,
            include_needs_review=include_needs_review,
            reprice_after_publish=reprice_after_publish,
        )

    def _publish(
        self,
        *,
        supplier: Supplier,
        supplier_code: str,
        run_id: str | None,
        include_needs_review: bool,
        reprice_after_publish: bool,
    ) -> SupplierMappedPublishResult:
        counters = PublishCounters()
        offer_key_seen: set[str] = set()
        affected_product_ids: set[str] = set()
        image_checked_product_ids: set[str] = set()

        brand_cache = self._build_brand_cache()
        product_cache = self._build_product_cache()
        supplier_offer_cache = self._build_supplier_offer_cache(supplier=supplier)

        queryset = selection.get_publish_queryset(supplier_code=supplier_code, run_id=run_id)
        for raw_offer in queryset.iterator(chunk_size=1000):
            counters.raw_rows_scanned += 1
            supplier_sku = self._resolve_supplier_sku(raw_offer=raw_offer)
            offer_key = selection.build_offer_key(supplier_sku=supplier_sku, raw_offer_id=str(raw_offer.id))
            if offer_key in offer_key_seen:
                counters.add_skip("older_history_row")
                continue

            offer_key_seen.add(offer_key)
            counters.unique_latest_rows += 1

            reason = self._resolve_skip_reason(
                raw_offer=raw_offer,
                supplier_sku=supplier_sku,
                include_needs_review=include_needs_review,
            )
            if reason:
                counters.add_skip(reason)
                continue

            counters.eligible_rows += 1
            try:
                with transaction.atomic():
                    product, product_created, product_updated = self._upsert_product(
                        raw_offer=raw_offer,
                        supplier_sku=supplier_sku,
                        brand_cache=brand_cache,
                        product_cache=product_cache,
                        supplier_offer_cache=supplier_offer_cache,
                    )
                    offer, offer_created, offer_updated = self._upsert_supplier_offer(
                        raw_offer=raw_offer,
                        product=product,
                        supplier_sku=supplier_sku,
                        supplier_offer_cache=supplier_offer_cache,
                    )

                    if raw_offer.matched_product_id != product.id:
                        raw_offer.matched_product = product
                        raw_offer.save(update_fields=("matched_product", "updated_at"))
                        counters.raw_offer_links_updated += 1

                if offer_created:
                    counters.created_rows += 1
                else:
                    counters.updated_rows += 1

                if product_created:
                    counters.products_created += 1
                if product_updated:
                    counters.products_updated += 1
                if offer_created:
                    counters.offers_created += 1
                if offer_updated:
                    counters.offers_updated += 1

                affected_product_ids.add(str(offer.product_id))
                product_id = str(product.id)
                if product_id not in image_checked_product_ids:
                    image_checked_product_ids.add(product_id)
                    images.ensure_gpl_product_image(raw_offer=raw_offer, product=product)
            except Exception as exc:
                error_reason = diagnostics.error_reason_from_exception(exc)
                counters.add_error(error_reason)
                diagnostics.log_publish_error(
                    supplier_code=supplier_code,
                    raw_offer_id=str(raw_offer.id),
                    reason=error_reason,
                )

        if reprice_after_publish and affected_product_ids:
            stats = self._reprice_products(affected_product_ids=affected_product_ids, supplier_code=supplier_code)
            counters.repricing_stats = stats
            counters.repriced_products = int(stats.get("repriced", 0))

        return reporting.build_result(
            counters=counters,
            supplier_code=supplier_code,
            supplier_name=supplier.name,
        )

    # Back-compat private wrappers
    def _resolve_skip_reason(
        self,
        *,
        raw_offer: SupplierRawOffer,
        supplier_sku: str,
        include_needs_review: bool,
    ) -> str:
        return selection.resolve_skip_reason(
            raw_offer=raw_offer,
            supplier_sku=supplier_sku,
            include_needs_review=include_needs_review,
        )

    def _build_brand_cache(self) -> dict[str, Brand]:
        return publish.build_brand_cache()

    def _build_product_cache(self) -> dict[str, Product]:
        return publish.build_product_cache()

    def _build_supplier_offer_cache(self, *, supplier: Supplier) -> dict[str, SupplierOffer]:
        return publish.build_supplier_offer_cache(supplier=supplier)

    def _upsert_product(
        self,
        *,
        raw_offer: SupplierRawOffer,
        supplier_sku: str,
        brand_cache: dict[str, Brand],
        product_cache: dict[str, Product],
        supplier_offer_cache: dict[str, SupplierOffer],
    ) -> tuple[Product, bool, bool]:
        return publish.upsert_product(
            raw_offer=raw_offer,
            supplier_sku=supplier_sku,
            brand_cache=brand_cache,
            product_cache=product_cache,
            supplier_offer_cache=supplier_offer_cache,
        )

    def _upsert_supplier_offer(
        self,
        *,
        raw_offer: SupplierRawOffer,
        product: Product,
        supplier_sku: str,
        supplier_offer_cache: dict[str, SupplierOffer],
    ) -> tuple[SupplierOffer, bool, bool]:
        return publish.upsert_supplier_offer(
            raw_offer=raw_offer,
            product=product,
            supplier_sku=supplier_sku,
            supplier_offer_cache=supplier_offer_cache,
        )

    def _resolve_brand(self, *, raw_offer: SupplierRawOffer, brand_cache: dict[str, Brand]) -> Brand:
        return publish.resolve_brand(raw_offer=raw_offer, brand_cache=brand_cache)

    def _resolve_product_name(self, *, raw_offer: SupplierRawOffer, supplier_sku: str) -> str:
        return publish.resolve_product_name(raw_offer=raw_offer, supplier_sku=supplier_sku)

    def _resolve_supplier_sku(self, *, raw_offer: SupplierRawOffer) -> str:
        return selection.resolve_supplier_sku(raw_offer=raw_offer)

    def _build_product_sku(self, *, supplier_sku: str) -> str:
        return selection.build_product_sku(supplier_sku=supplier_sku)

    def _generate_unique_brand_slug(self, base_name: str) -> str:
        return publish.generate_unique_brand_slug(base_name)

    def _reprice_products(self, *, affected_product_ids: set[str], supplier_code: str) -> dict[str, int]:
        return repricing.reprice_products(affected_product_ids=affected_product_ids, supplier_code=supplier_code)
