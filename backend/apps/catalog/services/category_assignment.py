from __future__ import annotations

from apps.catalog.models import Category


def can_assign_products_to_category(category: Category | None) -> bool:
    return bool(category is not None and category.is_active and category.is_assignable)


def assignable_category_or_none(category: Category | None) -> Category | None:
    if can_assign_products_to_category(category):
        return category
    return None
