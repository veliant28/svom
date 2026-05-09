from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.supplier_imports.models import SupplierRawOffer


EXHAUST_TOKENS = (
    "глушитель",
    "глушник",
    "резонатор",
    "выхлоп",
    "вихлоп",
    "система выпуска",
    "система випуску",
    "труба",
    "exhaust",
    "silencer",
    "muffler",
)

SHOCK_TOKENS = (
    "амортизатор",
    "амортизат",
    "shock absorber",
)

BRAKE_TOKENS = (
    "гальм",
    "тормоз",
    "brake",
    "колодк",
    "disc brake",
)

PAINT_TOKENS = (
    "емал",
    "эмал",
    "фарб",
    "краск",
    "paint",
    "varnish",
    "лак",
    "грунт",
    "шпакл",
    "аэрозол",
    "аерозол",
)

CHEM_TOKENS = (
    "очистител",
    "очищувач",
    "автохим",
    "adblue",
    "def",
    "urea",
    "мочевин",
    "сечовин",
)

BATTERY_TOKENS = (
    "аккумулятор",
    "акумулятор",
    "battery",
)

FILTER_TOKENS = (
    "фильтр",
    "фільтр",
    "filter",
)

SPARK_TOKENS = (
    "свеч",
    "свіч",
    "spark plug",
)

MECHANICAL_TOKENS = SHOCK_TOKENS + BRAKE_TOKENS + FILTER_TOKENS + SPARK_TOKENS + EXHAUST_TOKENS + (
    "подвес",
    "підвіс",
    "clutch",
    "сцеплен",
)


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _split_words(text: str) -> set[str]:
    return set(re.findall(r"[0-9a-zа-яіїєґ]+", text, flags=re.IGNORECASE))


def _contains_word(text: str, word: str) -> bool:
    return _norm(word) in _split_words(_norm(text))


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _payload_pick(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def extract_raw_fields(payload: dict[str, Any] | None) -> dict[str, str]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "raw_name": _payload_pick(source, ("Найменування", "Наименование", "name", "title")),
        "raw_description": _payload_pick(source, ("Опис", "Описание", "description")),
        "raw_category": _payload_pick(source, ("Категорія", "Категория", "category")),
        "raw_group": _payload_pick(source, ("Група ТД", "Группа ТД", "group")),
        "gpl_image_url": _payload_pick(
            source,
            (
                "Зображення товару",
                "Изображение товара",
                "Фото",
                "Фотография",
                "image",
                "image_url",
            ),
        ),
    }


def extract_autodb_titles_from_quality(quality: AutoDbProductLinkQuality | None) -> str:
    if quality is None or not isinstance(quality.evidence, dict):
        return ""
    evidence = quality.evidence
    parts: list[str] = []
    for key in (
        "autodb_article_title",
        "autodb_prd_title",
        "article_title",
        "prd_title",
        "reference_title",
    ):
        value = str(evidence.get(key) or "").strip()
        if value:
            parts.append(value)
    return " | ".join(parts)


def load_latest_quality_map(*, product_ids: list[str]) -> dict[str, AutoDbProductLinkQuality]:
    if not product_ids:
        return {}
    rows = (
        AutoDbProductLinkQuality.objects.filter(product_id__in=product_ids)
        .order_by("product_id", "-checked_at", "-updated_at", "-id")
    )
    out: dict[str, AutoDbProductLinkQuality] = {}
    for row in rows.iterator(chunk_size=300):
        key = str(row.product_id)
        if key not in out:
            out[key] = row
    return out


