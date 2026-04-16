from __future__ import annotations

from django.utils.text import slugify

from apps.catalog.models import Product


def sanitize_product_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def generate_unique_product_slug(
    *,
    name: str,
    preferred_slug: str = "",
    exclude_product_id: str | None = None,
) -> str:
    source = preferred_slug or name
    base = slugify(source).strip("-")
    if not base:
        base = "product"

    base = base[:300]
    if not base:
        base = "product"

    candidate = base
    index = 2

    while True:
        queryset = Product.objects.filter(slug=candidate)
        if exclude_product_id:
            queryset = queryset.exclude(id=exclude_product_id)
        if not queryset.exists():
            return candidate

        suffix = f"-{index}"
        candidate = f"{base[: max(1, 300 - len(suffix))]}{suffix}"
        index += 1
