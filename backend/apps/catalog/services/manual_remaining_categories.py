from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class RemainingManualCategorySpec:
    root_slug: str
    slug: str
    name: str
    name_uk: str
    name_ru: str
    name_en: str
    sort_order: int


REMAINING_MANUAL_CATEGORY_SPECS: tuple[RemainingManualCategorySpec, ...] = (
    RemainingManualCategorySpec(
        root_slug="podveska-i-rulevoe",
        slug="amortizatory",
        name="Амортизаторы",
        name_uk="Амортизатори",
        name_ru="Амортизаторы",
        name_en="Shock absorbers",
        sort_order=510,
    ),
    RemainingManualCategorySpec(
        root_slug="podveska-i-rulevoe",
        slug="rychagi-i-sailentbloki",
        name="Рычаги и сайлентблоки",
        name_uk="Важелі та сайлентблоки",
        name_ru="Рычаги и сайлентблоки",
        name_en="Control arms and bushings",
        sort_order=520,
    ),
    RemainingManualCategorySpec(
        root_slug="elektrika-i-osveshchenie",
        slug="akkumuliatory",
        name="Аккумуляторы",
        name_uk="Акумулятори",
        name_ru="Аккумуляторы",
        name_en="Batteries",
        sort_order=710,
    ),
    RemainingManualCategorySpec(
        root_slug="elektrika-i-osveshchenie",
        slug="izolenta-i-elektromaterialy",
        name="Изолента и электроматериалы",
        name_uk="Ізострічка та електроматеріали",
        name_ru="Изолента и электроматериалы",
        name_en="Electrical tape and materials",
        sort_order=720,
    ),
    RemainingManualCategorySpec(
        root_slug="klimat-komfort-i-bezopasnost",
        slug="aptechki-i-bezopasnost",
        name="Аптечки и безопасность",
        name_uk="Аптечки та безпека",
        name_ru="Аптечки и безопасность",
        name_en="First aid and safety",
        sort_order=1010,
    ),
    RemainingManualCategorySpec(
        root_slug="avtokhimiia-i-aksesuary",
        slug="instrumenty-i-aksessuary",
        name="Инструменты и аксессуары",
        name_uk="Інструменти та аксесуари",
        name_ru="Инструменты и аксессуары",
        name_en="Tools and accessories",
        sort_order=250,
    ),
    RemainingManualCategorySpec(
        root_slug="kuzov-i-salon",
        slug="kovriki-i-bagazhnik",
        name="Коврики и багажник",
        name_uk="Килимки та багажник",
        name_ru="Коврики и багажник",
        name_en="Mats and trunk",
        sort_order=810,
    ),
)


@dataclass(frozen=True)
class RemainingPayloadFields:
    category: str
    group: str
    name: str
    description: str
    article_td: str
    code: str


@dataclass(frozen=True)
class RemainingCategoryDecision:
    proposed_slug: str
    proposed_category: str
    proposed_root_slug: str
    confidence: float
    reason: str
    status: str


STATUS_SAFE = "safe_manual_category_candidate"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_SKIP = "skip_unclear"


BRAND_NEEDS_SHOCK = {"DAINTON", "AT"}
BRAND_NEEDS_BATTERY = {"HAGENBATTERIE"}
BRAND_NEEDS_FIRST_AID = {"AVPHARMA"}
BRAND_NEEDS_TOOL = {"YATO", "ELEGANT", "RUGBY"}

SHOCK_TOKENS = ("амортиз", "стойк", "стійк", "shock absorber")
ARM_BUSHING_TOKENS = ("рычаг", "важіл", "сайлент", "втулк", "шарнир")
BATTERY_TOKENS = ("аккумулятор", "акумулятор", "батаре", "battery")
TAPE_TOKENS = ("изолент", "ізоляційн", "изоляцион", "electrical tape")
FIRST_AID_TOKENS = ("аптечк", "first aid", "аварийн", "аварій", "безопас")
TOOL_TOKENS = (
    "инструмент",
    "інструмент",
    "аксессуар",
    "аксесуар",
    "щетк",
    "щітк",
    "скреб",
    "воронк",
    "tool",
)
MAT_TRUNK_TOKENS = ("коврик", "килимок", "багажник", "ванночка багажника", "сумка багажного")


def spec_by_slug() -> dict[str, RemainingManualCategorySpec]:
    return {item.slug: item for item in REMAINING_MANUAL_CATEGORY_SPECS}


