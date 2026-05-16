from __future__ import annotations

from apps.supplier_imports.parsers.utils import normalize_brand


def sanitize_brand_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalized_brand_name(value: str) -> str:
    return normalize_brand(sanitize_brand_name(value))
