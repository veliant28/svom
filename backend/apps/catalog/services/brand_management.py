from __future__ import annotations

from django.utils.text import slugify

from apps.catalog.models import Brand
from apps.supplier_imports.parsers.utils import normalize_brand


def sanitize_brand_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalized_brand_name(value: str) -> str:
    return normalize_brand(sanitize_brand_name(value))


def find_brand_by_normalized_name(*, name: str, exclude_brand_id: str | None = None) -> Brand | None:
    target = normalized_brand_name(name)
    if not target:
        return None

    queryset = Brand.objects.all()
    if exclude_brand_id:
        queryset = queryset.exclude(id=exclude_brand_id)

    exact = queryset.filter(name__iexact=sanitize_brand_name(name)).order_by("id").first()
    if exact is not None:
        return exact

    for brand in queryset.only("id", "name").iterator(chunk_size=500):
        if normalized_brand_name(brand.name) == target:
            return brand
    return None


def generate_unique_brand_slug(
    *,
    name: str,
    preferred_slug: str = "",
    exclude_brand_id: str | None = None,
    reserved_slugs: set[str] | None = None,
) -> str:
    source = preferred_slug or name
    base = slugify(source).strip("-")
    if not base:
        normalized = normalized_brand_name(name).lower()
        base = normalized or "brand"

    base = base[:140]
    if not base:
        base = "brand"

    candidate = base
    index = 2

    def is_taken(value: str) -> bool:
        if reserved_slugs is not None and value in reserved_slugs:
            return True
        queryset = Brand.objects.filter(slug=value)
        if exclude_brand_id:
            queryset = queryset.exclude(id=exclude_brand_id)
        return queryset.exists()

    while is_taken(candidate):
        suffix = f"-{index}"
        candidate = f"{base[: max(1, 140 - len(suffix))]}{suffix}"
        index += 1

    if reserved_slugs is not None:
        reserved_slugs.add(candidate)
    return candidate
