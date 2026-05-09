from collections import defaultdict, deque
from typing import Any

from django.db.models import QuerySet

from apps.catalog.models import Category

HEADER_NAVIGATION_MAX_ROOTS = 10


def get_active_categories_queryset(*, scope: str | None = None) -> QuerySet[Category]:
    normalized_scope = (scope or "").strip().casefold()
    if normalized_scope == "header":
        root_rows = list(
            Category.objects.filter(
                is_active=True,
                parent__isnull=True,
                show_in_header=True,
                source=Category.SOURCE_MANUAL,
            )
            .order_by("sort_order", "name", "id")[:HEADER_NAVIGATION_MAX_ROOTS]
            .values_list("id", flat=True)
        )
        if not root_rows:
            return Category.objects.none()

        descendants = _collect_manual_descendant_ids(root_rows)
        if not descendants:
            return Category.objects.none()

        return (
            Category.objects.filter(
                is_active=True,
                id__in=descendants,
            )
            .select_related("parent")
            .order_by("sort_order", "name", "id")
        )

    return Category.objects.filter(is_active=True).select_related("parent").order_by("sort_order", "name", "id")


def _collect_manual_descendant_ids(root_ids: list[Any]) -> set[Any]:
    child_map: dict[Any, list[Any]] = defaultdict(list)
    for category_id, parent_id in Category.objects.filter(is_active=True).values_list("id", "parent_id"):
        if parent_id is None:
            continue
        child_map[parent_id].append(category_id)

    collected: set[Any] = set(root_ids)
    queue: deque[Any] = deque(root_ids)
    while queue:
        parent_id = queue.popleft()
        for child_id in child_map.get(parent_id, []):
            if child_id in collected:
                continue
            collected.add(child_id)
            queue.append(child_id)
    return collected
