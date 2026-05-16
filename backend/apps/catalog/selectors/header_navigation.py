from __future__ import annotations

from typing import Any

from django.core.cache import cache

from apps.catalog.models import Category, CategoryNavigationCollection

_HEADER_NAVIGATION_CACHE_TTL_SECONDS = 300


def get_header_navigation_payload(*, locale: str | None = None) -> list[dict[str, Any]]:
    normalized_locale = (locale or "").strip().lower() or "default"
    cache_key = f"catalog:header_navigation:{normalized_locale}"
    cached_payload = cache.get(cache_key)
    if isinstance(cached_payload, list):
        return cached_payload

    roots = list(
        Category.objects.filter(
            is_active=True,
            parent__isnull=True,
            show_in_header=True,
            source=Category.SOURCE_MANUAL,
        )
        .order_by("sort_order", "name", "id")
        .prefetch_related("children")
    )
    if not roots:
        return []

    collections_by_root_id = {
        collection.root_category_id: collection
        for collection in CategoryNavigationCollection.objects.filter(
            is_active=True,
            show_in_header=True,
            root_category_id__in=[root.id for root in roots],
        )
        .select_related("root_category")
        .prefetch_related("groups__items__category")
        .order_by("sort_order", "title", "id")
    }

    payload: list[dict[str, Any]] = []
    for root in roots:
        collection = collections_by_root_id.get(root.id)
        sections = (
            _build_collection_sections(collection=collection, locale=locale)
            if collection is not None
            else _build_category_sections(root=root, locale=locale)
        )
        payload.append(
            {
                "id": str(root.id),
                "name": root.get_localized_name(locale),
                "slug": root.slug,
                "sections": sections,
            }
        )
    cache.set(cache_key, payload, timeout=_HEADER_NAVIGATION_CACHE_TTL_SECONDS)
    return payload


def _build_collection_sections(*, collection: CategoryNavigationCollection, locale: str | None) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for group in sorted(collection.groups.all(), key=lambda item: (item.sort_order, item.title, str(item.id))):
        if not group.is_active:
            continue
        items = []
        for nav_item in sorted(group.items.all(), key=lambda item: (item.sort_order, str(item.id))):
            category = nav_item.category
            if not nav_item.is_active or not category.is_active or not category.is_assignable:
                continue
            override = nav_item.get_localized_title(locale)
            items.append(_category_payload(category=category, locale=locale, name_override=override))
        if items:
            sections.append(
                {
                    "id": str(group.id),
                    "title": group.get_localized_title(locale),
                    "items": items,
                }
            )
    return sections


def _build_category_sections(*, root: Category, locale: str | None) -> list[dict[str, Any]]:
    children = list(
        Category.objects.filter(is_active=True, parent=root)
        .order_by("sort_order", "name", "id")
    )
    sections: list[dict[str, Any]] = []
    direct_items = []
    for child in children:
        if child.is_assignable:
            direct_items.append(_category_payload(category=child, locale=locale))
            continue
        leaf_items = [
            _category_payload(category=leaf, locale=locale)
            for leaf in Category.objects.filter(
                is_active=True,
                is_assignable=True,
                parent=child,
            ).order_by("sort_order", "name", "id")
        ]
        if leaf_items:
            sections.append(
                {
                    "id": str(child.id),
                    "title": child.get_localized_name(locale),
                    "items": leaf_items,
                }
            )

    if direct_items:
        sections.append(
            {
                "id": f"{root.id}-direct",
                "title": None,
                "items": direct_items,
            }
        )
    return sections


def _category_payload(*, category: Category, locale: str | None, name_override: str = "") -> dict[str, Any]:
    return {
        "id": str(category.id),
        "name": name_override or category.get_localized_name(locale),
        "slug": category.slug,
        "sort_order": int(category.sort_order or 0),
        "is_assignable": bool(category.is_assignable),
        "parent": {
            "id": str(category.parent_id),
            "name": category.parent.get_localized_name(locale) if category.parent_id and category.parent else "",
            "slug": category.parent.slug if category.parent_id and category.parent else "",
            "sort_order": int(category.parent.sort_order or 0) if category.parent_id and category.parent else 0,
        }
        if category.parent_id
        else None,
    }
