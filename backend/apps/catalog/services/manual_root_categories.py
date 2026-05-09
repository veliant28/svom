from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Category


@dataclass(frozen=True)
class ManualRootCategorySpec:
    slug: str
    name: str
    name_uk: str
    name_ru: str
    name_en: str
    sort_order: int


MANUAL_ROOT_CATEGORY_SPECS: tuple[ManualRootCategorySpec, ...] = (
    ManualRootCategorySpec(
        slug="zapchasti-dlia-to",
        name="Запчасти для ТО",
        name_uk="Запчастини для ТО",
        name_ru="Запчасти для ТО",
        name_en="Maintenance parts",
        sort_order=10,
    ),
    ManualRootCategorySpec(
        slug="podveska-i-rulevoe",
        name="Подвеска и рулевое",
        name_uk="Підвіска та кермове",
        name_ru="Подвеска и рулевое",
        name_en="Suspension and steering",
        sort_order=20,
    ),
    ManualRootCategorySpec(
        slug="tormoznaia-sistema",
        name="Тормозная система",
        name_uk="Гальмівна система",
        name_ru="Тормозная система",
        name_en="Brake system",
        sort_order=30,
    ),
    ManualRootCategorySpec(
        slug="okhlazhdenie-i-otoplenie",
        name="Охлаждение и отопление",
        name_uk="Охолодження та опалення",
        name_ru="Охлаждение и отопление",
        name_en="Cooling and heating",
        sort_order=40,
    ),
    ManualRootCategorySpec(
        slug="dvigatel-i-vykhlop",
        name="Двигатель и выхлоп",
        name_uk="Двигун і вихлоп",
        name_ru="Двигатель и выхлоп",
        name_en="Engine and exhaust",
        sort_order=50,
    ),
    ManualRootCategorySpec(
        slug="stseplenie-i-transmissiia",
        name="Сцепление и трансмиссия",
        name_uk="Зчеплення і трансмісія",
        name_ru="Сцепление и трансмиссия",
        name_en="Clutch and transmission",
        sort_order=60,
    ),
    ManualRootCategorySpec(
        slug="elektrika-i-osveshchenie",
        name="Электрика и освещение",
        name_uk="Електрика та освітлення",
        name_ru="Электрика и освещение",
        name_en="Electrical and lighting",
        sort_order=70,
    ),
    ManualRootCategorySpec(
        slug="detali-kuzova",
        name="Детали кузова",
        name_uk="Деталі кузова",
        name_ru="Детали кузова",
        name_en="Body parts",
        sort_order=80,
    ),
    ManualRootCategorySpec(
        slug="kolesa-i-shiny",
        name="Колёса и шины",
        name_uk="Колеса та шини",
        name_ru="Колёса и шины",
        name_en="Wheels and tires",
        sort_order=90,
    ),
    ManualRootCategorySpec(
        slug="avtohimiia-i-aksessuary",
        name="Автохимия и аксессуары",
        name_uk="Автохімія та аксесуари",
        name_ru="Автохимия и аксессуары",
        name_en="Car chemicals and accessories",
        sort_order=100,
    ),
)


def manual_root_spec_by_slug() -> dict[str, ManualRootCategorySpec]:
    return {item.slug: item for item in MANUAL_ROOT_CATEGORY_SPECS}


def manual_root_names_casefold() -> set[str]:
    out: set[str] = set()
    for spec in MANUAL_ROOT_CATEGORY_SPECS:
        out.add(" ".join(spec.name.split()).casefold())
        out.add(" ".join(spec.name_uk.split()).casefold())
        out.add(" ".join(spec.name_ru.split()).casefold())
    return out


def get_manual_roots_queryset():
    slugs = [item.slug for item in MANUAL_ROOT_CATEGORY_SPECS]
    return Category.objects.filter(parent__isnull=True, slug__in=slugs)
