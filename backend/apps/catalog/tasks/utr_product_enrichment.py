from __future__ import annotations

from celery import shared_task

from apps.catalog.services.utr_product_enrichment import enrich_utr_product


@shared_task(name="catalog.enrich_utr_product")
def enrich_utr_product_task(product_id: str) -> dict[str, object]:
    return enrich_utr_product(product_id=product_id)