def load_latest_raw_offer_map(*, supplier_code: str, product_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not product_ids:
        return {}
    rows = (
        SupplierRawOffer.objects.filter(source__code=supplier_code, matched_product_id__in=product_ids)
        .order_by("matched_product_id", "-updated_at", "-id")
        .values(
            "id",
            "matched_product_id",
            "brand_name",
            "article",
            "product_name",
            "raw_payload",
        )
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows.iterator(chunk_size=500):
        key = str(row.get("matched_product_id") or "")
        if key and key not in out:
            out[key] = row
    return out


@dataclass(frozen=True)
class SemanticConflict:
    conflict_type: str
    confidence: float
    reason: str


def detect_semantic_conflicts(
    *,
    raw_brand: str,
    raw_text: str,
    product_text: str,
    category_text: str,
    autodb_title_text: str,
) -> list[SemanticConflict]:
    raw_norm = _norm(raw_text)
    product_norm = _norm(product_text)
    category_norm = _norm(category_text)
    autodb_norm = _norm(autodb_title_text)
    reference_norm = " ".join(x for x in [product_norm, category_norm, autodb_norm] if x).strip()

    raw_has_exhaust = _contains_any(raw_norm, EXHAUST_TOKENS) or "polmo" in _norm(raw_brand)
    raw_has_brake = _contains_any(raw_norm, BRAKE_TOKENS)
    raw_has_paint_chem = _contains_any(raw_norm, PAINT_TOKENS) or _contains_word(raw_norm, "primer") or _contains_any(raw_norm, CHEM_TOKENS)
    raw_has_battery = _contains_any(raw_norm, BATTERY_TOKENS)
    raw_has_filter = _contains_any(raw_norm, FILTER_TOKENS)
    raw_has_spark = _contains_any(raw_norm, SPARK_TOKENS)

    ref_has_shock = _contains_any(reference_norm, SHOCK_TOKENS)
    ref_has_exhaust = _contains_any(reference_norm, EXHAUST_TOKENS)
    ref_has_brake = _contains_any(reference_norm, BRAKE_TOKENS)
    ref_has_paint_chem = _contains_any(reference_norm, PAINT_TOKENS) or _contains_word(reference_norm, "primer") or _contains_any(reference_norm, CHEM_TOKENS)
    ref_has_battery = _contains_any(reference_norm, BATTERY_TOKENS)
    ref_has_filter = _contains_any(reference_norm, FILTER_TOKENS)
    ref_has_spark = _contains_any(reference_norm, SPARK_TOKENS)
    ref_has_mechanical = _contains_any(reference_norm, MECHANICAL_TOKENS)

    conflicts: list[SemanticConflict] = []

    if raw_has_exhaust and ref_has_shock:
        conflicts.append(SemanticConflict("exhaust_vs_shock", 0.98, "raw_exhaust_but_autodb_shock"))

    if raw_has_brake and not ref_has_brake and (ref_has_shock or ref_has_filter or ref_has_battery or ref_has_spark):
        conflicts.append(SemanticConflict("brake_vs_non_brake", 0.92, "raw_brake_but_autodb_other_part"))

    if raw_has_paint_chem and ref_has_mechanical and not ref_has_paint_chem:
        conflicts.append(SemanticConflict("paint_chemical_vs_mechanical", 0.9, "raw_paint_or_chemical_but_autodb_mechanical"))

    if raw_has_battery and not ref_has_battery and ref_has_mechanical:
        conflicts.append(SemanticConflict("battery_vs_non_battery", 0.91, "raw_battery_but_autodb_non_battery"))

    if raw_has_filter and not ref_has_filter and (ref_has_shock or ref_has_brake or ref_has_battery):
        conflicts.append(SemanticConflict("filter_vs_non_filter", 0.9, "raw_filter_but_autodb_other_part"))

    if raw_has_spark and not ref_has_spark and (ref_has_shock or ref_has_filter or ref_has_battery):
        conflicts.append(SemanticConflict("spark_plug_vs_non_spark", 0.9, "raw_spark_plug_but_autodb_other_part"))

    if raw_has_exhaust and ref_has_shock and "polmo" in _norm(raw_brand):
        conflicts.append(SemanticConflict("polmo_exhaust_vs_shock", 0.99, "polmo_brand_with_exhaust_vs_shock_conflict"))

    unique: dict[str, SemanticConflict] = {}
    for item in conflicts:
        prev = unique.get(item.conflict_type)
        if prev is None or item.confidence > prev.confidence:
            unique[item.conflict_type] = item
    return list(unique.values())


def recommend_action(
    *,
    conflicts: list[SemanticConflict],
    product: Product,
    category_source: str,
) -> str:
    if not conflicts:
        return "safe"

    high = max(item.confidence for item in conflicts)
    has_exhaust_shock = any(item.conflict_type in {"exhaust_vs_shock", "polmo_exhaust_vs_shock"} for item in conflicts)

    if has_exhaust_shock and high >= 0.95:
        if (
            str(getattr(product, "name_source", "") or "") == Product.NAME_SOURCE_AUTODB_PRO
            or str(getattr(product, "brand_source", "") or "") == Product.BRAND_SOURCE_AUTODB_PRO
            or category_source == "autodb_pro"
        ):
            return "unlink_autodb_and_reset_name_category"
        return "mark_link_suspicious_only"

    if high >= 0.9:
        return "mark_link_suspicious_only"
    return "needs_manual_review"
