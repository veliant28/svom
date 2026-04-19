from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .types import CategoryMappingCommandOptions


def normalize_options(raw_options: Mapping[str, Any]) -> CategoryMappingCommandOptions:
    supplier_codes = tuple(
        str(item).strip().lower()
        for item in (raw_options.get("supplier") or [])
        if str(item).strip()
    )
    batch_size = max(50, int(raw_options.get("batch_size") or 500))

    return CategoryMappingCommandOptions(
        supplier_codes=supplier_codes,
        batch_size=batch_size,
        limit=raw_options.get("limit"),
        dry_run=bool(raw_options.get("dry_run")),
        overwrite_manual=bool(raw_options.get("overwrite_manual")),
        force_map_all=bool(raw_options.get("force_map_all")),
        recheck_risky_mappings=bool(raw_options.get("recheck_risky_mappings")),
        recheck_guardrail_codes=_normalized_tuple(raw_options.get("recheck_guardrail_codes")),
        recheck_reasons=_normalized_tuple(raw_options.get("recheck_reason")),
        recheck_category_names=_normalized_tuple(raw_options.get("recheck_category_name")),
        recheck_title_patterns=_normalized_tuple(raw_options.get("recheck_title_pattern")),
    )


def _normalized_tuple(values: Any) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in (values or []) if str(item).strip())
