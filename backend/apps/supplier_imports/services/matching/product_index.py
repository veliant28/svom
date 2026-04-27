from __future__ import annotations

from collections import defaultdict

from apps.catalog.models import Product
from apps.supplier_imports.services.matching.normalizers import normalize_article, normalize_brand


class ProductMatchIndex:
    def __init__(self, *, lightweight_products: bool = False) -> None:
        self._by_article_brand: dict[tuple[str, str], list[Product]] = defaultdict(list)
        self._by_article: dict[str, list[Product]] = defaultdict(list)
        self._lightweight_products = lightweight_products
        self._build_index()

    def _build_index(self) -> None:
        if self._lightweight_products:
            self._build_lightweight_index()
            return

        queryset = Product.objects.select_related("brand").order_by("id")
        for product in queryset.iterator(chunk_size=500):
            brand_norm = normalize_brand(product.brand.name)
            keys = {normalize_article(product.article), normalize_article(product.sku)}
            for key in {item for item in keys if item}:
                self._by_article_brand[(key, brand_norm)].append(product)
                self._by_article[key].append(product)

    def _build_lightweight_index(self) -> None:
        queryset = Product.objects.order_by("id").values(
            "id",
            "sku",
            "article",
            "brand_id",
            "brand__name",
            "category_id",
        )
        for row in queryset.iterator(chunk_size=5000):
            product = Product(
                id=row["id"],
                sku=row["sku"],
                article=row["article"],
                brand_id=row["brand_id"],
                category_id=row["category_id"],
            )
            brand_norm = normalize_brand(row["brand__name"])
            keys = {normalize_article(row["article"]), normalize_article(row["sku"])}
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
