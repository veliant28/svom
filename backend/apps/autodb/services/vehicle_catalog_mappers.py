from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone as dt_timezone
from typing import Any, Callable

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.autodb.services.intervals import parse_construction_interval


class AutoDbMappingError(ValueError):
    pass


MapperFn = Callable[[dict[str, Any]], dict[str, Any]]


def _pick(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


def _to_int(value: Any, *, required: bool = False, field_name: str = "") -> int | None:
    if value in (None, ""):
        if required:
            raise AutoDbMappingError(f"Missing required integer field '{field_name}'.")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        if required:
            raise AutoDbMappingError(f"Invalid integer value for '{field_name}': {value!r}.") from exc
        return None


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_dt(value: Any) -> datetime | None:
    text = _to_text(value)
    if not text:
        return None
    parsed = parse_datetime(text)
    if parsed is not None:
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone=dt_timezone.utc)
        return parsed
    return None


def _normalize_name(value: Any) -> str:
    text = _to_text(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _source_row_id(table: str, row: dict[str, Any], *preferred_keys: str) -> str:
    for key in preferred_keys:
        if key in row and row.get(key) not in (None, ""):
            return f"{table}:{_to_text(row.get(key))}"

    digest = hashlib.sha1(repr(sorted(row.items())).encode("utf-8")).hexdigest()  # noqa: S324
    return f"{table}:sha1:{digest}"


def map_country(row: dict[str, Any]) -> dict[str, Any]:
    country_id = _to_int(_pick(row, "isocodeno", "id", "country_id"), required=True, field_name="countries.id")
    return {
        "autodb_country_id": country_id,
        "name": _to_text(_pick(row, "description", "name", "country_name")),
        "iso_code": _to_text(_pick(row, "isocode2", "iso", "iso_code", "code", "country_code")),
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_country_group(row: dict[str, Any]) -> dict[str, Any]:
    group_id = _to_int(_pick(row, "id", "country_group_id", "group_id"), required=True, field_name="country_groups.id")
    return {
        "autodb_country_group_id": group_id,
        "name": _to_text(_pick(row, "name", "description", "group_name")),
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_language(row: dict[str, Any]) -> dict[str, Any]:
    language_id = _to_int(_pick(row, "id", "language_id"), required=True, field_name="languages.id")
    return {
        "autodb_language_id": language_id,
        "code": _to_text(_pick(row, "isocode2", "code", "lang", "language_code", "iso")),
        "name": _to_text(_pick(row, "description", "name", "language_name")),
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_manufacturer(row: dict[str, Any]) -> dict[str, Any]:
    manufacturer_id = _to_int(_pick(row, "id", "manufacturer_id"), required=True, field_name="manufacturers.id")
    name = _to_text(_pick(row, "name", "description", "manufacturer_name"))
    return {
        "autodb_manufacturer_id": manufacturer_id,
        "name": name,
        "normalized_name": _normalize_name(name),
        "country_id": _to_int(_pick(row, "country_id", "id_country"), required=False),
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_model(row: dict[str, Any]) -> dict[str, Any]:
    model_id = _to_int(_pick(row, "id", "model_id"), required=True, field_name="models.id")
    manufacturer_id = _to_int(
        _pick(row, "manufacturerid", "manufacturer_id", "id_mfa", "mfa_id"),
        required=False,
        field_name="models.manufacturer_id",
    )
    name = _to_text(_pick(row, "name", "description", "model", "model_name"))
    interval = _to_text(_pick(row, "constructioninterval", "construction_interval", "year_range"))
    parsed_from, _, parsed_to, _ = parse_construction_interval(interval)
    year_from = _to_int(_pick(row, "year_from", "start_year"), required=False) or parsed_from
    year_to = _to_int(_pick(row, "year_to", "end_year"), required=False) or parsed_to

    return {
        "id": model_id,
        "autodb_model_id": model_id,
        "vehicle_manufacturer_id": manufacturer_id,
        "manufacturer_id": None,
        "name": name,
        "normalized_name": _normalize_name(name),
        "year_from": year_from,
        "year_to": year_to,
        "description": name,
        "full_description": _to_text(
            _pick(row, "fulldescription", "full_description", "model_full_name", "name_full", "full_name")
        )
        or name,
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_engine(row: dict[str, Any]) -> dict[str, Any]:
    engine_id = _to_int(_pick(row, "id", "engine_id"), required=True, field_name="engines.id")
    description = _to_text(_pick(row, "description", "engine_code", "code", "motor_code"))
    full_description = _to_text(_pick(row, "fulldescription", "salesdescription"))
    interval = _to_text(_pick(row, "constructioninterval", "construction_interval", "year_range"))
    _start_year, _start_month, _end_year, _end_month = parse_construction_interval(interval)
    capacity = ""
    if _start_year:
        capacity = f"{_start_year}" if not _end_year else f"{_start_year}-{_end_year}"

    return {
        "autodb_engine_id": engine_id,
        "engine_code": description,
        "capacity": _to_text(_pick(row, "capacity", "volume", "ccm")) or capacity,
        "power_kw": _to_int(_pick(row, "power_kw", "kw"), required=False),
        "power_hp": _to_int(_pick(row, "power_hp", "hp", "power_ps"), required=False),
        "fuel_type": _to_text(_pick(row, "fuel_type", "fuel", "fuel_name")) or full_description,
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_passanger_car(row: dict[str, Any]) -> dict[str, Any]:
    vehicle_id = _to_int(
        _pick(row, "id", "passanger_car_id", "passenger_car_id", "vehicle_id", "ktype"),
        required=True,
        field_name="passanger_cars.id",
    )
    manufacturer_id = _to_int(_pick(row, "manufacturerid", "manufacturer_id", "id_mfa", "mfa_id"), required=False)
    model_id = _to_int(_pick(row, "modelid", "model_id", "id_mod", "mod_id"), required=False)

    interval = _to_text(_pick(row, "constructioninterval", "construction_interval", "year_range"))
    start_year, start_month, end_year, end_month = parse_construction_interval(interval)

    year_from = _to_int(_pick(row, "year_from", "start_year"), required=False) or start_year
    year_to = _to_int(_pick(row, "year_to", "end_year"), required=False) or end_year
    description = _to_text(_pick(row, "description", "name", "modification_name"))
    full_description = _to_text(_pick(row, "fulldescription", "full_description", "full_name")) or description

    return {
        "id": vehicle_id,
        "autodb_vehicle_id": vehicle_id,
        "ktype": _to_int(_pick(row, "ktype", "k_type"), required=False) or vehicle_id,
        "vehicle_manufacturer_id": manufacturer_id,
        "model_id": model_id,
        "modification_name": _to_text(_pick(row, "modification_name", "modification", "name")) or description,
        "engine_code": _to_text(_pick(row, "engine_code", "motor_code")),
        "engine_capacity": _to_text(_pick(row, "engine_capacity", "capacity", "ccm")),
        "power_kw": _to_int(_pick(row, "power_kw", "kw"), required=False),
        "power_hp": _to_int(_pick(row, "power_hp", "hp", "power_ps"), required=False),
        "fuel_type": _to_text(_pick(row, "fuel_type", "fuel", "fuel_name")),
        "body_type": _to_text(_pick(row, "body_type", "body", "body_name")),
        "description": description,
        "full_description": full_description,
        "construction_interval": interval,
        "start_year": _to_int(_pick(row, "start_year"), required=False) or start_year,
        "start_month": _to_int(_pick(row, "start_month"), required=False) or start_month,
        "end_year": _to_int(_pick(row, "end_year"), required=False) or end_year,
        "end_month": _to_int(_pick(row, "end_month"), required=False) or end_month,
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_passanger_car_engine(row: dict[str, Any]) -> dict[str, Any]:
    passenger_car_id = _to_int(
        _pick(row, "passangercarid", "passanger_car_id", "passenger_car_id", "vehicle_id", "id_car", "id"),
        required=True,
        field_name="passanger_car_engines.passanger_car_id",
    )
    source_row_id = _source_row_id("passanger_car_engines", row, "id", "row_id")

    return {
        "source_row_id": source_row_id,
        "passenger_car_id": passenger_car_id,
        "engine_id": _to_int(_pick(row, "engineid", "engine_id", "id_eng"), required=False),
        "engine_code": _to_text(_pick(row, "engine_code", "code", "motor_code")),
        "capacity": _to_text(_pick(row, "capacity", "volume", "ccm")),
        "power_kw": _to_int(_pick(row, "power_kw", "kw"), required=False),
        "power_hp": _to_int(_pick(row, "power_hp", "hp", "power_ps"), required=False),
        "fuel_type": _to_text(_pick(row, "fuel_type", "fuel", "fuel_name")),
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_passanger_car_attribute(row: dict[str, Any]) -> dict[str, Any]:
    vehicle_id = _to_int(
        _pick(row, "passangercarid", "passanger_car_id", "passenger_car_id", "vehicle_id", "id_car", "ktype"),
        required=True,
        field_name="passanger_car_attributes.passanger_car_id",
    )
    source_row_id = _source_row_id("passanger_car_attributes", row, "id", "row_id")

    return {
        "source_row_id": source_row_id,
        "vehicle_id": vehicle_id,
        "source_key": _to_text(_pick(row, "attributetype", "criterion_id", "attribute_id", "key", "criterion")),
        "name_uk": _to_text(_pick(row, "displaytitle", "name_uk", "name_ua", "name")),
        "name_ru": _to_text(_pick(row, "name_ru")),
        "name_en": _to_text(_pick(row, "name_en")),
        "value_uk": _to_text(_pick(row, "displayvalue", "value_uk", "value_ua", "value")),
        "value_ru": _to_text(_pick(row, "value_ru")),
        "value_en": _to_text(_pick(row, "value_en")),
        "unit": _to_text(_pick(row, "attributegroup", "unit", "measure", "unit_name")),
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_prd(row: dict[str, Any]) -> dict[str, Any]:
    prd_id = _to_int(_pick(row, "id", "prd_id", "category_id"), required=True, field_name="prd.id")
    name = _to_text(_pick(row, "description", "name", "name_uk", "name_ru", "name_en"))

    return {
        "id": prd_id,
        "autodb_prd_id": prd_id,
        "parent_id": _to_int(_pick(row, "parent_id", "parent"), required=False),
        "group_id": _to_int(_pick(row, "group_id", "group"), required=False),
        "category_id": _to_int(_pick(row, "category_id", "cat_id"), required=False),
        "name": name,
        "name_uk": _to_text(_pick(row, "assemblygroupdescription", "name_uk", "name_ua")) or name,
        "name_ru": _to_text(_pick(row, "description", "name_ru")) or name,
        "name_en": _to_text(_pick(row, "normalizeddescription", "name_en")) or name,
        "normalized_name": _normalize_name(name),
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


def map_passanger_car_tree(row: dict[str, Any]) -> dict[str, Any]:
    vehicle_id = _to_int(
        _pick(row, "passangercarid", "passanger_car_id", "passenger_car_id", "vehicle_id", "id_car", "ktype"),
        required=True,
        field_name="passanger_car_trees.passanger_car_id",
    )
    source_row_id = _source_row_id("passanger_car_trees", row, "id", "row_id")

    name = _to_text(_pick(row, "description", "name", "name_uk", "name_ru", "name_en"))

    return {
        "source_row_id": source_row_id,
        "vehicle_id": vehicle_id,
        "prd_id": _to_int(_pick(row, "searchtreeid", "prd_id", "id_prd", "category_id"), required=False),
        "category_id": _to_int(_pick(row, "category_id", "cat_id"), required=False),
        "parent_id": _to_int(_pick(row, "parentid", "parent_id", "parent"), required=False),
        "name_uk": _to_text(_pick(row, "name_uk", "name_ua")) or name,
        "name_ru": _to_text(_pick(row, "name_ru")) or name,
        "name_en": _to_text(_pick(row, "name_en")) or name,
        "source_payload": dict(row),
        "source_updated_at": _to_dt(_pick(row, "updated_at", "date_upd", "modified_at")),
    }


TABLE_MAPPERS: dict[str, MapperFn] = {
    "countries": map_country,
    "country_groups": map_country_group,
    "languages": map_language,
    "manufacturers": map_manufacturer,
    "models": map_model,
    "engines": map_engine,
    "passanger_cars": map_passanger_car,
    "passanger_car_engines": map_passanger_car_engine,
    "passanger_car_attributes": map_passanger_car_attribute,
    "prd": map_prd,
    "passanger_car_trees": map_passanger_car_tree,
}
