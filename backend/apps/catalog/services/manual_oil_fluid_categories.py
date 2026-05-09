from __future__ import annotations

from dataclasses import dataclass


MANUAL_OIL_FLUID_ROOT_SLUG = "to-i-raskhodniki"


@dataclass(frozen=True)
class ManualOilFluidCategorySpec:
    slug: str
    name: str
    name_uk: str
    name_ru: str
    name_en: str
    sort_order: int


MANUAL_OIL_FLUID_CATEGORY_SPECS: tuple[ManualOilFluidCategorySpec, ...] = (
    ManualOilFluidCategorySpec(
        slug="motornye-masla",
        name="Моторные масла",
        name_uk="Моторні оливи",
        name_ru="Моторные масла",
        name_en="Engine oils",
        sort_order=120,
    ),
    ManualOilFluidCategorySpec(
        slug="transmissionnye-masla",
        name="Трансмиссионные масла",
        name_uk="Трансмісійні оливи",
        name_ru="Трансмиссионные масла",
        name_en="Transmission oils",
        sort_order=130,
    ),
    ManualOilFluidCategorySpec(
        slug="gidravlicheskie-masla",
        name="Гидравлические масла",
        name_uk="Гідравлічні оливи",
        name_ru="Гидравлические масла",
        name_en="Hydraulic oils",
        sort_order=140,
    ),
    ManualOilFluidCategorySpec(
        slug="tekhnicheskie-zhidkosti",
        name="Технические жидкости",
        name_uk="Технічні рідини",
        name_ru="Технические жидкости",
        name_en="Technical fluids",
        sort_order=150,
    ),
    ManualOilFluidCategorySpec(
        slug="antifrizy-i-okhlazhdaiushchie-zhidkosti",
        name="Антифризы и охлаждающие жидкости",
        name_uk="Антифризи та охолоджувальні рідини",
        name_ru="Антифризы и охлаждающие жидкости",
        name_en="Antifreeze and coolants",
        sort_order=160,
    ),
    ManualOilFluidCategorySpec(
        slug="tormoznye-zhidkosti",
        name="Тормозные жидкости",
        name_uk="Гальмівні рідини",
        name_ru="Тормозные жидкости",
        name_en="Brake fluids",
        sort_order=170,
    ),
)
