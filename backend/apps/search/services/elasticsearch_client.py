from __future__ import annotations

from functools import lru_cache
from typing import Any

from django.conf import settings
from elasticsearch import Elasticsearch


@lru_cache(maxsize=1)
def get_elasticsearch_client() -> Elasticsearch | None:
    hosts = settings.ELASTICSEARCH.get("hosts", [])
    if not hosts:
        return None
    return Elasticsearch(hosts=hosts)


def get_products_index_name() -> str:
    index_prefix = settings.ELASTICSEARCH.get("index_prefix", "svom")
    return f"{index_prefix}-products"


def is_elasticsearch_enabled() -> bool:
    return getattr(settings, "SEARCH_BACKEND", "db") == "elasticsearch"


def parse_product_ids(response: dict[str, Any]) -> list[str]:
    hits = response.get("hits", {}).get("hits", [])
    return [hit.get("_id") for hit in hits if hit.get("_id")]
