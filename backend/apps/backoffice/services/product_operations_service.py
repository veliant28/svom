from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.catalog.models import Category, Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services import SupplierRawOfferCategoryMappingService


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
        normalized_ids = self._normalize_ids(product_ids)
        queryset = Product.objects.filter(id__in=normalized_ids)

        found_ids = {str(value) for value in queryset.values_list("id", flat=True)}
        products_updated = queryset.exclude(category_id=category.id).update(category=category)

        raw_offers_total = 0
        raw_offers_updated = 0
        if update_import_rules and found_ids:
            mapping_service = SupplierRawOfferCategoryMappingService()
            raw_offers = (
                SupplierRawOffer.objects.select_related("mapped_category")
                .filter(matched_product_id__in=tuple(found_ids))
            )
            for raw_offer in raw_offers.iterator(chunk_size=500):
                raw_offers_total += 1
                result = mapping_service.apply_manual_mapping(
                    raw_offer=raw_offer,
                    category=category,
                    actor=actor,
                )
                if result.updated:
                    raw_offers_updated += 1

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
