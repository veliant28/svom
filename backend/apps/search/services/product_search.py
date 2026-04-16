from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.search.services.elasticsearch_client import (
    get_elasticsearch_client,
    get_products_index_name,
    is_elasticsearch_enabled,
    parse_product_ids,
)


class ProductSearchService:
    def apply(self, queryset: QuerySet, query: str) -> QuerySet:
        cleaned_query = query.strip()
        if not cleaned_query:
            return queryset

        if is_elasticsearch_enabled():
            es_ids = self._search_ids_elasticsearch(cleaned_query)
            if es_ids:
                return queryset.filter(id__in=es_ids)

        return queryset.filter(
            Q(name__icontains=cleaned_query)
            | Q(sku__icontains=cleaned_query)
            | Q(article__icontains=cleaned_query)
            | Q(brand__name__icontains=cleaned_query)
        )

    def _search_ids_elasticsearch(self, query: str) -> list[str]:
        client = get_elasticsearch_client()
        if client is None:
            return []

        payload = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["name^4", "sku^5", "article^3", "brand_name^2"],
                    "type": "best_fields",
                }
            },
            "size": 200,
        }

        try:
            response = client.search(index=get_products_index_name(), body=payload)
        except Exception:
            return []

        return parse_product_ids(response)
