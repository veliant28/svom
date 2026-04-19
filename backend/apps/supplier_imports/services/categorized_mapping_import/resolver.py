from __future__ import annotations

from apps.catalog.models import Category
from apps.catalog.services import (
    build_category_i18n_names,
    find_category_by_normalized_name,
    generate_unique_category_slug,
    sanitize_category_name,
)

from .types import CreatedCategoryRecord


class CategoryTreeResolver:
    def __init__(self) -> None:
        self._children: dict[tuple[str | None, str], Category] = {}
        self._path_cache: dict[str, tuple[str, ...]] = {}
        self._by_id: dict[str, Category] = {}
        self._reserved_slugs: set[str] = set(Category.objects.values_list("slug", flat=True))
        self.created_count = 0
        self.reactivated_count = 0
        self.created_records: list[CreatedCategoryRecord] = []
        self._build_index()

    def _build_index(self) -> None:
        categories = list(Category.objects.select_related("parent").order_by("id"))
        for category in categories:
            self._register(category)

    def resolve_path(self, path: tuple[str, ...]) -> Category | None:
        current: Category | None = None
        for segment in path:
            current = self._find_child(parent=current, name=segment)
            if current is None:
                return None
        return current

    def ensure_path(self, path: tuple[str, ...]) -> Category | None:
        current: Category | None = None
        traversed: list[str] = []
        for segment in path:
            category = self._find_child(parent=current, name=segment)
            if category is None:
                name = sanitize_category_name(segment)
                if not name:
                    return None

                name_uk, name_ru, name_en = build_category_i18n_names(name)
                category = Category.objects.create(
                    parent=current,
                    name=name_uk or name,
                    name_uk=name_uk or name,
                    name_ru=name_ru or name,
                    name_en=name_en or name,
                    slug=generate_unique_category_slug(name=name, reserved_slugs=self._reserved_slugs),
                    is_active=True,
                )
                self.created_count += 1
                self._register(category)
                current_path = tuple((*traversed, name))
                self.created_records.append(
                    CreatedCategoryRecord(
                        category_id=str(category.id),
                        category_name=category.name_uk or category.name,
                        category_path=" > ".join(current_path),
                        parent_path=" > ".join(current_path[:-1]) if current_path[:-1] else "ROOT",
                    )
                )
                current = category
                traversed.append(name)
                continue

            if not category.is_active:
                category.is_active = True
                category.save(update_fields=("is_active", "updated_at"))
                self.reactivated_count += 1
            current = category
            traversed.append(category.name_uk or category.name)
        return current

    def _find_child(self, *, parent: Category | None, name: str) -> Category | None:
        parent_key = str(parent.id) if parent is not None else None
        clean_name = sanitize_category_name(name)
        if not clean_name:
            return None

        cached = self._children.get((parent_key, normalized_name(clean_name)))
        if cached is not None:
            return cached

        resolved = find_category_by_normalized_name(name=clean_name, parent=parent)
        if resolved is not None:
            self._register(resolved)
        return resolved

    def _register(self, category: Category) -> None:
        category_id = str(category.id)
        self._by_id[category_id] = category
        parent_key = str(category.parent_id) if category.parent_id else None
        key = (parent_key, normalized_name(category.name_uk or category.name))
        self._children.setdefault(key, category)
        self._path_cache[category_id] = self._build_path_tuple(category=category)

    def _build_path_tuple(self, *, category: Category) -> tuple[str, ...]:
        category_id = str(category.id)
        cached = self._path_cache.get(category_id)
        if cached is not None:
            return cached

        names: list[str] = []
        seen: set[str] = set()
        current = category
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            names.append(current.name_uk or current.name)
            if not current.parent_id:
                break
            current = self._by_id.get(str(current.parent_id))
        names.reverse()
        return tuple(item for item in names if item)


def normalized_name(value: str) -> str:
    return "".join(sanitize_category_name(value).lower().split())
