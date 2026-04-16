from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

from django.db.models import Count
from django.utils import timezone

from apps.catalog.models import Category
from apps.catalog.services import (
    build_category_i18n_names,
    find_category_by_normalized_name,
    generate_unique_category_slug,
    sanitize_category_name,
)
from apps.supplier_imports.models import SupplierRawOffer

from .categorized_mapping_import_parser import (
    CategorizedSupplierFileParseResult,
    CategorizedSupplierRow,
    parse_categorized_supplier_xlsx,
)


@dataclass(frozen=True)
class CreatedCategoryRecord:
    category_id: str
    category_name: str
    category_path: str
    parent_path: str


@dataclass(frozen=True)
class CategorizedImportRowIssue:
    supplier_code: str
    raw_offer_id: str
    row_number: int
    file_name: str
    article: str
    error_code: str
    message: str


@dataclass
class CategorizedImportStats:
    files_processed: int = 0
    rows_total: int = 0
    rows_parsed: int = 0
    rows_skipped_invalid: int = 0
    rows_skipped_duplicate: int = 0
    rows_skipped_supplier_filter: int = 0
    rows_not_found: int = 0
    rows_supplier_mismatch: int = 0
    rows_unresolved_category: int = 0
    rows_mapped: int = 0
    rows_updated: int = 0
    rows_unchanged: int = 0
    mappings_overwritten: int = 0
    categories_created: int = 0
    categories_reactivated: int = 0
    file_summaries: list[dict[str, int | str | list[str]]] = field(default_factory=list)
    created_categories: list[CreatedCategoryRecord] = field(default_factory=list)
    row_issues: list[CategorizedImportRowIssue] = field(default_factory=list)

    @property
    def errors_count(self) -> int:
        return self.rows_not_found + self.rows_supplier_mismatch + self.rows_unresolved_category + self.rows_skipped_invalid


