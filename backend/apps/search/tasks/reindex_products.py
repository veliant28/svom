from celery import shared_task

from apps.search.services import ProductIndexer


@shared_task(name="search.reindex_products")
def reindex_products_task(product_ids: list[str] | None = None) -> dict[str, int | str]:
    return ProductIndexer().reindex_products(product_ids)
