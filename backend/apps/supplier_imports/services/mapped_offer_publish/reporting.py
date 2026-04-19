from __future__ import annotations

from .types import PublishCounters, SupplierMappedPublishResult


def build_result(*, counters: PublishCounters, supplier_code: str, supplier_name: str) -> SupplierMappedPublishResult:
    return SupplierMappedPublishResult(
        supplier_code=supplier_code,
        supplier_name=supplier_name,
        raw_rows_scanned=counters.raw_rows_scanned,
        unique_latest_rows=counters.unique_latest_rows,
        eligible_rows=counters.eligible_rows,
        created_rows=counters.created_rows,
        updated_rows=counters.updated_rows,
        skipped_rows=counters.skipped_rows,
        error_rows=counters.error_rows,
        products_created=counters.products_created,
        products_updated=counters.products_updated,
        offers_created=counters.offers_created,
        offers_updated=counters.offers_updated,
        raw_offer_links_updated=counters.raw_offer_links_updated,
        repriced_products=counters.repriced_products,
        repricing_stats=counters.repricing_stats,
        skip_reasons=counters.skip_reasons,
        error_reasons=counters.error_reasons,
    )
