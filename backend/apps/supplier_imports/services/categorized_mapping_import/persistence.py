from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services.categorized_mapping_import_parser import CategorizedSupplierRow

from .diagnostics import add_row_issue
from .rows import chunked
from .types import CategorizedImportStats


def import_rows(
    *,
    rows: list[CategorizedSupplierRow],
    stats: CategorizedImportStats,
    strict_supplier_match: bool,
    batch_size: int,
    categories_by_path: dict[tuple[str, ...], object | None],
) -> None:
    if not rows:
        return

    row_map = {row.raw_offer_id: row for row in rows}
    raw_offer_ids = list(row_map.keys())
    now = timezone.now()
    updated_fields = (
        "mapped_category",
        "category_mapping_status",
        "category_mapping_reason",
        "category_mapping_confidence",
        "category_mapped_at",
        "category_mapped_by",
        "updated_at",
    )

    for offer_chunk_ids in chunked(raw_offer_ids, batch_size):
        offers = SupplierRawOffer.objects.select_related("source", "supplier").filter(id__in=offer_chunk_ids)
        offers_by_id = {str(item.id): item for item in offers}
        to_update: list[SupplierRawOffer] = []

        for raw_offer_id in offer_chunk_ids:
            row = row_map[raw_offer_id]
            raw_offer = offers_by_id.get(raw_offer_id)
            if raw_offer is None:
                stats.rows_not_found += 1
                add_row_issue(
                    stats=stats,
                    row=row,
                    error_code="raw_offer_not_found",
                    message="SupplierRawOffer not found by source_row_id.",
                )
                continue

            source_code = str(getattr(raw_offer.source, "code", "")).strip().lower()
            supplier_code = str(getattr(raw_offer.supplier, "code", "")).strip().lower()
            if strict_supplier_match and row.supplier_code and row.supplier_code not in {source_code, supplier_code}:
                stats.rows_supplier_mismatch += 1
                add_row_issue(
                    stats=stats,
                    row=row,
                    error_code="supplier_mismatch",
                    message=f"Supplier mismatch: row supplier '{row.supplier_code}' vs offer source '{source_code}'.",
                )
                continue

            category = categories_by_path.get(row.target_category_path)
            if category is None:
                stats.rows_unresolved_category += 1
                add_row_issue(
                    stats=stats,
                    row=row,
                    error_code="category_path_unresolved",
                    message=f"Unable to resolve category path: {' > '.join(row.target_category_path)}.",
                )
                continue

            stats.rows_mapped += 1

            changed = False
            previous_category_id = str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else None
            next_category_id = str(category.id)
            if previous_category_id != next_category_id:
                if previous_category_id:
                    stats.mappings_overwritten += 1
                raw_offer.mapped_category = category
                changed = True

            if raw_offer.category_mapping_status != SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED:
                raw_offer.category_mapping_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED
                changed = True
            if raw_offer.category_mapping_reason != SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL:
                raw_offer.category_mapping_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL
                changed = True
            if raw_offer.category_mapping_confidence != Decimal("1.000"):
                raw_offer.category_mapping_confidence = Decimal("1.000")
                changed = True
            if raw_offer.category_mapped_by_id is not None:
                raw_offer.category_mapped_by = None
                changed = True

            if changed:
                raw_offer.category_mapped_at = now
                raw_offer.updated_at = now
                to_update.append(raw_offer)
                stats.rows_updated += 1
            else:
                stats.rows_unchanged += 1

        if to_update:
            SupplierRawOffer.objects.bulk_update(to_update, updated_fields, batch_size=batch_size)
