from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.backoffice.selectors import get_conflict_raw_offers_queryset, get_import_raw_offers_queryset, get_unmatched_raw_offers_queryset
from apps.catalog.models import Product
from apps.supplier_imports.models import OfferMatchReview, SupplierRawOffer
from apps.supplier_imports.services import ImportQualityService, ProductMatcher, SupplierOfferSyncService


@dataclass(frozen=True)
class MatchingActionStats:
    processed: int
    matched: int
    ignored: int
    updated: int


class MatchingReviewService:
    def __init__(self) -> None:
        self._matcher = ProductMatcher()
        self._sync = SupplierOfferSyncService()
        self._quality = ImportQualityService()

    def get_summary(self) -> dict[str, int]:
        return {
            "unmatched": get_unmatched_raw_offers_queryset().count(),
            "conflicts": get_conflict_raw_offers_queryset().count(),
            "auto_matched": get_import_raw_offers_queryset().filter(match_status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED).count(),
            "manually_matched": get_import_raw_offers_queryset().filter(match_status=SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED).count(),
            "ignored": get_import_raw_offers_queryset().filter(match_status=SupplierRawOffer.MATCH_STATUS_IGNORED).count(),
        }

    def get_candidates(self, *, raw_offer: SupplierRawOffer) -> list[Product]:
        if raw_offer.match_candidate_product_ids:
            candidates_map = {
                str(product.id): product
                for product in Product.objects.filter(id__in=raw_offer.match_candidate_product_ids).select_related("brand", "category")
            }
            ordered = [candidates_map[item] for item in raw_offer.match_candidate_product_ids if item in candidates_map]
            if ordered:
                return ordered

        return list(
            self._matcher.find_candidates(
                article=raw_offer.article,
                external_sku=raw_offer.external_sku,
                brand_name=raw_offer.brand_name,
                source=raw_offer.source,
                supplier=raw_offer.supplier,
            )
        )

    @transaction.atomic
    def confirm_match(self, *, raw_offer: SupplierRawOffer, product: Product, actor=None, note: str = "") -> dict:
        now = timezone.now()
        status_before = raw_offer.match_status

        raw_offer.matched_product = product
        raw_offer.match_status = SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED
        raw_offer.match_reason = ""
        raw_offer.match_candidate_product_ids = self._merge_candidate_ids(raw_offer.match_candidate_product_ids, [str(product.id)])
        raw_offer.matching_attempts += 1
        raw_offer.last_matched_at = now
        raw_offer.matched_manually_by = actor
        raw_offer.matched_manually_at = now
        raw_offer.ignored_at = None

        if raw_offer.price is None:
            raw_offer.is_valid = False
            raw_offer.skip_reason = "missing_price"
        else:
            raw_offer.is_valid = True
            raw_offer.skip_reason = ""

        raw_offer.save(
            update_fields=(
                "matched_product",
                "match_status",
                "match_reason",
                "match_candidate_product_ids",
                "matching_attempts",
                "last_matched_at",
                "matched_manually_by",
                "matched_manually_at",
                "ignored_at",
                "is_valid",
                "skip_reason",
                "updated_at",
            )
        )

        OfferMatchReview.objects.create(
            raw_offer=raw_offer,
            action=OfferMatchReview.ACTION_MANUAL_CONFIRM,
            status_before=status_before,
            status_after=raw_offer.match_status,
            reason=raw_offer.match_reason,
            candidate_product_ids=raw_offer.match_candidate_product_ids,
            selected_product=product,
            performed_by=actor,
            note=note,
        )

        synced = False
        created = False
        if raw_offer.price is not None:
            _, created = self._sync.upsert_from_raw_offer(raw_offer)
            synced = True

        self._quality.refresh_for_run(run=raw_offer.run)

        return {
            "raw_offer_id": str(raw_offer.id),
            "status": raw_offer.match_status,
            "product_id": str(product.id),
            "synced_supplier_offer": synced,
            "supplier_offer_created": created,
        }

    @transaction.atomic
    def ignore_offer(self, *, raw_offer: SupplierRawOffer, actor=None, note: str = "", action: str = OfferMatchReview.ACTION_IGNORE) -> dict:
        status_before = raw_offer.match_status
        now = timezone.now()

        raw_offer.match_status = SupplierRawOffer.MATCH_STATUS_IGNORED
        raw_offer.match_reason = raw_offer.match_reason or ""
        raw_offer.matched_product = None
        raw_offer.ignored_at = now
        raw_offer.is_valid = False
        raw_offer.skip_reason = "ignored"
        raw_offer.matching_attempts += 1
        raw_offer.last_matched_at = now
        raw_offer.save(
            update_fields=(
                "match_status",
                "match_reason",
                "matched_product",
                "ignored_at",
                "is_valid",
                "skip_reason",
                "matching_attempts",
                "last_matched_at",
                "updated_at",
            )
        )

        OfferMatchReview.objects.create(
            raw_offer=raw_offer,
            action=action,
            status_before=status_before,
            status_after=raw_offer.match_status,
            reason=raw_offer.match_reason,
            candidate_product_ids=raw_offer.match_candidate_product_ids,
            selected_product=None,
            performed_by=actor,
            note=note,
        )

        self._quality.refresh_for_run(run=raw_offer.run)

        return {
            "raw_offer_id": str(raw_offer.id),
            "status": raw_offer.match_status,
        }

    @transaction.atomic
    def retry_matching(self, *, raw_offer: SupplierRawOffer, actor=None, note: str = "", action: str = OfferMatchReview.ACTION_RETRY_MATCHING) -> dict:
        status_before = raw_offer.match_status
        now = timezone.now()

        decision = self._matcher.evaluate_offer(
            article=raw_offer.article,
            external_sku=raw_offer.external_sku,
            brand_name=raw_offer.brand_name,
            source=raw_offer.source,
            supplier=raw_offer.supplier,
        )
        candidate_ids = [str(product.id) for product in decision.candidate_products]

        raw_offer.match_status = decision.status
        raw_offer.match_reason = decision.reason
        raw_offer.match_candidate_product_ids = candidate_ids
        raw_offer.matched_product = decision.matched_product
        raw_offer.matching_attempts += 1
        raw_offer.last_matched_at = now

        if decision.status != SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED:
            raw_offer.matched_manually_by = None
            raw_offer.matched_manually_at = None

        if decision.status == SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED and raw_offer.price is not None and raw_offer.matched_product is not None:
            raw_offer.is_valid = True
            raw_offer.skip_reason = ""
            synced_offer, created = self._sync.upsert_from_raw_offer(raw_offer)
            synced = True
            synced_product_id = str(synced_offer.product_id)
        else:
            raw_offer.is_valid = False
            if raw_offer.price is None:
                raw_offer.skip_reason = "missing_price"
            else:
                raw_offer.skip_reason = decision.reason or decision.status
            synced = False
            created = False
            synced_product_id = ""

        raw_offer.save(
            update_fields=(
                "match_status",
                "match_reason",
                "match_candidate_product_ids",
                "matched_product",
                "matching_attempts",
                "last_matched_at",
                "matched_manually_by",
                "matched_manually_at",
                "is_valid",
                "skip_reason",
                "updated_at",
            )
        )

        OfferMatchReview.objects.create(
            raw_offer=raw_offer,
            action=action,
            status_before=status_before,
            status_after=raw_offer.match_status,
            reason=raw_offer.match_reason,
            candidate_product_ids=candidate_ids,
            selected_product=raw_offer.matched_product,
            performed_by=actor,
            note=note,
        )

        self._quality.refresh_for_run(run=raw_offer.run)

        return {
            "raw_offer_id": str(raw_offer.id),
            "status": raw_offer.match_status,
            "reason": raw_offer.match_reason,
            "synced_supplier_offer": synced,
            "supplier_offer_created": created,
            "product_id": synced_product_id,
        }

    def bulk_auto_match(self, *, raw_offers: list[SupplierRawOffer], actor=None, note: str = "") -> MatchingActionStats:
        processed = 0
        matched = 0
        updated = 0

        for raw_offer in raw_offers:
            result = self.retry_matching(
                raw_offer=raw_offer,
                actor=actor,
                note=note,
                action=OfferMatchReview.ACTION_BULK_AUTO_MATCH,
            )
            processed += 1
            updated += 1
            if result.get("status") == SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED:
                matched += 1

        return MatchingActionStats(processed=processed, matched=matched, ignored=0, updated=updated)

    def bulk_ignore(self, *, raw_offers: list[SupplierRawOffer], actor=None, note: str = "") -> MatchingActionStats:
        processed = 0
        ignored = 0
        updated = 0

        for raw_offer in raw_offers:
            self.ignore_offer(raw_offer=raw_offer, actor=actor, note=note, action=OfferMatchReview.ACTION_BULK_IGNORE)
            processed += 1
            ignored += 1
            updated += 1

        return MatchingActionStats(processed=processed, matched=0, ignored=ignored, updated=updated)

    def apply_manual_matches(self, *, mappings: list[dict], actor=None, note: str = "") -> MatchingActionStats:
        processed = 0
        matched = 0
        updated = 0

        offers_map = {
            str(item.id): item
            for item in SupplierRawOffer.objects.filter(id__in=[mapping.get("raw_offer_id") for mapping in mappings])
        }
        products_map = {
            str(item.id): item
            for item in Product.objects.filter(id__in=[mapping.get("product_id") for mapping in mappings])
        }

        for mapping in mappings:
            raw_offer = offers_map.get(str(mapping.get("raw_offer_id")))
            product = products_map.get(str(mapping.get("product_id")))
            if raw_offer is None or product is None:
                continue
            self.confirm_match(raw_offer=raw_offer, product=product, actor=actor, note=note)
            processed += 1
            matched += 1
            updated += 1

        return MatchingActionStats(processed=processed, matched=matched, ignored=0, updated=updated)

    def _merge_candidate_ids(self, existing: list[str], extra: list[str]) -> list[str]:
        merged = [*existing, *extra]
        unique = []
        seen = set()
        for item in merged:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique
