from __future__ import annotations

from .types import CategorizedImportStats


def build_stats() -> CategorizedImportStats:
    return CategorizedImportStats()


def normalize_supplier_filter(supplier_filter: set[str] | None) -> set[str]:
    return {item.strip().lower() for item in (supplier_filter or set()) if item.strip()}


def apply_file_stats(*, stats: CategorizedImportStats, parse_result, file_stats: dict[str, int | str | list[str]]) -> None:
    stats.files_processed += 1
    stats.rows_total += parse_result.total_rows
    stats.rows_parsed += int(file_stats["rows_kept"])
    stats.rows_skipped_invalid += parse_result.invalid_rows
    stats.rows_skipped_duplicate += parse_result.duplicate_row_ids + int(file_stats["rows_duplicate_global"])
    stats.rows_skipped_supplier_filter += int(file_stats["rows_skipped_supplier_filter"])
    stats.file_summaries.append(file_stats)


def finalize_stats(*, stats: CategorizedImportStats, category_resolver) -> None:
    stats.categories_created = category_resolver.created_count
    stats.categories_reactivated = category_resolver.reactivated_count
    stats.created_categories = list(category_resolver.created_records)
