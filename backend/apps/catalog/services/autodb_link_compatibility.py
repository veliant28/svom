from __future__ import annotations

import re


def _norm(value: str) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^0-9a-zа-яіїєґ]+", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


_EXPLICIT_EQUIVALENCE_RULES: tuple[tuple[str, str, str], ...] = (
    ("повітряні фільтри", "воздушный фильтр", "air_filter_uk_to_ru"),
    ("фільтри оливи", "масляный фильтр", "oil_filter_uk_to_ru"),
    ("паливні фільтри", "топливный фильтр", "fuel_filter_uk_to_ru"),
    ("фільтри салону", "фильтр салона", "cabin_filter_uk_to_ru"),
    ("гальмівні колодки", "тормозные колодки", "brake_pads_uk_to_ru"),
    ("гальмівні диски барабани", "тормозные диски", "brake_discs_uk_to_ru"),
    ("труби приймальні", "приемная труба", "exhaust_downpipe_uk_to_ru"),
    ("труби випускні проміжні коліна", "трубы выхлопной системы", "exhaust_pipes_uk_to_ru"),
    ("свічки запалювання", "свечи зажигания", "spark_plugs_uk_to_ru"),
    ("ремені", "ремень приводной", "drive_belt_uk_to_ru"),
    ("сайлентблоки", "сайлентблоки", "silent_block_same"),
    ("втулки та компоненти", "втулки стабилизатора", "stabilizer_bushing_uk_to_ru"),
    ("ролики", "ролик ремня приводного", "drive_belt_roller_uk_to_ru"),
    ("присадки", "присадки", "additives_same"),
    ("сальники", "сальники", "seals_same"),
    ("термостати", "термостат", "thermostat_uk_to_ru"),
    ("охолоджуючі рідини", "антифриз", "coolant_to_antifreeze"),
    ("трансмісійні оливи", "масло трансмиссионное", "transmission_oil_uk_to_ru"),
    ("троси гальмівної системи", "трос ручника", "brake_cable_to_handbrake_cable"),
    ("ремкомплекти гальмівної системи", "ремкомплект суппорта", "brake_repair_kit_to_caliper_repair_kit"),
    ("дроти запалювання", "провода высоковольтные", "ignition_wires_uk_to_ru"),
    ("моторні оливи", "моторное масло", "engine_oil_uk_to_ru"),
    ("акумулятори", "аккумуляторы", "battery_uk_to_ru"),
    ("подушки та опори двигуна", "подушки двигателя", "engine_mounts_uk_to_ru"),
    ("стабілізатори", "стойки стабилизатора", "stabilizer_links_uk_to_ru"),
    ("шркш", "шрус", "cv_joint_uk_to_ru"),
    ("котушки", "катушка зажигания", "ignition_coil_uk_to_ru"),
    ("насоси паливні", "топливный насос", "fuel_pump_uk_to_ru"),
)


def evaluate_category_compatibility(
    *,
    raw_category: str,
    raw_group: str,
    mapped_site_category: str,
    candidate_group: str,
    candidate_title: str,
) -> tuple[float, str]:
    raw_category_norm = _norm(raw_category)
    mapped_norm = _norm(mapped_site_category)
    raw_text = _norm(" ".join([raw_category, raw_group]))
    ref_text = _norm(" ".join([mapped_site_category, candidate_group, candidate_title]))

    if not raw_text or not ref_text:
        return 0.4, "empty_signal_fallback"

    for raw_expected, mapped_expected, rule_name in _EXPLICIT_EQUIVALENCE_RULES:
        if raw_category_norm == _norm(raw_expected) and mapped_norm == _norm(mapped_expected):
            return 1.0, f"explicit_equivalence:{rule_name}"

    # Conservative concept-level overlap fallback.
    # This keeps generic buckets (e.g. sensor/gasket) in needs_review unless explicit mapping exists.
    raw_is_filter = _contains_any(raw_text, ("фільтр", "фильтр", "filter"))
    ref_is_filter = _contains_any(ref_text, ("фільтр", "фильтр", "filter"))
    raw_is_brake = _contains_any(raw_text, ("гальм", "тормоз", "brake"))
    ref_is_brake = _contains_any(ref_text, ("гальм", "тормоз", "brake"))
    raw_is_shock = _contains_any(raw_text, ("амортиз", "shock"))
    ref_is_shock = _contains_any(ref_text, ("амортиз", "shock"))
    raw_is_exhaust = _contains_any(raw_text, ("глуш", "резонатор", "выхлоп", "вихлоп", "exhaust"))
    ref_is_exhaust = _contains_any(ref_text, ("глуш", "резонатор", "выхлоп", "вихлоп", "exhaust"))

    if raw_is_filter and ref_is_filter:
        return 0.7, "concept_overlap:filter"
    if raw_is_brake and ref_is_brake:
        return 0.7, "concept_overlap:brake"
    if raw_is_shock and ref_is_shock:
        return 0.7, "concept_overlap:shock"
    if raw_is_exhaust and ref_is_exhaust:
        return 0.7, "concept_overlap:exhaust"

    return 0.2, "category_compatibility_low"
