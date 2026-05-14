from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from apps.autodb.models import AutoDbMatchJob
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolver
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class AutoDbMultiOfferConflictResult:
    product_id: str
    offer_count: int
    status: str
    reason_code: str
    allow_auto_matching: bool
    recommended_job_status: str
    conflict_reasons: tuple[str, ...]
    supplier_codes: tuple[str, ...]
    offer_brand_norms: tuple[str, ...]
    offer_article_norms: tuple[str, ...]
    candidate_supplier_ids: tuple[int, ...]
    trusted_supplier_ids: tuple[int, ...]
    price_ratio: str
    brand_conflict_between_offers: bool
    article_conflict_between_offers: bool
    title_brand_conflict: bool
    supplier_code_conflict_gpl_utr: bool
    price_spread_high: bool
    price_ratio_extreme: bool
    product_autodb_supplier_conflict: bool
    trusted_link_conflict: bool
    likely_bad_merge: bool
    split_product_candidate: bool

    def metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "allow_auto_matching": self.allow_auto_matching,
            "conflict_reasons": list(self.conflict_reasons),
            "supplier_codes": list(self.supplier_codes),
            "offer_brand_norms": list(self.offer_brand_norms),
            "offer_article_norms": list(self.offer_article_norms),
            "candidate_supplier_ids": list(self.candidate_supplier_ids),
            "trusted_supplier_ids": list(self.trusted_supplier_ids),
            "price_ratio": self.price_ratio,
            "brand_conflict_between_offers": self.brand_conflict_between_offers,
            "article_conflict_between_offers": self.article_conflict_between_offers,
            "title_brand_conflict": self.title_brand_conflict,
            "supplier_code_conflict_gpl_utr": self.supplier_code_conflict_gpl_utr,
            "price_spread_high": self.price_spread_high,
            "price_ratio_extreme": self.price_ratio_extreme,
            "product_autodb_supplier_conflict": self.product_autodb_supplier_conflict,
            "trusted_link_conflict": self.trusted_link_conflict,
            "likely_bad_merge": self.likely_bad_merge,
            "split_product_candidate": self.split_product_candidate,
        }


