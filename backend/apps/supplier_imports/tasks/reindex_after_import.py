from celery import shared_task

from apps.search.services import ProductIndexer
from apps.supplier_imports.models import ImportRun


@shared_task(name="supplier_imports.reindex_after_import")
def reindex_after_import_task(import_run_id: str) -> dict[str, int | str]:
    run = ImportRun.objects.get(id=import_run_id)
    product_ids = list(
        run.raw_offers.filter(matched_product__isnull=False)
        .values_list("matched_product_id", flat=True)
        .distinct()
    )
    if not product_ids:
        return {"indexed": 0, "errors": 0, "total": 0, "backend": "none"}

    stats = ProductIndexer().reindex_products(product_ids=product_ids)
    run.reindexed_products = int(stats.get("indexed", 0))
    run.summary = {**(run.summary or {}), "reindex": stats}
    run.save(update_fields=("reindexed_products", "summary", "updated_at"))
    return stats