class CategorizedSupplierCategoryImportService:
    def __init__(self, *, batch_size: int = 1000) -> None:
        self._batch_size = max(100, int(batch_size))
        self._category_resolver = _CategoryTreeResolver()

    def import_from_files(
        self,
        *,
        file_paths: Sequence[Path],
        supplier_filter: set[str] | None = None,
        strict_supplier_match: bool = True,
    ) -> CategorizedImportStats:
        stats = CategorizedImportStats()
        supplier_filter = {item.strip().lower() for item in (supplier_filter or set()) if item.strip()}

        rows: list[CategorizedSupplierRow] = []
        seen_ids: set[str] = set()

        for file_path in file_paths:
            parse_result = parse_categorized_supplier_xlsx(
                file_path=file_path,
                default_supplier_code=_infer_supplier_code_from_file_name(file_path.name),
            )
            file_stats = self._append_parse_result(
                rows=rows,
                seen_ids=seen_ids,
                parse_result=parse_result,
                supplier_filter=supplier_filter,
            )
            stats.files_processed += 1
            stats.rows_total += parse_result.total_rows
            stats.rows_parsed += file_stats["rows_kept"]
            stats.rows_skipped_invalid += parse_result.invalid_rows
            stats.rows_skipped_duplicate += parse_result.duplicate_row_ids + file_stats["rows_duplicate_global"]
            stats.rows_skipped_supplier_filter += file_stats["rows_skipped_supplier_filter"]
            stats.file_summaries.append(file_stats)

        self._import_rows(rows=rows, stats=stats, strict_supplier_match=strict_supplier_match)
        stats.categories_created = self._category_resolver.created_count
        stats.categories_reactivated = self._category_resolver.reactivated_count
        stats.created_categories = list(self._category_resolver.created_records)
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

    def _append_parse_result(
        self,
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

    def _import_rows(
        self,
        *,
        rows: list[CategorizedSupplierRow],
        stats: CategorizedImportStats,
        strict_supplier_match: bool,
    ) -> None:
        if not rows:
            return

        categories_by_path = self._resolve_categories_by_path(rows=rows)
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

        for offer_chunk_ids in _chunked(raw_offer_ids, self._batch_size):
            offers = SupplierRawOffer.objects.select_related("source", "supplier").filter(id__in=offer_chunk_ids)
            offers_by_id = {str(item.id): item for item in offers}
            to_update: list[SupplierRawOffer] = []

            for raw_offer_id in offer_chunk_ids:
                row = row_map[raw_offer_id]
                raw_offer = offers_by_id.get(raw_offer_id)
                if raw_offer is None:
                    stats.rows_not_found += 1
                    stats.row_issues.append(
                        CategorizedImportRowIssue(
                            supplier_code=row.supplier_code,
                            raw_offer_id=row.raw_offer_id,
                            row_number=row.row_number,
                            file_name=row.file_name,
                            article=row.article,
                            error_code="raw_offer_not_found",
                            message="SupplierRawOffer not found by source_row_id.",
                        )
                    )
                    continue

                source_code = str(getattr(raw_offer.source, "code", "")).strip().lower()
                supplier_code = str(getattr(raw_offer.supplier, "code", "")).strip().lower()
                if strict_supplier_match and row.supplier_code and row.supplier_code not in {source_code, supplier_code}:
                    stats.rows_supplier_mismatch += 1
                    stats.row_issues.append(
                        CategorizedImportRowIssue(
                            supplier_code=row.supplier_code,
                            raw_offer_id=row.raw_offer_id,
                            row_number=row.row_number,
                            file_name=row.file_name,
                            article=row.article,
                            error_code="supplier_mismatch",
                            message=f"Supplier mismatch: row supplier '{row.supplier_code}' vs offer source '{source_code}'.",
                        )
                    )
                    continue

                category = categories_by_path.get(row.target_category_path)
                if category is None:
                    stats.rows_unresolved_category += 1
                    stats.row_issues.append(
                        CategorizedImportRowIssue(
                            supplier_code=row.supplier_code,
                            raw_offer_id=row.raw_offer_id,
                            row_number=row.row_number,
                            file_name=row.file_name,
                            article=row.article,
                            error_code="category_path_unresolved",
                            message=f"Unable to resolve category path: {' > '.join(row.target_category_path)}.",
                        )
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
                SupplierRawOffer.objects.bulk_update(to_update, updated_fields, batch_size=self._batch_size)

    def _resolve_categories_by_path(
        self,
        *,
        rows: list[CategorizedSupplierRow],
    ) -> dict[tuple[str, ...], Category | None]:
        rows_by_path: dict[tuple[str, ...], list[CategorizedSupplierRow]] = defaultdict(list)
        for row in rows:
            rows_by_path[row.target_category_path].append(row)

        resolved: dict[tuple[str, ...], Category | None] = {}
        for path, path_rows in rows_by_path.items():
            create_path = any(item.new_category_needed for item in path_rows)
            category = self._category_resolver.ensure_path(path) if create_path else self._category_resolver.resolve_path(path)
            resolved[path] = category
        return resolved


class _CategoryTreeResolver:
    def __init__(self) -> None:
        self._children: dict[tuple[str | None, str], Category] = {}
        self._path_cache: dict[str, tuple[str, ...]] = {}
        self._by_id: dict[str, Category] = {}
        self._reserved_slugs: set[str] = set(Category.objects.values_list("slug", flat=True))
        self.created_count = 0
        self.reactivated_count = 0
        self.created_records: list[CreatedCategoryRecord] = []
        self._build_index()

    def _build_index(self) -> None:
        categories = list(Category.objects.select_related("parent").order_by("id"))
        for category in categories:
            self._register(category)

    def resolve_path(self, path: tuple[str, ...]) -> Category | None:
        current: Category | None = None
        for segment in path:
            current = self._find_child(parent=current, name=segment)
            if current is None:
                return None
        return current

    def ensure_path(self, path: tuple[str, ...]) -> Category | None:
        current: Category | None = None
        traversed: list[str] = []
        for segment in path:
            category = self._find_child(parent=current, name=segment)
            if category is None:
                name = sanitize_category_name(segment)
                if not name:
                    return None

                name_uk, name_ru, name_en = build_category_i18n_names(name)
                category = Category.objects.create(
                    parent=current,
                    name=name_uk or name,
                    name_uk=name_uk or name,
                    name_ru=name_ru or name,
                    name_en=name_en or name,
                    slug=generate_unique_category_slug(name=name, reserved_slugs=self._reserved_slugs),
                    is_active=True,
                )
                self.created_count += 1
                self._register(category)
                current_path = tuple((*traversed, name))
                self.created_records.append(
                    CreatedCategoryRecord(
                        category_id=str(category.id),
                        category_name=category.name_uk or category.name,
                        category_path=" > ".join(current_path),
                        parent_path=" > ".join(current_path[:-1]) if current_path[:-1] else "ROOT",
                    )
                )
                current = category
                traversed.append(name)
                continue

            if not category.is_active:
                category.is_active = True
                category.save(update_fields=("is_active", "updated_at"))
                self.reactivated_count += 1
            current = category
            traversed.append(category.name_uk or category.name)
        return current

    def _find_child(self, *, parent: Category | None, name: str) -> Category | None:
        parent_key = str(parent.id) if parent is not None else None
        clean_name = sanitize_category_name(name)
        if not clean_name:
            return None

        cached = self._children.get((parent_key, _normalized_name(clean_name)))
        if cached is not None:
            return cached

        resolved = find_category_by_normalized_name(name=clean_name, parent=parent)
        if resolved is not None:
            self._register(resolved)
        return resolved

    def _register(self, category: Category) -> None:
        category_id = str(category.id)
        self._by_id[category_id] = category
        parent_key = str(category.parent_id) if category.parent_id else None
        key = (parent_key, _normalized_name(category.name_uk or category.name))
        self._children.setdefault(key, category)
        self._path_cache[category_id] = self._build_path_tuple(category=category)

    def _build_path_tuple(self, *, category: Category) -> tuple[str, ...]:
        category_id = str(category.id)
        cached = self._path_cache.get(category_id)
        if cached is not None:
            return cached

        names: list[str] = []
        seen: set[str] = set()
        current = category
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            names.append(current.name_uk or current.name)
            if not current.parent_id:
                break
            current = self._by_id.get(str(current.parent_id))
        names.reverse()
        return tuple(item for item in names if item)


def _infer_supplier_code_from_file_name(file_name: str) -> str | None:
    normalized = file_name.lower()
    if "gpl" in normalized:
        return "gpl"
    if "utr" in normalized:
        return "utr"
    return None


def _normalized_name(value: str) -> str:
    return "".join(sanitize_category_name(value).lower().split())


def _chunked(values: Iterable[str], chunk_size: int) -> Iterable[list[str]]:
    chunk: list[str] = []
    for item in values:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
