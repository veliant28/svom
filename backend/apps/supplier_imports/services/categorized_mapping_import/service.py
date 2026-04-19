from __future__ import annotations

from pathlib import Path
from typing import Sequence

from django.db.models import Count

from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services.categorized_mapping_import_parser import (
    CategorizedSupplierFileParseResult,
    CategorizedSupplierRow,
    parse_categorized_supplier_xlsx,
)

from . import persistence, rows as rows_module, summary
from .resolver import CategoryTreeResolver
from .types import CategorizedImportStats


class CategorizedSupplierCategoryImportService:
    def __init__(self, *, batch_size: int = 1000) -> None:
        self._batch_size = max(100, int(batch_size))
        self._category_resolver = CategoryTreeResolver()

    def import_from_files(
        self,
        *,
        file_paths: Sequence[Path],
        supplier_filter: set[str] | None = None,
        strict_supplier_match: bool = True,
    ) -> CategorizedImportStats:
        stats = summary.build_stats()
        supplier_filter = summary.normalize_supplier_filter(supplier_filter)

        parsed_rows: list[CategorizedSupplierRow] = []
        seen_ids: set[str] = set()

        for file_path in file_paths:
            parse_result = parse_categorized_supplier_xlsx(
                file_path=file_path,
                default_supplier_code=rows_module.infer_supplier_code_from_file_name(file_path.name),
            )
            file_stats = self._append_parse_result(
                rows=parsed_rows,
                seen_ids=seen_ids,
                parse_result=parse_result,
                supplier_filter=supplier_filter,
            )
            summary.apply_file_stats(stats=stats, parse_result=parse_result, file_stats=file_stats)

        self._import_rows(rows=parsed_rows, stats=stats, strict_supplier_match=strict_supplier_match)
        summary.finalize_stats(stats=stats, category_resolver=self._category_resolver)
        return stats

    def get_source_category_status_counts(self, *, supplier_code: str) -> dict[str, int]:
        buckets = (
            SupplierRawOffer.objects.filter(source__code=supplier_code)
            .values("category_mapping_status")
            .annotate(total=Count("id"))
            .order_by("category_mapping_status")
        )
        result = {item["category_mapping_status"]: int(item["total"]) for item in buckets}
        for status in (
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED,
        ):
            result.setdefault(status, 0)
        return result

    # Back-compat wrappers
    def _append_parse_result(
        self,
        *,
        rows: list[CategorizedSupplierRow],
        seen_ids: set[str],
        parse_result: CategorizedSupplierFileParseResult,
        supplier_filter: set[str],
    ) -> dict[str, int | str | list[str]]:
        return rows_module_append_parse_result(
            rows=rows,
            seen_ids=seen_ids,
            parse_result=parse_result,
            supplier_filter=supplier_filter,
        )

    def _import_rows(
        self,
        *,
        rows: list[CategorizedSupplierRow],
        stats: CategorizedImportStats,
        strict_supplier_match: bool,
    ) -> None:
        categories_by_path = self._resolve_categories_by_path(rows=rows)
        persistence.import_rows(
            rows=rows,
            stats=stats,
            strict_supplier_match=strict_supplier_match,
            batch_size=self._batch_size,
            categories_by_path=categories_by_path,
        )

    def _resolve_categories_by_path(
        self,
        *,
        rows: list[CategorizedSupplierRow],
    ) -> dict[tuple[str, ...], object | None]:
        return rows_module.resolve_categories_by_path(rows=rows, category_resolver=self._category_resolver)


# Keep local alias to avoid shadowing method arg `rows`.
rows_module_append_parse_result = rows_module.append_parse_result
