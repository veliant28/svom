from __future__ import annotations

from collections import defaultdict

from apps.catalog.models import Product
from apps.supplier_imports.services.matching.normalizers import normalize_article, normalize_brand


class ProductMatchIndex:
    def __init__(self) -> None:
        self._by_article_brand: dict[tuple[str, str], list[Product]] = defaultdict(list)
        self._by_article: dict[str, list[Product]] = defaultdict(list)
        self._build_index()

    def _build_index(self) -> None:
        queryset = Product.objects.select_related("brand").order_by("id")
        for product in queryset.iterator(chunk_size=500):
            brand_norm = normalize_brand(product.brand.name)
            keys = {normalize_article(product.article), normalize_article(product.sku)}
            for key in {item for item in keys if item}:
                self._by_article_brand[(key, brand_norm)].append(product)
                self._by_article[key].append(product)

    def find_by_article_brand(self, article_key: str, brand_key: str) -> list[Product]:
        if not article_key or not brand_key:
            return []
        return self._by_article_brand.get((article_key, brand_key), [])

    def find_by_article(self, article_key: str) -> list[Product]:
        if not article_key:
            return []
        return self._by_article.get(article_key, [])
