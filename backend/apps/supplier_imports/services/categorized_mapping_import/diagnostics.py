from __future__ import annotations

import logging

from apps.supplier_imports.services.categorized_mapping_import_parser import CategorizedSupplierRow

from .types import CategorizedImportRowIssue, CategorizedImportStats

logger = logging.getLogger(__name__)


def add_row_issue(
    *,
    stats: CategorizedImportStats,
    row: CategorizedSupplierRow,
    error_code: str,
    message: str,
) -> None:
    stats.row_issues.append(
        CategorizedImportRowIssue(
            supplier_code=row.supplier_code,
            raw_offer_id=row.raw_offer_id,
            row_number=row.row_number,
            file_name=row.file_name,
            article=row.article,
            error_code=error_code,
            message=message,
        )
    )
