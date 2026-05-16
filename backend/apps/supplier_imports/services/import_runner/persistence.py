from __future__ import annotations

# Thin facade module to keep import surface stable while implementation
# is split into dedicated modules/files.
from .persistence_impl import (  # noqa: F401
    GplImportCategoryAssignmentResolver,
    attach_utr_detail_id,
    create_row_error,
    persist_current_offer_rows,
    persist_parsed_rows,
    persist_raw_history_rows,
    uses_current_offer_persistence,
)

__all__ = [
    "attach_utr_detail_id",
    "create_row_error",
    "GplImportCategoryAssignmentResolver",
    "persist_current_offer_rows",
    "persist_parsed_rows",
    "persist_raw_history_rows",
    "uses_current_offer_persistence",
]
