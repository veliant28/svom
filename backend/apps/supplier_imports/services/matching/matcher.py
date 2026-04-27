from __future__ import annotations

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article as simple_normalize_article
from apps.supplier_imports.parsers.utils import normalize_brand as simple_normalize_brand
from apps.supplier_imports.services.matching.product_index import ProductMatchIndex
from apps.supplier_imports.services.matching.types import MatchDecision
from apps.supplier_imports.services.normalization import ArticleNormalizerService, BrandAliasResolverService


class OfferMatcher:
    def __init__(
        self,
        index: ProductMatchIndex | None = None,
        *,
        article_normalizer: ArticleNormalizerService | None = None,
        brand_resolver: BrandAliasResolverService | None = None,
        lightweight_products: bool = False,
    ) -> None:
        self._index = index or ProductMatchIndex(lightweight_products=lightweight_products)
        self._article_normalizer = article_normalizer or ArticleNormalizerService()
        self._brand_resolver = brand_resolver or BrandAliasResolverService()

    def evaluate(
        self,
        *,
        article: str,
        external_sku: str,
        brand_name: str,
        source: ImportSource | None = None,
        supplier: Supplier | None = None,
    ) -> MatchDecision:
        article_keys = self._build_article_keys(article=article, external_sku=external_sku, source=source)
        brand_key = self._normalize_brand(value=brand_name, source=source, supplier=supplier)

        if not article_keys:
            return MatchDecision(
                status=SupplierRawOffer.MATCH_STATUS_UNMATCHED,
                reason=SupplierRawOffer.MATCH_REASON_MISSING_ARTICLE,
                matched_product=None,
                candidate_products=(),
            )

        if brand_key:
            exact_candidates = self._collect_unique_candidates_by_brand(article_keys=article_keys, brand_key=brand_key)
            if len(exact_candidates) == 1:
                return MatchDecision(
                    status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED,
                    reason="",
                    matched_product=exact_candidates[0],
                    candidate_products=tuple(exact_candidates),
                )
            if len(exact_candidates) > 1:
                return MatchDecision(
                    status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED,
                    reason=SupplierRawOffer.MATCH_REASON_AMBIGUOUS,
                    matched_product=None,
                    candidate_products=tuple(exact_candidates),
                )

        fallback_candidates = self._collect_unique_candidates_by_article(article_keys=article_keys)
        if len(fallback_candidates) == 1:
            return MatchDecision(
                status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED,
                reason="",
                matched_product=fallback_candidates[0],
                candidate_products=tuple(fallback_candidates),
            )

        if len(fallback_candidates) > 1:
            if brand_key:
                reason = SupplierRawOffer.MATCH_REASON_BRAND_CONFLICT
            else:
                reason = SupplierRawOffer.MATCH_REASON_MISSING_BRAND
            return MatchDecision(
                status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED,
                reason=reason,
                matched_product=None,
                candidate_products=tuple(fallback_candidates),
            )

        return MatchDecision(
            status=SupplierRawOffer.MATCH_STATUS_UNMATCHED,
            reason=SupplierRawOffer.MATCH_REASON_ARTICLE_CONFLICT,
            matched_product=None,
            candidate_products=(),
        )

    def find_candidates(
        self,
        *,
        article: str,
        external_sku: str,
        brand_name: str,
        source: ImportSource | None = None,
        supplier: Supplier | None = None,
    ) -> tuple:
        decision = self.evaluate(
            article=article,
            external_sku=external_sku,
            brand_name=brand_name,
            source=source,
            supplier=supplier,
        )
        return decision.candidate_products

    def cache_stats(self) -> dict[str, dict[str, int]]:
        return {
            "article_normalizer": self._article_normalizer.cache_stats(),
            "brand_resolver": self._brand_resolver.cache_stats(),
        }

    def _build_article_keys(self, *, article: str, external_sku: str, source: ImportSource | None) -> list[str]:
        article_norm = self._normalize_article(value=article, source=source)
        external_norm = self._normalize_article(value=external_sku, source=source)
        keys = [value for value in (article_norm, external_norm) if value]
        return list(dict.fromkeys(keys))

    def _normalize_article(self, *, value: str | None, source: ImportSource | None) -> str:
        if source is None:
            return simple_normalize_article(value or "")
        return self._article_normalizer.normalize(article=value or "", source=source).normalized_article

    def _normalize_brand(
        self,
        *,
        value: str | None,
        source: ImportSource | None,
        supplier: Supplier | None,
    ) -> str:
        if source is None and supplier is None:
            return simple_normalize_brand(value or "")
        return self._brand_resolver.resolve(
            brand_name=value or "",
            source=source,
            supplier=supplier,
        ).normalized_brand

    def _collect_unique_candidates_by_brand(self, *, article_keys: list[str], brand_key: str):
        unique = {}
        for article_key in article_keys:
            for product in self._index.find_by_article_brand(article_key=article_key, brand_key=brand_key):
                unique[str(product.id)] = product
        return list(unique.values())

    def _collect_unique_candidates_by_article(self, *, article_keys: list[str]):
        unique = {}
        for article_key in article_keys:
            for product in self._index.find_by_article(article_key=article_key):
                unique[str(product.id)] = product
        return list(unique.values())
