from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import DatabaseError

from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService
from apps.autodb.services.article_lookup import ArticleLookupResult, AutoDbArticleLookupService
from apps.catalog.models import AutoDbArticleManualMapping, Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass(frozen=True)
class ProductLinkResult:
    linked: bool
    link_status: str
    product_id: str
    supplier_id: int | None
    article_id: int | None
    article_number: str
    article_key: str
    normalized_brand: str
    normalized_article: str
    warnings: list[str] = field(default_factory=list)


class AutoDbProductLinkService:
    MIN_MANUAL_MAPPING_CONFIDENCE = Decimal("0.500")

    def __init__(
        self,
        *,
        lookup_service: AutoDbArticleLookupService | None = None,
        enrichment_service: AutoDbArticleEnrichmentService | None = None,
    ):
        self.lookup_service = lookup_service or AutoDbArticleLookupService()
        self.enrichment_service = enrichment_service or AutoDbArticleEnrichmentService()

    def link_product(
        self,
        *,
        product: Product,
        brand_name: str,
        article: str,
        dry_run: bool = False,
        allow_remote: bool = True,
    ) -> ProductLinkResult:
        normalized_brand = normalize_brand(brand_name)
        normalized_article = normalize_article(article)

        lookup = self.lookup_service.lookup(brand_name=brand_name, article=article, allow_remote=allow_remote)

        if not lookup.found:
            mapping = self._resolve_manual_mapping(
                normalized_brand=normalized_brand,
                normalized_article=normalized_article,
            )
            if mapping is not None:
                lookup = self._lookup_from_manual_mapping(
                    mapping=mapping,
                    normalized_brand=normalized_brand,
                    normalized_article=normalized_article,
                )
            else:
                warnings = list(lookup.warnings)
                if "needs_manual_mapping" not in warnings:
                    warnings.append("needs_manual_mapping")
                lookup = ArticleLookupResult(
                    found=lookup.found,
                    normalized_brand=lookup.normalized_brand,
                    normalized_article=lookup.normalized_article,
                    supplier_id=lookup.supplier_id,
                    article_key=lookup.article_key,
                    article_id=lookup.article_id,
                    canonical_article_number=lookup.canonical_article_number,
                    canonical_brand=lookup.canonical_brand,
                    supplier_source=lookup.supplier_source,
                    article_source=lookup.article_source,
                    raw_local_refs=lookup.raw_local_refs,
                    populated_tables=lookup.populated_tables,
                    warnings=warnings,
                    article_search_variants=lookup.article_search_variants,
                    remote_supplier_called=lookup.remote_supplier_called,
                    remote_article_called=lookup.remote_article_called,
                )
        enrichment_warnings: list[str] = []
        if (
            lookup.found
            and allow_remote
            and not dry_run
            and (lookup.article_source == "remote" or lookup.remote_article_called)
        ):
            enrichment_warnings.extend(self._enrich_related_article_rows(lookup=lookup))
            if enrichment_warnings:
                lookup = ArticleLookupResult(
                    found=lookup.found,
                    normalized_brand=lookup.normalized_brand,
                    normalized_article=lookup.normalized_article,
                    supplier_id=lookup.supplier_id,
                    article_key=lookup.article_key,
                    article_id=lookup.article_id,
                    canonical_article_number=lookup.canonical_article_number,
                    canonical_brand=lookup.canonical_brand,
                    supplier_source=lookup.supplier_source,
                    article_source=lookup.article_source,
                    raw_local_refs=lookup.raw_local_refs,
                    populated_tables=lookup.populated_tables,
                    warnings=list(lookup.warnings) + enrichment_warnings,
                    article_search_variants=lookup.article_search_variants,
                    remote_supplier_called=lookup.remote_supplier_called,
                    remote_article_called=lookup.remote_article_called,
                )
        return self.link_product_with_lookup(
            product=product,
            lookup=lookup,
            normalized_brand=normalized_brand,
            normalized_article=normalized_article,
            dry_run=dry_run,
        )

    def link_product_with_lookup(
        self,
        *,
        product: Product,
        lookup: ArticleLookupResult,
        normalized_brand: str,
        normalized_article: str,
        dry_run: bool,
    ) -> ProductLinkResult:
        product.normalized_brand = normalized_brand
        product.normalized_article = normalized_article
        product.autodb_supplier_id = lookup.supplier_id
        product.autodb_article_id = lookup.article_id
        product.autodb_article_number = lookup.canonical_article_number
        product.autodb_article_key = lookup.article_key
        product.catalog_source = Product.CATALOG_SOURCE_AUTODB_PRO if lookup.found else Product.CATALOG_SOURCE_LEGACY
        if not dry_run:
            product.save(
                update_fields=(
                    "normalized_brand",
                    "normalized_article",
                    "autodb_supplier_id",
                    "autodb_article_id",
                    "autodb_article_number",
                    "autodb_article_key",
                    "catalog_source",
                    "updated_at",
                )
            )

        warnings = list(lookup.warnings)
        link_status = "linked" if lookup.found else "not_found"
        if lookup.found and "manual_mapping_applied" in warnings:
            link_status = "linked_manual_mapping"
        elif not lookup.found and "needs_manual_mapping" in warnings:
            link_status = "needs_manual_mapping"
        return ProductLinkResult(
            linked=lookup.found,
            link_status=link_status,
            product_id=str(product.id),
            supplier_id=lookup.supplier_id,
            article_id=lookup.article_id,
            article_number=lookup.canonical_article_number,
            article_key=lookup.article_key,
            normalized_brand=normalized_brand,
            normalized_article=normalized_article,
            warnings=warnings,
        )

    def link_product_by_id(self, *, product_id: str, dry_run: bool = False, allow_remote: bool = True) -> ProductLinkResult:
        product = Product.objects.select_related("brand").get(pk=product_id)
        brand_name = getattr(product.brand, "name", "")
        article = product.article or product.sku
        return self.link_product(
            product=product,
            brand_name=brand_name,
            article=article,
            dry_run=dry_run,
            allow_remote=allow_remote,
        )

    def _resolve_manual_mapping(
        self,
        *,
        normalized_brand: str,
        normalized_article: str,
    ) -> AutoDbArticleManualMapping | None:
        if not normalized_brand or not normalized_article:
            return None
        try:
            return (
                AutoDbArticleManualMapping.objects.filter(
                    normalized_brand=normalized_brand,
                    normalized_article=normalized_article,
                    manual_confirmed=True,
                    confidence__gte=self.MIN_MANUAL_MAPPING_CONFIDENCE,
                )
                .exclude(autodb_article_number="")
                .order_by("-confidence", "-updated_at")
                .first()
            )
        except DatabaseError:
            return None

    def _lookup_from_manual_mapping(
        self,
        *,
        mapping: AutoDbArticleManualMapping,
        normalized_brand: str,
        normalized_article: str,
    ) -> ArticleLookupResult:
        article_number = str(mapping.autodb_article_number or "").strip()
        article_key = str(mapping.autodb_article_key or "").strip()
        if not article_key and mapping.autodb_supplier_id and article_number:
            article_key = f"{mapping.autodb_supplier_id}:{article_number.replace(' ', '')}"

        return ArticleLookupResult(
            found=bool(mapping.autodb_supplier_id and article_number),
            normalized_brand=normalized_brand,
            normalized_article=normalized_article,
            supplier_id=mapping.autodb_supplier_id,
            article_key=article_key,
            article_id=mapping.autodb_article_id,
            canonical_article_number=article_number,
            canonical_brand=str(mapping.brand or normalized_brand),
            supplier_source="manual_mapping",
            article_source="manual_mapping",
            warnings=["manual_mapping_applied"],
        )

    def link_from_raw_offer(self, *, raw_offer_id: str, dry_run: bool = False, allow_remote: bool = True) -> ProductLinkResult:
        raw_offer = SupplierRawOffer.objects.select_related("matched_product", "matched_product__brand").get(pk=raw_offer_id)
        if raw_offer.matched_product is None:
            raise ValueError("Raw offer is not linked to a Product.")

        brand_name = getattr(raw_offer.matched_product.brand, "name", "") or raw_offer.brand_name or raw_offer.normalized_brand
        article = str(getattr(raw_offer.matched_product, "article", "") or "").strip()
        if not article:
            raise ValueError("Matched product has empty article in DB.")
        return self.link_product(
            product=raw_offer.matched_product,
            brand_name=brand_name,
            article=article,
            dry_run=dry_run,
            allow_remote=allow_remote,
        )

    def _enrich_related_article_rows(self, *, lookup: ArticleLookupResult) -> list[str]:
        if not lookup.supplier_id or not lookup.canonical_article_number:
            return []
        try:
            result = self.enrichment_service.enrich_article(
                article_id=lookup.article_id,
                supplier_id=lookup.supplier_id,
                article_number=lookup.canonical_article_number,
                tables=["articles", "article_numbers", "article_prd", "article_links", "prd", "article_inf"],
            )
        except Exception as exc:  # noqa: BLE001
            return [f"related_enrichment_failed:{exc}"]

        warnings: list[str] = []
        if result.warnings:
            warnings.extend([f"related_enrichment_warning:{item}" for item in result.warnings[:5]])
        return warnings