def extract_remaining_payload_fields(raw_payload: dict[str, Any] | None) -> RemainingPayloadFields:
    payload = raw_payload if isinstance(raw_payload, dict) else {}

    def _pick(*keys: str) -> str:
        for key in keys:
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        return ""

    return RemainingPayloadFields(
        category=_pick("Категорія", "Категория", "category"),
        group=_pick("Група ТД", "Группа ТД", "group"),
        name=_pick("Найменування", "Наименование", "name", "title"),
        description=_pick("Опис", "Описание", "description"),
        article_td=_pick("Артикул ТД", "Артикул ТД.", "article_td"),
        code=_pick("Код", "code"),
    )


def decide_remaining_manual_category(
    *,
    product_name: str,
    supplier_product_name: str,
    brand: str,
    payload: RemainingPayloadFields,
) -> RemainingCategoryDecision:
    brand_norm = normalize_brand(brand)
    text = " ".join(
        item
        for item in [
            str(product_name or "").strip(),
            str(supplier_product_name or "").strip(),
            payload.category,
            payload.group,
            payload.name,
            payload.description,
            payload.article_td,
            payload.code,
        ]
        if item
    )
    normalized_text = " ".join(text.lower().split())

    has_shock = _contains_any(normalized_text, SHOCK_TOKENS)
    has_arm = _contains_any(normalized_text, ARM_BUSHING_TOKENS)
    has_battery = _contains_any(normalized_text, BATTERY_TOKENS)
    has_tape = _contains_any(normalized_text, TAPE_TOKENS)
    has_first_aid = _contains_any(normalized_text, FIRST_AID_TOKENS)
    has_tools = _contains_any(normalized_text, TOOL_TOKENS)
    has_mat_trunk = _contains_any(normalized_text, MAT_TRUNK_TOKENS)

    if brand_norm in BRAND_NEEDS_SHOCK and not has_shock:
        return _needs_review("brand_requires_shock_signal", 0.62)
    if brand_norm in BRAND_NEEDS_BATTERY and not has_battery:
        return _needs_review("brand_requires_battery_signal", 0.62)
    if brand_norm in BRAND_NEEDS_FIRST_AID and not has_first_aid:
        return _needs_review("brand_requires_first_aid_signal", 0.62)
    if brand_norm in BRAND_NEEDS_TOOL and not has_tools:
        return _needs_review("brand_requires_tool_signal", 0.62)

    scored: list[tuple[str, float, str]] = []
    if has_shock:
        scored.append(("amortizatory", 0.96, "shock_signal"))
    if has_arm:
        scored.append(("rychagi-i-sailentbloki", 0.95, "control_arm_signal"))
    if has_battery:
        scored.append(("akkumuliatory", 0.96, "battery_signal"))
    if has_tape:
        scored.append(("izolenta-i-elektromaterialy", 0.95, "electrical_tape_signal"))
    if has_first_aid:
        scored.append(("aptechki-i-bezopasnost", 0.95, "first_aid_signal"))
    if has_tools:
        scored.append(("instrumenty-i-aksessuary", 0.94, "tool_accessory_signal"))
    if has_mat_trunk:
        scored.append(("kovriki-i-bagazhnik", 0.94, "mat_trunk_signal"))

    if not scored:
        return RemainingCategoryDecision(
            proposed_slug="",
            proposed_category="",
            proposed_root_slug="",
            confidence=0.0,
            reason="no_whitelist_signal",
            status=STATUS_SKIP,
        )

    scored.sort(key=lambda item: item[1], reverse=True)
    if len(scored) > 1 and abs(scored[0][1] - scored[1][1]) < 0.011:
        return _needs_review("ambiguous_multi_category_signal", 0.7)

    slug, confidence, reason = scored[0]
    return _safe(slug=slug, confidence=confidence, reason=reason)


def _safe(*, slug: str, confidence: float, reason: str) -> RemainingCategoryDecision:
    spec = spec_by_slug()[slug]
    return RemainingCategoryDecision(
        proposed_slug=slug,
        proposed_category=spec.name,
        proposed_root_slug=spec.root_slug,
        confidence=confidence,
        reason=reason,
        status=STATUS_SAFE,
    )


def _needs_review(reason: str, confidence: float) -> RemainingCategoryDecision:
    return RemainingCategoryDecision(
        proposed_slug="",
        proposed_category="",
        proposed_root_slug="",
        confidence=confidence,
        reason=reason,
        status=STATUS_NEEDS_REVIEW,
    )


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)
