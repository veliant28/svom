from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet

from apps.autodb.models import AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.matching.article_source_resolver import AutoDbArticleSourceResolver
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolver
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class AutoDbMatchJobBuildRow:
    product_id: str
    supplier_offer_id: str
    supplier_code: str
    raw_brand: str
    normalized_brand: str
    resolved_supplier_id: int | None
    article_source_type: str
    article_value: str
    canonical_article: str
    status: str
    reason: str
    resolver_source: str
    job_id: str = ""


class AutoDbMatchJobBuilder:
    def __init__(
        self,
        *,
        brand_resolver: AutoDbBrandResolver | None = None,
        article_resolver: AutoDbArticleSourceResolver | None = None,
    ):
        self.brand_resolver = brand_resolver or AutoDbBrandResolver()
        self.article_resolver = article_resolver or AutoDbArticleSourceResolver()

    def build_jobs(
        self,
        *,
        run: AutoDbMatchingRun | None = None,
        supplier_code: str = "",
        limit: int = 100,
        dry_run: bool = True,
    ) -> list[AutoDbMatchJobBuildRow]:
        offers = list(self._latest_offers(supplier_code=supplier_code, limit=limit))
        raw_offer_map = self._latest_raw_offer_map(offers=offers)
        trusted_link_map = self._trusted_link_map(offers=offers)
        rows: list[AutoDbMatchJobBuildRow] = []
        for offer in offers:
            rows.append(
                self._build_from_offer(
                    offer=offer,
                    run=run,
                    dry_run=dry_run,
                    raw_offer=raw_offer_map.get((str(offer.product_id), str(offer.supplier_id))),
                    trusted_link_exists=trusted_link_map.get(str(offer.product_id), False),
                )
            )
        return rows

    def _latest_offers(self, *, supplier_code: str, limit: int) -> Iterable[SupplierOffer]:
        queryset: QuerySet[SupplierOffer] = SupplierOffer.objects.select_related("supplier", "product", "product__brand").order_by(
            "-last_seen_at", "-updated_at"
        )
        if supplier_code:
            queryset = queryset.filter(supplier__code=supplier_code)
        return queryset[: max(int(limit or 0), 1)]

    def _build_from_offer(
        self,
        *,
        offer: SupplierOffer,
        run: AutoDbMatchingRun | None,
        dry_run: bool,
        raw_offer: SupplierRawOffer | None,
        trusted_link_exists: bool,
    ) -> AutoDbMatchJobBuildRow:
        product = offer.product
        raw_brand = self._raw_brand(product=product, raw_offer=raw_offer)
        supplier_code = offer.supplier.code

        if trusted_link_exists:
            return self._persist(
                product=product,
                offer=offer,
                run=run,
                dry_run=dry_run,
                supplier_code=supplier_code,
                raw_brand=raw_brand,
                normalized_brand=product.normalized_brand or "",
                resolved_supplier_id=product.autodb_supplier_id,
                article_source_type="trusted_link",
                article_value=product.autodb_article_number or "",
                canonical_article=product.autodb_article_number or "",
                status=AutoDbMatchJob.STATUS_LINKED,
                reason="trusted Auto_DB link already exists",
                resolver_source="trusted_link",
                metadata=self._metadata(raw_offer=raw_offer, reason="trusted_link"),
            )

        brand = self.brand_resolver.resolve(
            raw_brand=raw_brand,
            supplier_code=supplier_code,
            product_autodb_supplier_id=product.autodb_supplier_id,
        )
        if not brand.is_mapped:
            return self._persist(
                product=product,
                offer=offer,
                run=run,
                dry_run=dry_run,
                supplier_code=supplier_code,
                raw_brand=raw_brand,
                normalized_brand=brand.normalized_brand,
                resolved_supplier_id=None,
                article_source_type="",
                article_value="",
                canonical_article="",
                status=brand.status,
                reason=brand.reason,
                resolver_source=brand.resolver_source or "unresolved",
                metadata=self._metadata(raw_offer=raw_offer, brand_decision=brand.decision, brand_candidates=list(brand.candidates)),
            )

        payload = raw_offer.raw_payload if raw_offer is not None and isinstance(raw_offer.raw_payload, dict) else {}
        source = raw_offer.source if raw_offer is not None else None
        article = self.article_resolver.resolve(
            supplier_code=supplier_code,
            parser_type=source.parser_type if source else "",
            source_code=source.code if source else "",
            raw_brand=raw_brand,
            raw_payload=payload,
            raw_offer_article=raw_offer.article if raw_offer is not None else "",
            product_article=product.article,
            supplier_sku=offer.supplier_sku,
            supplier_sku_is_manufacturer_article=self._supplier_sku_rule(payload),
        )
        if not article.is_usable:
            status = AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE
        else:
            status = AutoDbMatchJob.STATUS_NEW

        return self._persist(
            product=product,
            offer=offer,
            run=run,
            dry_run=dry_run,
            supplier_code=supplier_code,
            raw_brand=raw_brand,
            normalized_brand=brand.normalized_brand,
            resolved_supplier_id=brand.supplier_id,
            article_source_type=article.source_type,
            article_value=article.article_value,
            canonical_article=article.canonical_article,
            status=status,
            reason=article.reason if not article.is_usable else brand.reason,
            resolver_source=brand.resolver_source or "unresolved",
            metadata=self._metadata(
                raw_offer=raw_offer,
                brand_decision=brand.decision,
                resolver_source=brand.resolver_source,
                article_confidence=article.confidence,
                article_reason=article.reason,
            ),
        )

    def _persist(
        self,
        *,
        product: Product,
        offer: SupplierOffer,
        run: AutoDbMatchingRun | None,
        dry_run: bool,
        supplier_code: str,
        raw_brand: str,
        normalized_brand: str,
        resolved_supplier_id: int | None,
        article_source_type: str,
        article_value: str,
        canonical_article: str,
        status: str,
        reason: str,
        resolver_source: str,
        metadata: dict[str, Any],
    ) -> AutoDbMatchJobBuildRow:
        if dry_run:
            return AutoDbMatchJobBuildRow(
                product_id=str(product.id),
                supplier_offer_id=str(offer.id),
                supplier_code=supplier_code,
                raw_brand=raw_brand,
                normalized_brand=normalized_brand,
                resolved_supplier_id=resolved_supplier_id,
                article_source_type=article_source_type,
                article_value=article_value,
                canonical_article=canonical_article,
                status=status,
                reason=reason,
                resolver_source=resolver_source or "unresolved",
                job_id="",
            )

        existing = (
            AutoDbMatchJob.objects.filter(product=product, supplier_offer=offer, canonical_article=canonical_article)
            .order_by("-created_at")
            .first()
        )
        values = {
            "supplier_code": supplier_code,
            "raw_brand": raw_brand,
            "normalized_brand": normalized_brand,
            "resolved_supplier_id": resolved_supplier_id,
            "article_source_type": article_source_type,
            "article_value": article_value,
            "canonical_article": canonical_article,
            "status": status,
            "last_error": "" if status in {AutoDbMatchJob.STATUS_NEW, AutoDbMatchJob.STATUS_LINKED} else reason,
            "last_run": run,
            "metadata_json": metadata,
        }
        if existing is None:
            job = AutoDbMatchJob.objects.create(product=product, supplier_offer=offer, **values)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            existing.save(update_fields=[*values.keys(), "updated_at"])
            job = existing

        return AutoDbMatchJobBuildRow(
            product_id=str(product.id),
            supplier_offer_id=str(offer.id),
            supplier_code=supplier_code,
            raw_brand=raw_brand,
            normalized_brand=normalized_brand,
            resolved_supplier_id=resolved_supplier_id,
            article_source_type=article_source_type,
            article_value=article_value,
            canonical_article=canonical_article,
            status=status,
            reason=reason,
            resolver_source=resolver_source or "unresolved",
            job_id=str(job.id),
        )

    def _latest_raw_offer(self, *, product: Product, offer: SupplierOffer) -> SupplierRawOffer | None:
        return (
            SupplierRawOffer.objects.select_related("source")
            .filter(matched_product=product, supplier=offer.supplier)
            .order_by("-updated_at", "-created_at")
            .first()
        )

    def _latest_raw_offer_map(self, *, offers: list[SupplierOffer]) -> dict[tuple[str, str], SupplierRawOffer]:
        if not offers:
            return {}
        product_ids_by_supplier: dict[str, set[str]] = defaultdict(set)
        for offer in offers:
            product_ids_by_supplier[str(offer.supplier_id)].add(str(offer.product_id))
        out: dict[tuple[str, str], SupplierRawOffer] = {}
        for supplier_id, product_ids in product_ids_by_supplier.items():
            rows = (
                SupplierRawOffer.objects.select_related("source")
                .filter(matched_product_id__in=product_ids, supplier_id=supplier_id)
                .order_by("matched_product_id", "-updated_at", "-created_at")
            )
            for row in rows.iterator(chunk_size=5000):
                key = (str(row.matched_product_id), str(row.supplier_id))
                if key not in out:
                    out[key] = row
        return out

    def _raw_brand(self, *, product: Product, raw_offer: SupplierRawOffer | None) -> str:
        if raw_offer is not None and raw_offer.brand_name:
            return raw_offer.brand_name
        return product.display_brand_name or product.normalized_brand or product.brand.name

    def _trusted_link_map(self, *, offers: list[SupplierOffer]) -> dict[str, bool]:
        if not offers:
            return {}
        product_key_map: dict[str, str] = {}
        for offer in offers:
            key = offer.product.autodb_article_key or ""
            if key:
                product_key_map[str(offer.product_id)] = key
        if not product_key_map:
            return {}
        trusted_rows = AutoDbProductLinkQuality.objects.filter(
            product_id__in=list(product_key_map.keys()),
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).values("product_id", "autodb_article_key")
        trusted_pairs = {(str(row["product_id"]), str(row["autodb_article_key"])) for row in trusted_rows}
        return {
            product_id: (product_id, article_key) in trusted_pairs
            for product_id, article_key in product_key_map.items()
        }

    def _supplier_sku_rule(self, payload: dict[str, Any]) -> bool:
        return bool(
            payload.get("supplier_sku_is_manufacturer_article")
            or payload.get("supplierSkuIsManufacturerArticle")
            or payload.get("article_source") == "supplier_sku_manufacturer"
        )

    def _metadata(self, *, raw_offer: SupplierRawOffer | None, **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = dict(extra)
        if raw_offer is not None:
            payload.update(
                {
                    "raw_offer_id": str(raw_offer.id),
                    "source_code": raw_offer.source.code,
                    "parser_type": raw_offer.source.parser_type,
                    "external_sku": raw_offer.external_sku,
                }
            )
        return payload