class AutoDbMultiOfferConflictClassifier:
    def __init__(self, *, brand_resolver: AutoDbBrandResolver | None = None):
        self.brand_resolver = brand_resolver or AutoDbBrandResolver()

    def classify_from_offers(
        self,
        *,
        offers: list[SupplierOffer],
        raw_offer_map: dict[tuple[str, str], SupplierRawOffer] | None = None,
    ) -> dict[str, AutoDbMultiOfferConflictResult]:
        if not offers:
            return {}
        by_product: dict[str, list[SupplierOffer]] = defaultdict(list)
        for offer in offers:
            by_product[str(offer.product_id)].append(offer)
        trusted_rows = self._trusted_rows(product_ids=list(by_product.keys()))
        return {
            product_id: self.classify_product(
                product=items[0].product,
                offers=items,
                raw_offer_map=raw_offer_map or {},
                trusted_rows=trusted_rows.get(product_id, []),
            )
            for product_id, items in by_product.items()
        }

    def classify_product(
        self,
        *,
        product: Product,
        offers: list[SupplierOffer],
        raw_offer_map: dict[tuple[str, str], SupplierRawOffer] | None = None,
        trusted_rows: list[dict[str, Any]] | None = None,
    ) -> AutoDbMultiOfferConflictResult:
        raw_offer_map = raw_offer_map or {}
        trusted_rows = trusted_rows or []
        product_id = str(product.id)
        offer_count = len(offers)
        if offer_count <= 1:
            return self._result(product_id=product_id, offer_count=offer_count)

        supplier_codes = sorted({str(item.supplier.code or "").strip().lower() for item in offers if str(item.supplier.code or "").strip()})
        offer_brand_norms: set[str] = set()
        offer_article_norms: set[str] = set()
        candidate_supplier_ids: set[int] = set()
        prices: list[Decimal] = []
        for offer in offers:
            raw_offer = raw_offer_map.get((str(offer.product_id), str(offer.supplier_id)))
            payload = raw_offer.raw_payload if raw_offer is not None and isinstance(raw_offer.raw_payload, dict) else {}
            raw_brand = self._first_nonempty(
                [
                    getattr(raw_offer, "brand_name", ""),
                    payload.get("Бренд"),
                    payload.get("brand"),
                    payload.get("brand_name"),
                ]
            )
            brand_norm = normalize_brand(raw_brand)
            if brand_norm:
                offer_brand_norms.add(brand_norm)
            article_norm = self._article_norm(
                self._first_nonempty(
                    [
                        payload.get("Артикул ТД"),
                        payload.get("Артикул ТД."),
                        payload.get("article_td"),
                        payload.get("manufacturer_article"),
                        payload.get("tecdoc_article"),
                        getattr(raw_offer, "article", ""),
                        offer.supplier_sku,
                    ]
                )
            )
            if article_norm:
                offer_article_norms.add(article_norm)
            candidate = self.brand_resolver.resolve(raw_brand=raw_brand or product.display_brand_name or product.brand.name, supplier_code=offer.supplier.code)
            if candidate.supplier_id:
                candidate_supplier_ids.add(int(candidate.supplier_id))
            value = self._decimal(offer.purchase_price)
            if value is not None and value > 0:
                prices.append(value)

        product_title_brand_norm = normalize_brand(self._first_token(product.name))
        display_brand_norm = normalize_brand(product.display_brand_name or "")
        title_brand_conflict = bool(
            product_title_brand_norm
            and display_brand_norm
            and product_title_brand_norm != display_brand_norm
            and not display_brand_norm.startswith(product_title_brand_norm)
        )
        brand_conflict = len(offer_brand_norms) > 1
        article_conflict = len(offer_article_norms) > 1
        price_ratio = self._ratio(prices)
        price_spread_high = price_ratio > Decimal("3")
        price_ratio_extreme = price_ratio > Decimal("5")
        gpl_utr_conflict = "gpl" in supplier_codes and "utr" in supplier_codes
        product_autodb_supplier_conflict = bool(int(product.autodb_supplier_id or 0) > 0 and candidate_supplier_ids and int(product.autodb_supplier_id) not in candidate_supplier_ids)
        trusted_supplier_ids = sorted({int(item.get("autodb_supplier_id") or 0) for item in trusted_rows if int(item.get("autodb_supplier_id") or 0) > 0})
        trusted_link_conflict = bool(trusted_supplier_ids and candidate_supplier_ids and not set(trusted_supplier_ids).intersection(candidate_supplier_ids))
        likely_bad_merge = bool(
            (brand_conflict and article_conflict)
            or (brand_conflict and price_ratio_extreme)
            or (article_conflict and price_ratio_extreme and gpl_utr_conflict)
        )
        split_product_candidate = bool(likely_bad_merge and gpl_utr_conflict and price_spread_high)

        conflict_reasons: list[str] = []
        if brand_conflict:
            conflict_reasons.append("multi_offer_brand_conflict")
        if article_conflict:
            conflict_reasons.append("multi_offer_article_conflict")
        if title_brand_conflict:
            conflict_reasons.append("title_brand_conflict")
        if price_spread_high:
            conflict_reasons.append("multi_offer_price_spread_high")
        if price_ratio_extreme:
            conflict_reasons.append("multi_offer_price_ratio_extreme")
        if gpl_utr_conflict:
            conflict_reasons.append("supplier_code_conflict_gpl_utr")
        if product_autodb_supplier_conflict:
            conflict_reasons.append("product_autodb_supplier_conflict")
        if trusted_link_conflict:
            conflict_reasons.append("trusted_link_conflict")
        if likely_bad_merge:
            conflict_reasons.append("likely_bad_merge")
        if split_product_candidate:
            conflict_reasons.append("split_product_candidate")

        status = "multi_offer_ok"
        reason_code = ""
        recommended_job_status = ""
        allow_auto_matching = True

        if split_product_candidate:
            status = "split_product_candidate"
            reason_code = "skipped_split_product_candidate"
            recommended_job_status = AutoDbMatchJob.STATUS_SKIPPED_SPLIT_NEEDED
            allow_auto_matching = False
        elif likely_bad_merge:
            status = "likely_bad_merge"
            reason_code = "skipped_multi_offer_conflict"
            recommended_job_status = AutoDbMatchJob.STATUS_REJECTED
            allow_auto_matching = False
        elif trusted_link_conflict:
            status = "manual_review_required"
            reason_code = "needs_review_trusted_conflict"
            recommended_job_status = AutoDbMatchJob.STATUS_NEEDS_REVIEW
            allow_auto_matching = False
        elif brand_conflict or article_conflict or price_ratio_extreme or price_spread_high or title_brand_conflict or product_autodb_supplier_conflict:
            status = (
                "multi_offer_brand_conflict"
                if brand_conflict
                else "multi_offer_article_conflict"
                if article_conflict
                else "multi_offer_price_ratio_extreme"
                if price_ratio_extreme
                else "multi_offer_price_spread_high"
            )
            reason_code = "needs_review"
            recommended_job_status = AutoDbMatchJob.STATUS_NEEDS_REVIEW
            allow_auto_matching = False

        return AutoDbMultiOfferConflictResult(
            product_id=product_id,
            offer_count=offer_count,
            status=status,
            reason_code=reason_code,
            allow_auto_matching=allow_auto_matching,
            recommended_job_status=recommended_job_status,
            conflict_reasons=tuple(conflict_reasons),
            supplier_codes=tuple(supplier_codes),
            offer_brand_norms=tuple(sorted(offer_brand_norms)),
            offer_article_norms=tuple(sorted(offer_article_norms)),
            candidate_supplier_ids=tuple(sorted(candidate_supplier_ids)),
            trusted_supplier_ids=tuple(trusted_supplier_ids),
            price_ratio=str(price_ratio),
            brand_conflict_between_offers=brand_conflict,
            article_conflict_between_offers=article_conflict,
            title_brand_conflict=title_brand_conflict,
            supplier_code_conflict_gpl_utr=gpl_utr_conflict,
            price_spread_high=price_spread_high,
            price_ratio_extreme=price_ratio_extreme,
            product_autodb_supplier_conflict=product_autodb_supplier_conflict,
            trusted_link_conflict=trusted_link_conflict,
            likely_bad_merge=likely_bad_merge,
            split_product_candidate=split_product_candidate,
        )

    def _trusted_rows(self, *, product_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        rows = AutoDbProductLinkQuality.objects.filter(
            product_id__in=product_ids,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).values("product_id", "autodb_supplier_id", "autodb_article_key", "status")
        out: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in rows:
            out[str(item["product_id"])].append(item)
        return out

    def _result(self, *, product_id: str, offer_count: int) -> AutoDbMultiOfferConflictResult:
        return AutoDbMultiOfferConflictResult(
            product_id=product_id,
            offer_count=offer_count,
            status="multi_offer_ok",
            reason_code="",
            allow_auto_matching=True,
            recommended_job_status="",
            conflict_reasons=tuple(),
            supplier_codes=tuple(),
            offer_brand_norms=tuple(),
            offer_article_norms=tuple(),
            candidate_supplier_ids=tuple(),
            trusted_supplier_ids=tuple(),
            price_ratio="0",
            brand_conflict_between_offers=False,
            article_conflict_between_offers=False,
            title_brand_conflict=False,
            supplier_code_conflict_gpl_utr=False,
            price_spread_high=False,
            price_ratio_extreme=False,
            product_autodb_supplier_conflict=False,
            trusted_link_conflict=False,
            likely_bad_merge=False,
            split_product_candidate=False,
        )

    def _decimal(self, value: Any) -> Decimal | None:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def _ratio(self, values: list[Decimal]) -> Decimal:
        if not values:
            return Decimal("0")
        minimum = min(item for item in values if item > 0)
        maximum = max(values)
        if minimum <= 0:
            return Decimal("0")
        return (maximum / minimum).quantize(Decimal("0.0001"))

    def _first_nonempty(self, values: list[Any]) -> str:
        for item in values:
            text = str(item or "").strip()
            if text:
                return text
        return ""

    def _first_token(self, value: str) -> str:
        match = re.search(r"[A-Za-zА-Яа-яЁёЇїІіЄє0-9\\-\\.]+", str(value or ""))
        return str(match.group(0) if match else "").strip()

    def _article_norm(self, value: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())
