from __future__ import annotations

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services.matching.normalizers import normalize_article, normalize_brand
from apps.supplier_imports.services.matching.product_index import ProductMatchIndex
from apps.supplier_imports.services.matching.types import MatchDecision


class OfferMatcher:
    def __init__(self, index: ProductMatchIndex | None = None) -> None:
        self._index = index or ProductMatchIndex()

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
        brand_key = normalize_brand(brand_name, source=source, supplier=supplier)

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

    def _build_article_keys(self, *, article: str, external_sku: str, source: ImportSource | None) -> list[str]:
        article_norm = normalize_article(article, source=source)
        external_norm = normalize_article(external_sku, source=source)
        keys = [value for value in (article_norm, external_norm) if value]
        return list(dict.fromkeys(keys))

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
