from __future__ import annotations

from apps.catalog.models import Category

from .normalizers import normalize_text, tokenize
from .types import CategoryIndexEntry


class CategoryIndex:
    def __init__(
        self,
        *,
        entries: tuple[CategoryIndexEntry, ...],
        by_category_id: dict[str, CategoryIndexEntry],
        exact_name_lookup: dict[str, tuple[CategoryIndexEntry, ...]],
        exact_path_lookup: dict[str, tuple[CategoryIndexEntry, ...]],
        token_lookup: dict[str, tuple[CategoryIndexEntry, ...]],
    ) -> None:
        self.entries = entries
        self.by_category_id = by_category_id
        self.exact_name_lookup = exact_name_lookup
        self.exact_path_lookup = exact_path_lookup
        self.token_lookup = token_lookup

    @classmethod
    def build(cls) -> "CategoryIndex":
        categories = list(
            Category.objects.filter(is_active=True)
            .only("id", "name", "name_uk", "name_ru", "name_en", "parent_id")
            .order_by("name")
        )
        categories_by_id = {str(item.id): item for item in categories}
        has_children = {str(item.parent_id) for item in categories if item.parent_id}

        entries: list[CategoryIndexEntry] = []
        exact_name_lookup: dict[str, list[CategoryIndexEntry]] = {}
        exact_path_lookup: dict[str, list[CategoryIndexEntry]] = {}
        token_lookup: dict[str, list[CategoryIndexEntry]] = {}

        for category in categories:
            names = tuple(
                item
                for item in {
                    normalize_text(category.name),
                    normalize_text(category.name_uk),
                    normalize_text(category.name_ru),
                    normalize_text(category.name_en),
                }
                if item
            )
            path = cls._build_path(category=category, categories_by_id=categories_by_id)
            path_normalized = normalize_text(path)
            token_pool = set()
            for name in names:
                token_pool.update(tokenize(name))
            token_pool.update(tokenize(path_normalized))
            primary_tokens = tokenize(names[0] if names else path_normalized)
            is_leaf = str(category.id) not in has_children

            entry = CategoryIndexEntry(
                category=category,
                path=path,
                path_normalized=path_normalized,
                is_leaf=is_leaf,
                names_normalized=names,
                token_pool=frozenset(token_pool),
                primary_tokens=frozenset(primary_tokens),
            )
            entries.append(entry)

            for value in names:
                exact_name_lookup.setdefault(value, []).append(entry)
            if path_normalized:
                exact_path_lookup.setdefault(path_normalized, []).append(entry)

            for token in entry.token_pool:
                token_lookup.setdefault(token, []).append(entry)

        return cls(
            entries=tuple(entries),
            by_category_id={str(item.category.id): item for item in entries},
            exact_name_lookup={key: tuple(value) for key, value in exact_name_lookup.items()},
            exact_path_lookup={key: tuple(value) for key, value in exact_path_lookup.items()},
            token_lookup={key: tuple(value) for key, value in token_lookup.items()},
        )

    @staticmethod
    def _build_path(*, category: Category, categories_by_id: dict[str, Category]) -> str:
        items: list[str] = []
        seen: set[str] = set()
        current: Category | None = category
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            items.append(current.name_uk or current.name or "")
            if not current.parent_id:
                break
            current = categories_by_id.get(str(current.parent_id))

        items.reverse()
        return " / ".join(item for item in items if item.strip())
