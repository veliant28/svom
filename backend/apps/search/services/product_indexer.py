from __future__ import annotations

from apps.search.selectors import get_products_for_indexing
from apps.search.services.elasticsearch_client import (
    get_elasticsearch_client,
    get_products_index_name,
    is_elasticsearch_enabled,
)
from apps.search.services.product_document_builder import build_product_document


class ProductIndexer:
    def reindex_products(self, product_ids: list[str] | None = None) -> dict[str, int | str]:
        queryset = get_products_for_indexing(product_ids)
        total = queryset.count()

        if total == 0:
            return {"indexed": 0, "errors": 0, "total": 0, "backend": "none"}

        if not is_elasticsearch_enabled():
            return {"indexed": 0, "errors": 0, "total": total, "backend": "db"}

        client = get_elasticsearch_client()
        if client is None:
            return {"indexed": 0, "errors": total, "total": total, "backend": "unavailable"}

        index_name = get_products_index_name()
        self._ensure_index(client=client, index_name=index_name)

        indexed = 0
        errors = 0

        for product in queryset.iterator(chunk_size=200):
            payload = build_product_document(product)
            try:
                client.index(index=index_name, id=str(product.id), document=payload)
                indexed += 1
            except Exception:
                errors += 1

        return {"indexed": indexed, "errors": errors, "total": total, "backend": "elasticsearch"}

    def delete_products(self, product_ids: list[str]) -> dict[str, int | str]:
        if not product_ids:
            return {"deleted": 0, "errors": 0, "backend": "none"}

        if not is_elasticsearch_enabled():
            return {"deleted": 0, "errors": 0, "backend": "db"}

        client = get_elasticsearch_client()
        if client is None:
            return {"deleted": 0, "errors": len(product_ids), "backend": "unavailable"}

        index_name = get_products_index_name()
        deleted = 0
        errors = 0
        for product_id in product_ids:
            try:
                client.delete(index=index_name, id=product_id, ignore=[404])
                deleted += 1
            except Exception:
                errors += 1

        return {"deleted": deleted, "errors": errors, "backend": "elasticsearch"}

    def _ensure_index(self, *, client, index_name: str) -> None:
        if client.indices.exists(index=index_name):
            return

        client.indices.create(
            index=index_name,
            mappings={
                "properties": {
                    "sku": {"type": "keyword"},
                    "article": {"type": "keyword"},
                    "name": {"type": "text"},
                    "slug": {"type": "keyword"},
                    "brand_name": {"type": "text"},
                    "brand_slug": {"type": "keyword"},
                    "category_name": {"type": "text"},
                    "category_slug": {"type": "keyword"},
                    "is_active": {"type": "boolean"},
                    "is_featured": {"type": "boolean"},
                    "is_new": {"type": "boolean"},
                    "is_bestseller": {"type": "boolean"},
                    "final_price": {"type": "double"},
                    "currency": {"type": "keyword"},
                }
            },
        )
