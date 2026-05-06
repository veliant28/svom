from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def find_column_name(columns: Iterable[str], candidates: list[str]) -> str | None:
    by_lower = {str(item).lower(): str(item) for item in columns}
    for candidate in candidates:
        found = by_lower.get(str(candidate).lower())
        if found:
            return found
    return None


def find_column(row: Mapping[str, Any], candidates: list[str]) -> str | None:
    return find_column_name(row.keys(), candidates)


def find_value(row: Mapping[str, Any], candidates: list[str]) -> Any:
    key = find_column(row, candidates)
    if key is None:
        return None
    return row.get(key)
