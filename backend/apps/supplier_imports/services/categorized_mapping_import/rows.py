from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from apps.supplier_imports.services.categorized_mapping_import_parser import (
    CategorizedSupplierFileParseResult,
    CategorizedSupplierRow,
)


def infer_supplier_code_from_file_name(file_name: str) -> str | None:
    normalized = file_name.lower()
    if "gpl" in normalized:
        return "gpl"
    if "utr" in normalized:
        return "utr"
    return None


def append_parse_result(
    *,
    rows: list[CategorizedSupplierRow],
    seen_ids: set[str],
    parse_result: CategorizedSupplierFileParseResult,
    supplier_filter: set[str],
) -> dict[str, int | str | list[str]]:
    rows_kept = 0
    rows_skipped_supplier_filter = 0
    rows_duplicate_global = 0
    for row in parse_result.rows:
        if supplier_filter and row.supplier_code not in supplier_filter:
            rows_skipped_supplier_filter += 1
            continue
        if row.raw_offer_id in seen_ids:
            rows_duplicate_global += 1
            continue
        seen_ids.add(row.raw_offer_id)
        rows.append(row)
        rows_kept += 1

    missing_headers = sorted(
        {
            "source_row_id",
            "supplier",
            "our_category",
            "our_subcategory",
            "category_path",
            "new_category_needed",
            "new_category_parent",
            "proposed_new_category",
            "mapping_notes",
        }
        - set(parse_result.headers)
    )
    return {
        "file_name": parse_result.file_name,
        "rows_total": parse_result.total_rows,
        "rows_kept": rows_kept,
        "rows_invalid": parse_result.invalid_rows,
        "rows_duplicate_file": parse_result.duplicate_row_ids,
        "rows_duplicate_global": rows_duplicate_global,
        "rows_skipped_supplier_filter": rows_skipped_supplier_filter,
        "missing_headers": missing_headers,
    }


def resolve_categories_by_path(
    *,
    rows: list[CategorizedSupplierRow],
    category_resolver,
) -> dict[tuple[str, ...], object | None]:
    rows_by_path: dict[tuple[str, ...], list[CategorizedSupplierRow]] = defaultdict(list)
    for row in rows:
        rows_by_path[row.target_category_path].append(row)

    resolved: dict[tuple[str, ...], object | None] = {}
    for path, path_rows in rows_by_path.items():
        create_path = any(item.new_category_needed for item in path_rows)
        category = category_resolver.ensure_path(path) if create_path else category_resolver.resolve_path(path)
        resolved[path] = category
    return resolved


def chunked(values: Iterable[str], chunk_size: int) -> Iterable[list[str]]:
    chunk: list[str] = []
    for item in values:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
