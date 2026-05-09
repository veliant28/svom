from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Category
from apps.catalog.services.category_management import normalized_category_name, sanitize_category_name


@dataclass(frozen=True)
class CanonicalCategorySpec:
    root_slug: str
    canonical_slug: str
    name_uk: str
    name_ru: str
    name_en: str
    aliases: tuple[str, ...]

    @property
    def canonical_name(self) -> str:
        return self.name_ru or self.name_uk


CANONICAL_CATEGORY_SPECS: tuple[CanonicalCategorySpec, ...] = (
    CanonicalCategorySpec(
        root_slug="elektrika-i-osveshchenie",
        canonical_slug="akkumuliatory",
        name_uk="Акумулятори",
        name_ru="Аккумуляторы",
        name_en="Batteries",
        aliases=(
            "аккумулятор",
            "аккумуляторы",
            "акумулятор",
            "акумулятори",
            "battery",
            "batteries",
            "accumulator",
            "accumulators",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="podveska-i-rulevoe",
        canonical_slug="amortizatory",
        name_uk="Амортизатори",
        name_ru="Амортизаторы",
        name_en="Shock absorbers",
        aliases=(
            "амортизатор",
            "амортизаторы",
            "амортизатори",
            "shock absorber",
            "shock absorbers",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="avtohimiia-i-aksessuary",
        canonical_slug="motornoe-maslo",
        name_uk="Моторна олива",
        name_ru="Моторное масло",
        name_en="Engine oil",
        aliases=(
            "масло моторное",
            "моторное масло",
            "моторна олива",
            "олива моторна",
            "engine oil",
            "motor oil",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="dvigatel-i-vykhlop",
        canonical_slug="vozdushnyi-filtr",
        name_uk="Повітряний фільтр",
        name_ru="Воздушный фильтр",
        name_en="Air filter",
        aliases=(
            "фильтр воздушный",
            "воздушный фильтр",
            "повітряний фільтр",
            "фільтр повітряний",
            "air filter",
            "air filters",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="dvigatel-i-vykhlop",
        canonical_slug="maslianyi-filtr",
        name_uk="Масляний фільтр",
        name_ru="Масляный фильтр",
        name_en="Oil filter",
        aliases=(
            "фильтр масляный",
            "масляный фильтр",
            "оливний фільтр",
            "масляний фільтр",
            "oil filter",
            "oil filters",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="dvigatel-i-vykhlop",
        canonical_slug="toplivnyi-filtr",
        name_uk="Паливний фільтр",
        name_ru="Топливный фильтр",
        name_en="Fuel filter",
        aliases=(
            "фильтр топливный",
            "топливный фильтр",
            "паливний фільтр",
            "фільтр паливний",
            "fuel filter",
            "fuel filters",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="dvigatel-i-vykhlop",
        canonical_slug="filtr-salona",
        name_uk="Фільтр салону",
        name_ru="Фильтр салона",
        name_en="Cabin filter",
        aliases=(
            "фильтр салона",
            "салонный фильтр",
            "фільтр салону",
            "салонний фільтр",
            "cabin filter",
            "cabin filters",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="dvigatel-i-vykhlop",
        canonical_slug="glushitel",
        name_uk="Глушник",
        name_ru="Глушитель",
        name_en="Muffler",
        aliases=(
            "глушитель",
            "глушители",
            "глушник",
            "глушники",
            "muffler",
            "mufflers",
        ),
    ),
    CanonicalCategorySpec(
        root_slug="tormoznaia-sistema",
        canonical_slug="tormoznye-kolodki",
        name_uk="Гальмівні колодки",
        name_ru="Тормозные колодки",
        name_en="Brake pads",
        aliases=(
            "тормозные колодки",
            "тормозная колодка",
            "гальмівні колодки",
            "гальмівна колодка",
            "brake pad",
            "brake pads",
        ),
    ),
)


def canonical_specs_by_slug() -> dict[str, CanonicalCategorySpec]:
    return {item.canonical_slug: item for item in CANONICAL_CATEGORY_SPECS}


def _normalized_alias_map() -> dict[str, CanonicalCategorySpec]:
    out: dict[str, CanonicalCategorySpec] = {}
    for spec in CANONICAL_CATEGORY_SPECS:
        for raw in spec.aliases:
            key = normalized_category_name(raw)
            if key:
                out[key] = spec
        for raw in (spec.name_ru, spec.name_uk, spec.name_en):
            key = normalized_category_name(raw)
            if key:
                out[key] = spec
    return out


_ALIASES = _normalized_alias_map()


def resolve_canonical_spec_for_name(name: str) -> CanonicalCategorySpec | None:
    key = normalized_category_name(name)
    if not key:
        return None
    return _ALIASES.get(key)


def resolve_canonical_display_name(name: str) -> str:
    spec = resolve_canonical_spec_for_name(name)
    if spec is None:
        return sanitize_category_name(name)
    return spec.canonical_name


def find_semantic_category_under_parent(
    *,
    parent: Category | None,
    name: str,
    include_inactive: bool = False,
) -> Category | None:
    normalized = normalized_category_name(name)
    if not normalized:
        return None

    spec = resolve_canonical_spec_for_name(name)
    queryset = Category.objects.filter(parent=parent)
    if not include_inactive:
        queryset = queryset.filter(is_active=True)

    if spec is not None:
        preferred = (
            queryset.filter(slug=spec.canonical_slug).order_by("id").first()
            or queryset.filter(name__iexact=spec.name_ru).order_by("id").first()
            or queryset.filter(name_uk__iexact=spec.name_uk).order_by("id").first()
            or queryset.filter(name_en__iexact=spec.name_en).order_by("id").first()
        )
        if preferred is not None:
            return preferred

    exact = queryset.filter(name__iexact=sanitize_category_name(name)).order_by("id").first()
    if exact is not None:
        return exact

    for category in queryset.only("id", "name", "name_uk", "name_ru", "name_en", "slug").iterator(chunk_size=300):
        normalized_values = {
            normalized_category_name(category.name),
            normalized_category_name(category.name_uk),
            normalized_category_name(category.name_ru),
            normalized_category_name(category.name_en),
        }
        if normalized in normalized_values:
            return category
        if spec is not None:
            for alias in spec.aliases:
                alias_key = normalized_category_name(alias)
                if alias_key and alias_key in normalized_values:
                    return category
    return None
