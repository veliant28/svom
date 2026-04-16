from celery import shared_task

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory
from apps.pricing.services import ProductRepricer
from apps.supplier_imports.models import ImportRun


@shared_task(name="supplier_imports.reprice_after_import")
def reprice_after_import_task(
    import_run_id: str,
    trigger_note: str = "task:reprice_after_import",
) -> dict[str, int]:
    run = ImportRun.objects.get(id=import_run_id)
    product_ids = list(
        run.raw_offers.filter(matched_product__isnull=False)
        .values_list("matched_product_id", flat=True)
        .distinct()
    )
    if not product_ids:
        return {"repriced": 0, "skipped": 0, "errors": 0}

    queryset = Product.objects.filter(id__in=product_ids).select_related("brand", "category")
    stats = ProductRepricer().recalculate_products(
        queryset,
        source=PriceHistory.SOURCE_IMPORT,
        trigger_note=f"{trigger_note}:{run.source.code}:{run.id}",
    )
    run.repriced_products = int(stats.get("repriced", 0))
    run.summary = {**(run.summary or {}), "repricing": stats}
    run.save(update_fields=("repriced_products", "summary", "updated_at"))
    return stats
