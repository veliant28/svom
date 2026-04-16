from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import uuid

from apps.catalog.services import sanitize_category_name
from apps.supplier_imports.parsers.utils import parse_xlsx_rows

_REQUIRED_COLUMNS = {
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
_PATH_SPLIT_RE = re.compile(r"\s*>\s*")


@dataclass(frozen=True)
class CategorizedSupplierRow:
    supplier_code: str
    raw_offer_id: str
    row_number: int
    file_name: str
    article: str
    product_name: str
    target_category_path: tuple[str, ...]
    new_category_needed: bool
    mapping_notes: str


@dataclass(frozen=True)
class CategorizedSupplierFileParseResult:
    file_name: str
    rows: list[CategorizedSupplierRow]
    headers: tuple[str, ...]
    total_rows: int
    invalid_rows: int
    duplicate_row_ids: int


def parse_categorized_supplier_xlsx(
    *,
    file_path: Path,
    default_supplier_code: str | None = None,
) -> CategorizedSupplierFileParseResult:
    parsed_rows = parse_xlsx_rows(file_path)
    if not parsed_rows:
        return CategorizedSupplierFileParseResult(
            file_name=file_path.name,
            rows=[],
            headers=tuple(),
            total_rows=0,
            invalid_rows=0,
            duplicate_row_ids=0,
        )

    headers = tuple(parsed_rows[0][1].keys())
    _ = _ensure_expected_headers(headers=headers)

    rows: list[CategorizedSupplierRow] = []
    seen_ids: set[str] = set()
    invalid_rows = 0
    duplicate_row_ids = 0

    for row_number, row in parsed_rows:
        supplier_code = _clean(row.get("supplier")).lower() or (default_supplier_code or "").strip().lower()
        raw_offer_id = _clean(row.get("source_row_id"))
        mapping_notes = _clean(row.get("mapping_notes"))
        new_category_needed = _is_yes(row.get("new_category_needed"))
        target_path = _resolve_target_category_path(row=row, new_category_needed=new_category_needed)

        if not supplier_code or not raw_offer_id or not target_path:
            invalid_rows += 1
            continue

        try:
            normalized_row_id = str(uuid.UUID(raw_offer_id))
        except (TypeError, ValueError):
            invalid_rows += 1
            continue

        if normalized_row_id in seen_ids:
            duplicate_row_ids += 1
            continue
        seen_ids.add(normalized_row_id)

        rows.append(
            CategorizedSupplierRow(
                supplier_code=supplier_code,
                raw_offer_id=normalized_row_id,
                row_number=row_number,
                file_name=file_path.name,
                article=_clean(row.get("article")),
                product_name=_clean(row.get("name")),
                target_category_path=target_path,
                new_category_needed=new_category_needed,
                mapping_notes=mapping_notes,
            )
        )

    return CategorizedSupplierFileParseResult(
        file_name=file_path.name,
        rows=rows,
        headers=headers,
        total_rows=len(parsed_rows),
        invalid_rows=invalid_rows,
        duplicate_row_ids=duplicate_row_ids,
    )


def _resolve_target_category_path(*, row: dict[str, str], new_category_needed: bool) -> tuple[str, ...]:
    if new_category_needed:
        parent_parts = _parse_path(raw=_clean(row.get("new_category_parent")), strip_root=True)
        proposed_parts = _parse_path(raw=_clean(row.get("proposed_new_category")), strip_root=True)
        candidate = tuple((*parent_parts, *proposed_parts))
        if candidate:
            return candidate

    category_path = _parse_path(raw=_clean(row.get("category_path")), strip_root=True)
    if category_path:
        return category_path

    top_level = _clean(row.get("our_category"))
    sub_level = _clean(row.get("our_subcategory"))
    if top_level and sub_level:
        return (top_level, sub_level)
    if top_level:
        return (top_level,)

    return tuple()


def _parse_path(*, raw: str, strip_root: bool) -> tuple[str, ...]:
    cleaned = _clean(raw)
    if not cleaned:
        return tuple()

    parts = tuple(
        segment
        for segment in (sanitize_category_name(item) for item in _PATH_SPLIT_RE.split(cleaned))
        if segment
    )
    if not strip_root:
        return parts

    return tuple(item for item in parts if item.strip().lower() != "root")


def _is_yes(value: str | None) -> bool:
    normalized = _clean(value).lower()
    return normalized in {"yes", "y", "true", "1", "так", "да"}


def _clean(value: str | None) -> str:
    return sanitize_category_name(str(value or ""))


def _ensure_expected_headers(*, headers: tuple[str, ...]) -> set[str]:
    present = {str(item).strip() for item in headers}
    return _REQUIRED_COLUMNS - present
