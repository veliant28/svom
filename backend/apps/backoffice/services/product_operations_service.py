from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.supplier_imports.models import SupplierRawOffer


@dataclass
class ProductBulkCategoryMoveResult:
    requested: int
    found: int
    products_updated: int
    raw_offers_total: int
    raw_offers_updated: int
    update_import_rules: bool


class ProductOperationsService:
    @transaction.atomic
    def bulk_move_to_category(
        self,
        *,
        product_ids: list[str],
        category: Category,
        actor=None,
        update_import_rules: bool = True,
    ) -> ProductBulkCategoryMoveResult:
        if not category.is_assignable:
            raise ValueError("category_not_assignable")
        normalized_ids = self._normalize_ids(product_ids)
        queryset = Product.objects.filter(id__in=normalized_ids)

        found_ids = {str(value) for value in queryset.values_list("id", flat=True)}
        products_updated = queryset.exclude(category_id=category.id).update(
            category=category,
            category_manually_locked=True,
        )
        queryset.filter(category_id=category.id, category_manually_locked=False).update(category_manually_locked=True)

        raw_offers_total = 0
        raw_offers_updated = 0
        if update_import_rules and found_ids:
            raw_offers = SupplierRawOffer.objects.filter(matched_product_id__in=tuple(found_ids))
            raw_offers_total = raw_offers.count()
            update_queryset = raw_offers.exclude(
                mapped_category=category,
                category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
                category_mapping_reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL,
                category_mapping_confidence=Decimal("1.000"),
                category_mapped_by=actor,
            )
            raw_offers_updated = update_queryset.update(
                mapped_category=category,
                category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
                category_mapping_reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL,
                category_mapping_confidence=Decimal("1.000"),
                category_mapped_at=timezone.now(),
                category_mapped_by=actor,
            )

        return ProductBulkCategoryMoveResult(
            requested=len(normalized_ids),
            found=len(found_ids),
            products_updated=products_updated,
            raw_offers_total=raw_offers_total,
            raw_offers_updated=raw_offers_updated,
            update_import_rules=update_import_rules,
        )

    @staticmethod
    def _normalize_ids(product_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in product_ids:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result
