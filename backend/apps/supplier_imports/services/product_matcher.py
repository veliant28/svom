from __future__ import annotations

from apps.catalog.models import Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services.normalization import ArticleNormalizerService, BrandAliasResolverService
from apps.supplier_imports.services.matching import MatchDecision, OfferMatcher


class ProductMatcher:
    def __init__(
        self,
        *,
        article_normalizer: ArticleNormalizerService | None = None,
        brand_resolver: BrandAliasResolverService | None = None,
        lightweight_products: bool = False,
    ) -> None:
        self._matcher = OfferMatcher(
            article_normalizer=article_normalizer,
            brand_resolver=brand_resolver,
            lightweight_products=lightweight_products,
        )

    def match(
        self,
        *,
        article: str,
        external_sku: str,
        brand_name: str,
        source: ImportSource | None = None,
        supplier: Supplier | None = None,
    ) -> Product | None:
        decision = self.evaluate_offer(
            article=article,
            external_sku=external_sku,
            brand_name=brand_name,
            source=source,
            supplier=supplier,
        )
        return decision.matched_product

    def evaluate_offer(
        self,
        *,
        article: str,
        external_sku: str,
        brand_name: str,
        source: ImportSource | None = None,
        supplier: Supplier | None = None,
    ) -> MatchDecision:
        return self._matcher.evaluate(
            article=article,
            external_sku=external_sku,
            brand_name=brand_name,
            source=source,
            supplier=supplier,
        )

    def find_candidates(
        self,
        *,
        article: str,
        external_sku: str,
        brand_name: str,
        source: ImportSource | None = None,
        supplier: Supplier | None = None,
    ) -> tuple[Product, ...]:
        return self._matcher.find_candidates(
            article=article,
            external_sku=external_sku,
            brand_name=brand_name,
            source=source,
            supplier=supplier,
        )

    def cache_stats(self) -> dict[str, dict[str, int]]:
        return self._matcher.cache_stats()
