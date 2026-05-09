from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.supplier_imports.parsers.utils import normalize_brand


MANUAL_CHEMICAL_ROOT_SLUG = "avtokhimiia-i-aksesuary"


@dataclass(frozen=True)
class ManualChemicalCategorySpec:
    slug: str
    name: str
    name_uk: str
    name_ru: str
    name_en: str
    sort_order: int


MANUAL_CHEMICAL_CATEGORY_SPECS: tuple[ManualChemicalCategorySpec, ...] = (
    ManualChemicalCategorySpec(
        slug="avtoemali-i-kraski",
        name="Автоэмали и краски",
        name_uk="Автоемалі та фарби",
        name_ru="Автоэмали и краски",
        name_en="Car enamels and paints",
        sort_order=210,
    ),
    ManualChemicalCategorySpec(
        slug="aerozolnye-kraski",
        name="Аэрозольные краски",
        name_uk="Аерозольні фарби",
        name_ru="Аэрозольные краски",
        name_en="Aerosol paints",
        sort_order=220,
    ),
    ManualChemicalCategorySpec(
        slug="grunty-i-laki",
        name="Грунты и лаки",
        name_uk="Ґрунти та лаки",
        name_ru="Грунты и лаки",
        name_en="Primers and varnishes",
        sort_order=230,
    ),
    ManualChemicalCategorySpec(
        slug="adblue-i-tekhnicheskie-zhidkosti",
        name="AdBlue и технические жидкости",
        name_uk="AdBlue та технічні рідини",
        name_ru="AdBlue и технические жидкости",
        name_en="AdBlue and technical fluids",
        sort_order=235,
    ),
    ManualChemicalCategorySpec(
        slug="ochistiteli-i-avtokhimiia",
        name="Очистители и автохимия",
        name_uk="Очисники та автохімія",
        name_ru="Очистители и автохимия",
        name_en="Cleaners and car chemicals",
        sort_order=240,
    ),
)


@dataclass(frozen=True)
class ManualChemicalPayloadFields:
    category: str
    group: str
    name: str
    description: str


@dataclass(frozen=True)
class ManualChemicalDecision:
    proposed_slug: str
    proposed_category: str
    confidence: float
    reason: str
    status: str


STATUS_SAFE = "safe_manual_category_candidate"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_SKIP = "skip"


PAINT_TOKENS = ("емал", "эмал", "фарб", "краск", "paint")
AEROSOL_TOKENS = ("аерозол", "аэрозол", "spray", "балончик", "баллончик")
PRIMER_TOKENS = ("грунт", "грунтовк", "primer", "лак", "varnish")
CHEMICAL_TOKENS = ("очистител", "очищувач", "полирол", "присад", "смазк", "мастил", "автохим")
NEGATIVE_NON_PAINT_TOKENS = (
    "круг",
    "наждач",
    "шлиф",
    "абразив",
    "бумага",
    "папір",
    "sponge",
    "губка",
    "комбинезон",
    "комбінезон",
    "очки",
    "окуляри",
    "перчатки",
    "рукавички",
    "салфетка",
    "серветка",
    "малярная лента",
    "стрічка",
    "masking tape",
    "защит",
    "спецодежда",
    "workwear",
    "инструмент",
    "аксессуар",
)
ADBLUE_TOKENS = (
    "adblue",
    "euroblue",
    "def",
    "мочевин",
    "сечовин",
    "urea",
    "техническая жидкост",
    "технічна рідин",
)
NON_CHEMICAL_TOKENS = ("амортиз", "аккумулятор", "акумулятор", "аптеч", "изолент", "підвіск", "подвеск")

BLOCKED_BRANDS = {
    "DAINTON",
    "AT",
    "HAGENBATTERIE",
    "NOVVIC",
}

BRAND_CHEM_PAINT = {"CSSYSTEM"}
BRAND_CHEM_MITKA = {"MITKA"}
BRAND_CHEM_CLEANER = {"K2"}
BRAND_ADBLUE = {"K2"}


def spec_by_slug() -> dict[str, ManualChemicalCategorySpec]:
    return {item.slug: item for item in MANUAL_CHEMICAL_CATEGORY_SPECS}


