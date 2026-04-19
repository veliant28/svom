from __future__ import annotations

from dataclasses import dataclass, field


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
