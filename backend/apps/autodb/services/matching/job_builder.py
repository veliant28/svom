from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet

from apps.autodb.models import AutoDbMatchJob, AutoDbMatchingRun
from apps.autodb.services.matching.article_source_resolver import AutoDbArticleSourceResolver
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolver
from apps.autodb.services.matching.multi_offer_conflict_classifier import AutoDbMultiOfferConflictClassifier, AutoDbMultiOfferConflictResult
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


@dataclass(frozen=True)
class _ProductQuarantineState:
    status: str
    reason: str
    metadata: dict[str, Any]


class AutoDbMatchJobBuilder:
    FAST_ALLOWED_SOURCE_TYPES = {
        "product_article",
        "payload_manufacturer_article",
        "Артикул ТД",
        "Артикул",
        "article",
        "oem",
        "oe",
        "OENbr",
        "manufacturer_article",
        "manufacturerArticle",
        "manufacturer_article_number",
        "manufacturerArticleNumber",
    }
    FAST_BLOCKED_SOURCE_TYPES = {
        "raw_offer_article",
    }

    def __init__(
        self,
        *,
        brand_resolver: AutoDbBrandResolver | None = None,
        article_resolver: AutoDbArticleSourceResolver | None = None,
        multi_offer_classifier: AutoDbMultiOfferConflictClassifier | None = None,
        fast_mode: bool = False,
        fast_allowed_source_types: set[str] | None = None,
        fast_blocked_source_types: set[str] | None = None,
    ):
        self.brand_resolver = brand_resolver or AutoDbBrandResolver()
        self.article_resolver = article_resolver or AutoDbArticleSourceResolver()
        self.multi_offer_classifier = multi_offer_classifier or AutoDbMultiOfferConflictClassifier()
        self.fast_mode = bool(fast_mode)
        self.fast_allowed_source_types = set(fast_allowed_source_types or self.FAST_ALLOWED_SOURCE_TYPES)
        self.fast_blocked_source_types = set(fast_blocked_source_types or self.FAST_BLOCKED_SOURCE_TYPES)

    def build_jobs(
        self,
        *,
        run: AutoDbMatchingRun | None = None,
        supplier_code: str = "",
        limit: int = 100,
        dry_run: bool = True,
        fast_mode: bool | None = None,
    ) -> list[AutoDbMatchJobBuildRow]:
        effective_fast_mode = self.fast_mode if fast_mode is None else bool(fast_mode)
        offers = list(self._latest_offers(supplier_code=supplier_code, limit=limit))
        raw_offer_map = self._latest_raw_offer_map(offers=offers)
        trusted_link_map = self._trusted_link_map(offers=offers)
        guard_by_product = self.multi_offer_classifier.classify_from_offers(offers=offers, raw_offer_map=raw_offer_map)
        quarantine_by_product = self._quarantine_map(offers=offers)
        rows: list[AutoDbMatchJobBuildRow] = []
        for offer in offers:
            rows.append(
                self._build_from_offer(
                    offer=offer,
                    run=run,
                    dry_run=dry_run,
                    fast_mode=effective_fast_mode,
                    raw_offer=raw_offer_map.get((str(offer.product_id), str(offer.supplier_id))),
                    trusted_link_exists=trusted_link_map.get(str(offer.product_id), False),
                    multi_offer_guard=guard_by_product.get(str(offer.product_id)),
                    product_quarantine=quarantine_by_product.get(str(offer.product_id)),
                )
            )
        return rows

    def _latest_offers(self, *, supplier_code: str, limit: int) -> Iterable[SupplierOffer]:
        queryset: QuerySet[SupplierOffer] = SupplierOffer.objects.select_related("supplier", "product").order_by(
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
        fast_mode: bool,
        raw_offer: SupplierRawOffer | None,
        trusted_link_exists: bool,
        multi_offer_guard: AutoDbMultiOfferConflictResult | None,
        product_quarantine: _ProductQuarantineState | None,
    ) -> AutoDbMatchJobBuildRow:
        product = offer.product
        product_article = self.article_resolver.resolve(
            product_article=product.article,
            enforce_product_article=True,
        )
        raw_brand = self._raw_brand(product=product, raw_offer=raw_offer)
        supplier_code = offer.supplier.code
        source = raw_offer.source if raw_offer is not None else None
        parser_type = str(source.parser_type or "").strip().lower() if source is not None else ""
        source_code = str(source.code or "").strip().lower() if source is not None else ""
        is_gpl_source = parser_type == "gpl" or source_code.startswith("gpl") or str(supplier_code or "").strip().lower().startswith("gpl")

        if product_quarantine is not None:
            return self._persist(
                product=product,
                offer=offer,
                run=run,
                dry_run=dry_run,
                supplier_code=supplier_code,
                raw_brand=raw_brand,
                normalized_brand=product.normalized_brand or "",
                resolved_supplier_id=product.autodb_supplier_id,
                article_source_type=product_article.source_type,
                article_value=product_article.article_value,
                canonical_article=product_article.canonical_article,
                status=str(product_quarantine.status or AutoDbMatchJob.STATUS_NEEDS_REVIEW),
                reason=str(product_quarantine.reason or "product_quality_quarantine"),
                resolver_source="product_quality_quarantine",
                metadata=self._metadata(raw_offer=raw_offer, reason="product_quality_quarantine", quarantine=product_quarantine.metadata),
            )

        if multi_offer_guard is not None and not multi_offer_guard.allow_auto_matching:
            return self._persist(
                product=product,
                offer=offer,
                run=run,
                dry_run=dry_run,
                supplier_code=supplier_code,
                raw_brand=raw_brand,
                normalized_brand=product.normalized_brand or "",
                resolved_supplier_id=product.autodb_supplier_id,
                article_source_type=product_article.source_type,
                article_value=product_article.article_value,
                canonical_article=product_article.canonical_article,
                status=multi_offer_guard.recommended_job_status or AutoDbMatchJob.STATUS_NEEDS_REVIEW,
                reason=multi_offer_guard.reason_code or "needs_review",
                resolver_source="multi_offer_guard",
                metadata=self._metadata(
                    raw_offer=raw_offer,
                    reason="multi_offer_guard",
                    multi_offer_guard=multi_offer_guard.metadata(),
                ),
            )

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
            if fast_mode and is_gpl_source and str(brand.decision or "") == "keep_unmapped_missing_supplier":
                return self._persist(
                    product=product,
                    offer=offer,
                    run=run,
                    dry_run=dry_run,
                    supplier_code=supplier_code,
                    raw_brand=raw_brand,
                    normalized_brand=brand.normalized_brand,
                    resolved_supplier_id=None,
                    article_source_type=product_article.source_type,
                    article_value=product_article.article_value,
                    canonical_article=product_article.canonical_article,
                    status=AutoDbMatchJob.STATUS_SKIPPED_BRAND_UNRESOLVED,
                    reason="missing_supplier_id",
                    resolver_source=brand.resolver_source or "unresolved",
                    metadata=self._metadata(
                        raw_offer=raw_offer,
                        brand_decision=brand.decision,
                        brand_candidates=list(brand.candidates),
                        gate="gpl_supplier_id_pre_gate",
                    ),
                )
            return self._persist(
                product=product,
                offer=offer,
                run=run,
                dry_run=dry_run,
                supplier_code=supplier_code,
                raw_brand=raw_brand,
                normalized_brand=brand.normalized_brand,
                resolved_supplier_id=None,
                article_source_type=product_article.source_type,
                article_value=product_article.article_value,
                canonical_article=product_article.canonical_article,
                status=brand.status,
                reason=brand.reason,
                resolver_source=brand.resolver_source or "unresolved",
                metadata=self._metadata(raw_offer=raw_offer, brand_decision=brand.decision, brand_candidates=list(brand.candidates)),
            )

        payload = raw_offer.raw_payload if raw_offer is not None and isinstance(raw_offer.raw_payload, dict) else {}
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
            forbid_raw_offer_fallback=fast_mode,
            enforce_product_article=True,
        )
        if not article.is_usable:
            if fast_mode and article.source_type == "no_trusted_article":
                reason = "no_trusted_article"
            elif article.source_type == "missing_product_article":
                reason = "missing_product_article"
            elif fast_mode and article.source_type in {"raw_offer_article_forbidden", "gpl_missing_manufacturer_article"}:
                reason = "missing_article"
            elif fast_mode:
                reason = "filtered_by_existing_rule"
            else:
                reason = article.reason
            status = AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE
        else:
            reason = brand.reason
            status = AutoDbMatchJob.STATUS_NEW
            if fast_mode:
                source_type = str(article.source_type or "")
                if source_type in self.fast_blocked_source_types:
                    status = AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE
                    reason = "blocked_raw_offer_article"
                elif source_type not in self.fast_allowed_source_types:
                    status = AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE
                    reason = "no_allowed_source_type"
                elif not str(article.canonical_article or "").strip():
                    status = AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE
                    reason = "missing_article"
                elif not str(raw_brand or "").strip():
                    status = AutoDbMatchJob.STATUS_SKIPPED_BRAND_UNRESOLVED
                    reason = "missing_brand"

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
            reason=reason,
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
        return product.display_brand_name or product.normalized_brand or product.display_brand_name or product.autodb_supplier_name or ""

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

    def _quarantine_map(self, *, offers: list[SupplierOffer]) -> dict[str, _ProductQuarantineState]:
        product_ids = sorted({str(item.product_id) for item in offers if str(item.product_id)})
        if not product_ids:
            return {}
        rows = (
            AutoDbMatchJob.objects.filter(
                product_id__in=product_ids,
                supplier_offer__isnull=True,
                article_source_type="product_quality_quarantine",
            )
            .order_by("product_id", "-updated_at", "-created_at")
            .values("product_id", "status", "last_error", "metadata_json")
        )
        out: dict[str, _ProductQuarantineState] = {}
        for row in rows:
            pid = str(row["product_id"])
            if pid in out:
                continue
            meta = row.get("metadata_json") if isinstance(row.get("metadata_json"), dict) else {}
            quarantine = meta.get("quarantine") if isinstance(meta.get("quarantine"), dict) else {}
            if quarantine.get("active") is False:
                continue
            out[pid] = _ProductQuarantineState(
                status=str(row.get("status") or ""),
                reason=str(row.get("last_error") or "") or str(quarantine.get("reason") or ""),
                metadata=meta,
            )
        return out

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
