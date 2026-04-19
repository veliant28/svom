from __future__ import annotations

from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


def normalize_article_value(value: str) -> str:
    return normalize_article(value)


def normalize_brand_value(value: str) -> str:
    return normalize_brand(value)
