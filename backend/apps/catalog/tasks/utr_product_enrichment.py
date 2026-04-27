from __future__ import annotations

from celery import shared_task

from apps.catalog.services.utr_product_enrichment import (
    clear_utr_catalog_applicability_queue_locks,
    clear_utr_product_enrichment_queue_lock,
    clear_utr_product_enrichment_queue_locks,
    enrich_utr_catalog_products,
    enrich_utr_product,
    enrich_visible_utr_applicability,
)


@shared_task(name="catalog.enrich_utr_product")
def enrich_utr_product_task(product_id: str, mode: str = "detail") -> dict[str, object]:
    try:
        return enrich_utr_product(product_id=product_id, mode=mode)
    finally:
        clear_utr_product_enrichment_queue_lock(product_id=product_id)


@shared_task(name="catalog.enrich_visible_utr_catalog_products")
def enrich_visible_utr_catalog_products_task(product_ids: list[str]) -> dict[str, object]:
    try:
        return enrich_utr_catalog_products(product_ids=product_ids)
    finally:
        clear_utr_product_enrichment_queue_locks(product_ids=product_ids)


@shared_task(name="catalog.enrich_visible_utr_applicability")
def enrich_visible_utr_applicability_task(detail_ids: list[str]) -> dict[str, object]:
    try:
        return enrich_visible_utr_applicability(detail_ids=detail_ids)
    finally:
        clear_utr_catalog_applicability_queue_locks(detail_ids=detail_ids)
