from __future__ import annotations

import re
import unicodedata

from django.db.models import QuerySet
from django.utils.text import slugify

from apps.catalog.models import Category


def sanitize_category_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalized_category_name(value: str) -> str:
    cleaned = sanitize_category_name(value).lower()
    if not cleaned:
        return ""
    normalized = unicodedata.normalize("NFKD", cleaned)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-zа-яіїєґ0-9]+", " ", normalized, flags=re.IGNORECASE)
    return "".join(normalized.split())


def find_category_by_normalized_name(
    *,
    name: str,
    parent: Category | None,
    exclude_category_id: str | None = None,
) -> Category | None:
    target = normalized_category_name(name)
    if not target:
        return None

    queryset: QuerySet[Category] = Category.objects.filter(parent=parent)
    if exclude_category_id:
        queryset = queryset.exclude(id=exclude_category_id)

    exact = queryset.filter(name__iexact=sanitize_category_name(name)).order_by("id").first()
    if exact is not None:
        return exact

    for category in queryset.only("id", "name").iterator(chunk_size=500):
        if normalized_category_name(category.name) == target:
            return category
    return None


def generate_unique_category_slug(
    *,
    name: str,
    preferred_slug: str = "",
    exclude_category_id: str | None = None,
    reserved_slugs: set[str] | None = None,
) -> str:
    source = preferred_slug or name
    base = slugify(source).strip("-")
    if not base:
        normalized = normalized_category_name(name)
        base = normalized or "category"

    base = base[:220]
    if not base:
        base = "category"

    candidate = base
    index = 2

    def is_taken(value: str) -> bool:
        if reserved_slugs is not None and value in reserved_slugs:
            return True
        queryset = Category.objects.filter(slug=value)
        if exclude_category_id:
            queryset = queryset.exclude(id=exclude_category_id)
        return queryset.exists()

    while is_taken(candidate):
        suffix = f"-{index}"
        candidate = f"{base[: max(1, 220 - len(suffix))]}{suffix}"
        index += 1

    if reserved_slugs is not None:
        reserved_slugs.add(candidate)
    return candidate