def extract_manual_chemical_payload_fields(raw_payload: dict[str, Any] | None) -> ManualChemicalPayloadFields:
    payload = raw_payload if isinstance(raw_payload, dict) else {}

    def _pick(*keys: str) -> str:
        for key in keys:
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        return ""

    return ManualChemicalPayloadFields(
        category=_pick("Категорія", "Категория", "category"),
        group=_pick("Група ТД", "Группа ТД", "group"),
        name=_pick("Найменування", "Наименование", "name", "title"),
        description=_pick("Опис", "Описание", "description"),
    )


def decide_manual_chemical_category(
    *,
    product_name: str,
    brand: str,
    payload: ManualChemicalPayloadFields,
) -> ManualChemicalDecision:
    brand_norm = normalize_brand(brand)

    text = " ".join(
        item
        for item in [
            str(product_name or "").strip(),
            payload.category,
            payload.group,
            payload.name,
            payload.description,
        ]
        if item
    )
    normalized_text = " ".join(text.lower().split())

    if brand_norm in BLOCKED_BRANDS:
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.0,
            reason="blocked_brand_for_this_stage",
            status=STATUS_SKIP,
        )

    has_non_chemical = _contains_any(normalized_text, NON_CHEMICAL_TOKENS)
    has_paint = _contains_any(normalized_text, PAINT_TOKENS)
    has_aerosol = _contains_any(normalized_text, AEROSOL_TOKENS)
    has_primer = _contains_any(normalized_text, PRIMER_TOKENS)
    has_chemical = _contains_any(normalized_text, CHEMICAL_TOKENS)
    has_adblue = _contains_any(normalized_text, ADBLUE_TOKENS)
    has_negative_non_paint = _contains_any(normalized_text, NEGATIVE_NON_PAINT_TOKENS)

    if has_non_chemical and not any((has_paint, has_aerosol, has_primer, has_chemical)):
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.0,
            reason="non_chemical_product",
            status=STATUS_SKIP,
        )

    if has_negative_non_paint and not (has_paint or has_primer):
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.82,
            reason="negative_keyword_blocker_non_paint",
            status=STATUS_NEEDS_REVIEW,
        )

    if has_negative_non_paint and (has_paint or has_primer):
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.75,
            reason="mixed_paint_and_negative_signals",
            status=STATUS_NEEDS_REVIEW,
        )

    if brand_norm in BRAND_CHEM_PAINT and not any((has_paint, has_aerosol)):
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.0,
            reason="brand_requires_paint_signal",
            status=STATUS_SKIP,
        )

    if brand_norm in BRAND_CHEM_MITKA and not any((has_paint, has_aerosol)):
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.0,
            reason="mitka_without_paint_signal",
            status=STATUS_SKIP,
        )

    # Aerosol alone is insufficient; keep paints strict.
    if has_aerosol and has_paint:
        return _safe("aerozolnye-kraski", 0.99, "aerosol_paint_signal")
    if has_aerosol and not has_paint:
        if has_chemical:
            return _safe("ochistiteli-i-avtokhimiia", 0.95, "aerosol_cleaner_signal")
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.72,
            reason="aerosol_without_paint_signal",
            status=STATUS_NEEDS_REVIEW,
        )

    if has_primer and has_chemical:
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.72,
            reason="ambiguous_primer_vs_chemical",
            status=STATUS_NEEDS_REVIEW,
        )

    if has_primer:
        return _safe("grunty-i-laki", 0.97, "primer_or_varnish_signal")

    if has_paint:
        return _safe("avtoemali-i-kraski", 0.96, "paint_signal")

    if has_adblue:
        if brand_norm in BRAND_ADBLUE or "euroblue" in normalized_text:
            return _safe("adblue-i-tekhnicheskie-zhidkosti", 0.97, "adblue_or_technical_fluid_signal")
        return ManualChemicalDecision(
            proposed_slug="",
            proposed_category="",
            confidence=0.0,
            reason="adblue_brand_not_whitelisted",
            status=STATUS_SKIP,
        )

    if has_chemical or brand_norm in BRAND_CHEM_CLEANER:
        return _safe("ochistiteli-i-avtokhimiia", 0.95, "chemical_signal")

    return ManualChemicalDecision(
        proposed_slug="",
        proposed_category="",
        confidence=0.0,
        reason="no_chemical_signal",
        status=STATUS_SKIP,
    )


def _safe(slug: str, confidence: float, reason: str) -> ManualChemicalDecision:
    spec = spec_by_slug()[slug]
    return ManualChemicalDecision(
        proposed_slug=slug,
        proposed_category=spec.name,
        confidence=confidence,
        reason=reason,
        status=STATUS_SAFE,
    )


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)
