from __future__ import annotations

import re
from hashlib import sha1
from functools import lru_cache
from typing import Any, Iterable

from django.core.cache import cache
from django.db import connections

from apps.autodb.services.construction_interval import parse_construction_interval_years

DB_ALIAS = "auto_db_pro"
MANUFACTURERS_CACHE_TTL = 600
MODELS_CACHE_TTL = 600
FILTER_OPTIONS_CACHE_TTL = 0


def _cache_get(key: str) -> Any:
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key: str, value: Any, ttl: int) -> None:
    try:
        cache.set(key, value, ttl)
    except Exception:
        return None


@lru_cache(maxsize=64)
def _table_columns(table: str) -> tuple[str, ...]:
    try:
        with connections[DB_ALIAS].cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                [table],
            )
            rows = cursor.fetchall()
    except Exception:
        return ()
    return tuple(str(row[0]) for row in rows)


def _fetch_rows(sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    try:
        with connections[DB_ALIAS].cursor() as cursor:
            cursor.execute(sql, list(params or []))
            columns = [str(col[0]) for col in (cursor.description or [])]
            raw_rows = cursor.fetchall()
    except Exception:
        return []
    return [dict(zip(columns, row, strict=False)) for row in raw_rows]


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_name(*candidates: Any) -> str:
    for candidate in candidates:
        value = _safe_str(candidate)
        if value:
            return value
    return ""


def _cache_key(prefix: str, *parts: Any) -> str:
    normalized = "|".join(_safe_str(part) for part in parts)
    digest = sha1(normalized.encode("utf-8")).hexdigest()
    return f"autodb:admin_vehicle_catalog:{prefix}:{digest}"


_PERIOD_RE = re.compile(r"^\s*(?:(?:\d{2}\.)?(\d{4}))?\s*-\s*(?:(?:\d{2}\.)?(\d{4}))?\s*$")
_YEAR_PAIR_RE = re.compile(r"^\s*(\d{4})\s*-\s*(\d{4})\s*$")
_ZERO_VALUE_RE = re.compile(r"^0+(?:[.,]0+)?(?:\s*[A-Za-zА-Яа-яІіЇїЄєҐґ%]+)?$")


def format_admin_vehicle_period(raw_interval: str | None) -> str:
    raw = _safe_str(raw_interval)
    if not raw:
        return ""

    pair_match = _YEAR_PAIR_RE.match(raw)
    if pair_match:
        return f"{pair_match.group(1)}–{pair_match.group(2)}"

    match = _PERIOD_RE.match(raw)
    if not match:
        return raw

    year_from = match.group(1)
    year_to = match.group(2)
    if year_from and year_to:
        return f"{year_from}–{year_to}"
    if year_from:
        return f"з {year_from}"
    if year_to:
        return f"до {year_to}"
    return raw


def _normalize_measurement_value(value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    if _ZERO_VALUE_RE.fullmatch(text):
        return ""
    return text


def _normalize_casefold(value: Any) -> str:
    return _safe_str(value).casefold()


def _find_column(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _manufacturer_where_clause(columns: set[str]) -> str:
    if "ispassengercar" not in columns:
        return ""
    return """
    LOWER(CAST(man."ispassengercar" AS text)) IN ('1', 'true', 't', 'yes', 'y')
    """


def list_admin_vehicle_manufacturers(*, q: str = "") -> list[dict[str, Any]]:
    term = _safe_str(q)
    cache_key = _cache_key("manufacturers", term.lower())
    cached = _cache_get(cache_key)
    if cached is not None:
        return list(cached)

    manufacturer_columns = set(_table_columns("manufacturers"))
    if "id" not in manufacturer_columns:
        return []

    manufacturer_name_column = _find_column(manufacturer_columns, ("description", "fulldescription", "matchcode")) or "id"
    manufacturer_full_column = _find_column(manufacturer_columns, ("fulldescription", "description", "matchcode")) or manufacturer_name_column

    where_parts: list[str] = []
    passenger_where = _manufacturer_where_clause(manufacturer_columns)
    if passenger_where:
        where_parts.append(passenger_where)
    params: list[Any] = []
    if term:
        where_parts.append(
            f"""(
                COALESCE(CAST(man."{manufacturer_name_column}" AS text), '') ILIKE %s
                OR COALESCE(CAST(man."{manufacturer_full_column}" AS text), '') ILIKE %s
                OR COALESCE(CAST(man."id" AS text), '') ILIKE %s
            )"""
        )
        params.extend([f"%{term}%"] * 3)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    rows = _fetch_rows(
        f"""
        SELECT
            man."id" AS manufacturer_id,
            man."{manufacturer_name_column}" AS manufacturer_description,
            man."{manufacturer_full_column}" AS manufacturer_fulldescription
        FROM "manufacturers" man
        {where_sql}
        ORDER BY man."{manufacturer_name_column}" ASC, man."id" ASC
        """,
        params,
    )

    payload: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        manufacturer_id = _coerce_int(row.get("manufacturer_id"))
        if manufacturer_id is None or manufacturer_id in seen:
            continue
        seen.add(manufacturer_id)
        payload.append(
            {
                "id": manufacturer_id,
                "name": _safe_name(row.get("manufacturer_fulldescription"), row.get("manufacturer_description"), manufacturer_id),
            }
        )
    _cache_set(cache_key, payload, MANUFACTURERS_CACHE_TTL)
    return payload


def list_admin_vehicle_models(*, manufacturer_id: int, q: str = "") -> list[dict[str, Any]]:
    term = _safe_str(q)
    cache_key = _cache_key("models", manufacturer_id, term.lower())
    cached = _cache_get(cache_key)
    if cached is not None:
        return list(cached)

    model_columns = set(_table_columns("models"))
    if not {"id", "manufacturerid"}.issubset(model_columns):
        return []

    model_name_column = _find_column(model_columns, ("description", "fulldescription")) or "id"
    model_full_column = _find_column(model_columns, ("fulldescription", "description")) or model_name_column
    model_interval_column = _find_column(model_columns, ("constructioninterval",))

    passanger_car_columns = set(_table_columns("passanger_cars"))
    if not {"id", "modelid"}.issubset(passanger_car_columns):
        return []

    where_parts = [
        'm."manufacturerid" = %s',
        'EXISTS (SELECT 1 FROM "passanger_cars" pc WHERE pc."modelid" = m."id")',
    ]
    params: list[Any] = [manufacturer_id]
    if term:
        where_parts.append(
            f"""(
                COALESCE(CAST(m."{model_name_column}" AS text), '') ILIKE %s
                OR COALESCE(CAST(m."{model_full_column}" AS text), '') ILIKE %s
                OR COALESCE(CAST(m."id" AS text), '') ILIKE %s
            )"""
        )
        params.extend([f"%{term}%"] * 3)
    where_sql = f"WHERE {' AND '.join(where_parts)}"

    interval_select = f'm."{model_interval_column}"' if model_interval_column else "''"
    rows = _fetch_rows(
        f"""
        SELECT
            m."id" AS model_id,
            m."manufacturerid" AS manufacturer_id,
            m."{model_name_column}" AS model_description,
            m."{model_full_column}" AS model_fulldescription,
            {interval_select} AS constructioninterval
        FROM "models" m
        {where_sql}
        ORDER BY m."{model_name_column}" ASC, m."id" ASC
        """,
        params,
    )

    payload: list[dict[str, Any]] = []
    for row in rows:
        model_id = _coerce_int(row.get("model_id"))
        raw_manufacturer_id = _coerce_int(row.get("manufacturer_id"))
        if model_id is None or raw_manufacturer_id is None:
            continue
        payload.append(
            {
                "id": model_id,
                "manufacturer_id": raw_manufacturer_id,
                "name": _safe_name(row.get("model_fulldescription"), row.get("model_description"), model_id),
                "construction_interval": _safe_str(row.get("constructioninterval")),
            }
        )
    _cache_set(cache_key, payload, MODELS_CACHE_TTL)
    return payload


def _load_admin_vehicle_scope_rows(
    *,
    manufacturer_id: int | None = None,
    model_id: int | None = None,
) -> list[dict[str, Any]]:
    cache_key = _cache_key("scope_rows", manufacturer_id or "-", model_id or "-")
    cached = _cache_get(cache_key)
    if cached is not None:
        return list(cached)

    model_columns = set(_table_columns("models"))
    manufacturer_columns = set(_table_columns("manufacturers"))
    passanger_car_columns = set(_table_columns("passanger_cars"))
    required_model = {"id", "manufacturerid"}
    required_passanger_car = {"id", "modelid"}
    if not required_model.issubset(model_columns) or not required_passanger_car.issubset(passanger_car_columns):
        return []

    manufacturer_name_column = _find_column(manufacturer_columns, ("description", "fulldescription", "matchcode")) or "id"
    manufacturer_full_column = _find_column(manufacturer_columns, ("fulldescription", "description", "matchcode")) or manufacturer_name_column
    model_name_column = _find_column(model_columns, ("description", "fulldescription")) or "id"
    model_full_column = _find_column(model_columns, ("fulldescription", "description")) or model_name_column
    modification_name_column = _find_column(passanger_car_columns, ("description", "fulldescription")) or "id"
    modification_full_column = _find_column(passanger_car_columns, ("fulldescription", "description")) or modification_name_column
    interval_column = _find_column(passanger_car_columns, ("constructioninterval",)) or ""
    interval_select = f'pc."{interval_column}"' if interval_column else "''"

    where_parts: list[str] = []
    passenger_where = _manufacturer_where_clause(manufacturer_columns)
    if passenger_where:
        where_parts.append(passenger_where)
    params: list[Any] = []
    if manufacturer_id is not None:
        where_parts.append('m."manufacturerid" = %s')
        params.append(manufacturer_id)
    if model_id is not None:
        where_parts.append('pc."modelid" = %s')
        params.append(model_id)
    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    rows = _fetch_rows(
        f"""
        SELECT DISTINCT ON (pc."id")
            pc."id" AS passanger_car_id,
            {interval_select} AS constructioninterval,
            man."id" AS manufacturer_id,
            man."{manufacturer_name_column}" AS manufacturer_description,
            man."{manufacturer_full_column}" AS manufacturer_fulldescription,
            m."id" AS model_id,
            m."{model_name_column}" AS model_description,
            m."{model_full_column}" AS model_fulldescription,
            pc."{modification_name_column}" AS modification_description,
            pc."{modification_full_column}" AS modification_fulldescription
        FROM "passanger_cars" pc
        JOIN "models" m ON m."id" = pc."modelid"
        JOIN "manufacturers" man ON man."id" = m."manufacturerid"
        {where_sql}
        ORDER BY pc."id" ASC, man."{manufacturer_name_column}" ASC, m."{model_name_column}" ASC
        """,
        params,
    )
    _cache_set(cache_key, rows, FILTER_OPTIONS_CACHE_TTL)
    return rows


def _row_make_name(row: dict[str, Any]) -> str:
    return _safe_name(row.get("manufacturer_fulldescription"), row.get("manufacturer_description"))


def _row_model_name(row: dict[str, Any]) -> str:
    return _safe_name(row.get("model_description"), row.get("model_fulldescription"))


def _row_modification_name(row: dict[str, Any]) -> str:
    return _safe_name(row.get("modification_description"), row.get("modification_fulldescription"))


def _row_matches_year(row: dict[str, Any], year: int | None) -> bool:
    if year is None:
        return True
    raw_interval = _safe_name(row.get("constructioninterval"), row.get("period_raw"))
    interval = parse_construction_interval_years(raw_interval)
    if interval.year_from is not None and year < interval.year_from:
        return False
    if interval.year_to is not None and year > interval.year_to:
        return False
    return interval.year_from is not None or interval.year_to is not None


def _row_matches_modification(row: dict[str, Any], modification: str) -> bool:
    if not modification:
        return True
    return _normalize_casefold(_row_modification_name(row)) == _normalize_casefold(modification)


def _apply_post_filters(
    rows: list[dict[str, Any]],
    *,
    year: int | None = None,
    q: str = "",
    modification: str = "",
    volume: str = "",
    engine: str = "",
) -> list[dict[str, Any]]:
    query = _normalize_casefold(q)
    modification_key = _normalize_casefold(modification)
    volume_key = _normalize_casefold(volume)
    engine_key = _normalize_casefold(engine)

    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not _row_matches_year(row, year):
            continue
        if modification_key and _normalize_casefold(row.get("modification")) != modification_key:
            continue
        if volume_key and _normalize_casefold(row.get("volume")) != volume_key:
            continue
        if engine_key and _normalize_casefold(row.get("engine")) != engine_key:
            continue
        if query:
            haystack = " ".join(
                [
                    _safe_str(row.get("make")),
                    _safe_str(row.get("model")),
                    _safe_str(row.get("modification")),
                    _safe_str(row.get("period")),
                    _safe_str(row.get("engine")),
                    _safe_str(row.get("volume")),
                    _safe_str(row.get("passanger_car_id")),
                ]
            ).casefold()
            if query not in haystack:
                continue
        filtered.append(row)
    return filtered


def _build_admin_vehicle_results(scope_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    passanger_car_ids = [_coerce_int(row.get("passanger_car_id")) for row in scope_rows]
    passanger_car_ids = [value for value in passanger_car_ids if value is not None]
    engine_payload = _load_engine_payload_by_car_ids(passanger_car_ids)
    attrs_payload = _load_attributes_by_car_ids(passanger_car_ids)

    results: list[dict[str, Any]] = []
    seen_passanger_car_ids: set[int] = set()
    for row in scope_rows:
        passanger_car_id = _coerce_int(row.get("passanger_car_id"))
        if passanger_car_id is None or passanger_car_id in seen_passanger_car_ids:
            continue
        seen_passanger_car_ids.add(passanger_car_id)
        attrs = attrs_payload.get(passanger_car_id, {})
        engine_rows = engine_payload.get(passanger_car_id) or [{}]
        for engine_row in engine_rows:
            results.append(
                {
                    "passanger_car_id": passanger_car_id,
                    "manufacturer_id": _coerce_int(row.get("manufacturer_id")),
                    "model_id": _coerce_int(row.get("model_id")),
                    "make": _row_make_name(row),
                    "model": _row_model_name(row),
                    "modification": _row_modification_name(row),
                    "period": format_admin_vehicle_period(row.get("constructioninterval")),
                    "period_raw": _safe_str(row.get("constructioninterval")),
                    "volume": _normalize_measurement_value(_safe_name(attrs.get("volume"), engine_row.get("volume"))),
                    "engine": _safe_name(engine_row.get("engine")),
                    "hp": _normalize_measurement_value(_safe_name(attrs.get("hp"), engine_row.get("hp"))),
                    "kw": _normalize_measurement_value(_safe_name(attrs.get("kw"), engine_row.get("kw"))),
                }
            )
    return results


def _collect_year_options(rows: list[dict[str, Any]]) -> list[int]:
    years: set[int] = set()
    for row in rows:
        interval = parse_construction_interval_years(_safe_str(row.get("constructioninterval")))
        year_from = interval.year_from
        year_to = interval.year_to or interval.year_from
        if year_from is None or year_to is None:
            continue
        start = min(year_from, year_to)
        end = max(year_from, year_to)
        if end - start > 80:
            years.add(start)
            years.add(end)
            continue
        for value in range(start, end + 1):
            years.add(value)
    return sorted(years, reverse=True)


def _list_unique_named_options(rows: list[dict[str, Any]], *, id_key: str, name_builder) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        option_id = _coerce_int(row.get(id_key))
        option_name = _safe_str(name_builder(row))
        if option_id is None or not option_name or option_id in seen:
            continue
        seen.add(option_id)
        out.append({"id": option_id, "name": option_name})
    out.sort(key=lambda item: (item["name"], item["id"]))
    return out


def _list_unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = _safe_str(value)
        if not text:
            continue
        marker = text.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        out.append(text)
    out.sort()
    return out


def list_admin_vehicle_filter_options(
    *,
    year: int | None = None,
    manufacturer_id: int | None = None,
    model_id: int | None = None,
    modification: str = "",
    volume: str = "",
    years_only: bool = False,
) -> dict[str, Any]:
    cache_key = _cache_key(
        "filter_options_v3_all_engines",
        year or "-",
        manufacturer_id or "-",
        model_id or "-",
        _normalize_casefold(modification),
        _normalize_casefold(volume),
        "years_only" if years_only else "-",
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return dict(cached)

    global_rows = _load_admin_vehicle_scope_rows()
    if years_only:
        payload = {
            "years": _collect_year_options(global_rows),
            "manufacturers": [],
            "models": [],
            "modifications": [],
            "volumes": [],
            "engines": [],
        }
        _cache_set(cache_key, payload, FILTER_OPTIONS_CACHE_TTL)
        return payload

    year_scoped_rows = [row for row in global_rows if _row_matches_year(row, year)]
    manufacturer_scoped_rows = [
        row
        for row in year_scoped_rows
        if manufacturer_id is None or _coerce_int(row.get("manufacturer_id")) == manufacturer_id
    ]
    model_scoped_rows = [
        row
        for row in manufacturer_scoped_rows
        if model_id is None or _coerce_int(row.get("model_id")) == model_id
    ]
    modification_scoped_rows = [
        row
        for row in model_scoped_rows
        if _row_matches_modification(row, modification)
    ]

    needs_enriched_rows = bool(manufacturer_id and model_id and modification)
    enriched_modification_rows = _build_admin_vehicle_results(modification_scoped_rows) if needs_enriched_rows and modification_scoped_rows else []
    volume_scoped_rows = [
        row
        for row in enriched_modification_rows
        if not volume or _normalize_casefold(row.get("volume")) == _normalize_casefold(volume)
    ]

    payload = {
        "years": _collect_year_options(global_rows),
        "manufacturers": _list_unique_named_options(year_scoped_rows, id_key="manufacturer_id", name_builder=_row_make_name) if year is not None else [],
        "models": _list_unique_named_options(manufacturer_scoped_rows, id_key="model_id", name_builder=_row_model_name) if year is not None and manufacturer_id else [],
        "modifications": _list_unique_strings(_row_modification_name(row) for row in model_scoped_rows) if year is not None and manufacturer_id and model_id else [],
        "volumes": _list_unique_strings(str(row.get("volume") or "") for row in enriched_modification_rows)
        if year is not None and manufacturer_id and model_id and modification
        else [],
        "engines": _list_unique_strings(str(row.get("engine") or "") for row in volume_scoped_rows)
        if year is not None and manufacturer_id and model_id and modification and volume
        else [],
    }
    _cache_set(cache_key, payload, FILTER_OPTIONS_CACHE_TTL)
    return payload


def _passanger_car_engines_link_column() -> str | None:
    columns = set(_table_columns("passanger_car_engines"))
    if "passangercarid" in columns:
        return "passangercarid"
    if "id" in columns:
        return "id"
    return None


def _load_engine_payload_by_car_ids(passanger_car_ids: list[int]) -> dict[int, list[dict[str, str]]]:
    if not passanger_car_ids:
        return {}

    pce_columns = set(_table_columns("passanger_car_engines"))
    engines_columns = set(_table_columns("engines"))
    link_column = _passanger_car_engines_link_column()
    if not link_column or "engineid" not in pce_columns or "id" not in engines_columns:
        return {}

    pce_rows = _fetch_rows(
        f"""
        SELECT "{link_column}" AS passanger_car_id, "engineid"
        FROM "passanger_car_engines"
        WHERE "{link_column}" = ANY(%s)
        """,
        [passanger_car_ids],
    )
    engine_ids = sorted({_coerce_int(row.get("engineid")) for row in pce_rows if _coerce_int(row.get("engineid")) is not None})
    if not engine_ids:
        return {}

    select_columns = [
        column
        for column in (
            "id",
            "description",
            "fulldescription",
            "capacity",
            "cc",
            "powerkw",
            "kw",
            "powerhp",
            "hp",
            "code",
        )
        if column in engines_columns
    ]
    if "id" not in select_columns:
        select_columns.insert(0, "id")
    engine_rows = _fetch_rows(
        f"""
        SELECT {", ".join(f'"{column}"' for column in select_columns)}
        FROM "engines"
        WHERE "id" = ANY(%s)
        """,
        [engine_ids],
    )
    engine_by_id = {_coerce_int(row.get("id")): row for row in engine_rows if _coerce_int(row.get("id")) is not None}

    payload: dict[int, list[dict[str, str]]] = {}
    seen_by_car: dict[int, set[tuple[str, str, str, str]]] = {}
    for row in pce_rows:
        car_id = _coerce_int(row.get("passanger_car_id"))
        engine_id = _coerce_int(row.get("engineid"))
        if car_id is None or engine_id is None:
            continue
        engine_row = engine_by_id.get(engine_id)
        if not engine_row:
            continue
        entry = {
            "engine": _safe_name(engine_row.get("description"), engine_row.get("fulldescription"), engine_row.get("code")),
            "volume": _normalize_measurement_value(_safe_name(engine_row.get("capacity"), engine_row.get("cc"))),
            "hp": _normalize_measurement_value(engine_row.get("powerhp") if engine_row.get("powerhp") is not None else engine_row.get("hp")),
            "kw": _normalize_measurement_value(engine_row.get("powerkw") if engine_row.get("powerkw") is not None else engine_row.get("kw")),
        }
        marker = (entry["engine"], entry["volume"], entry["hp"], entry["kw"])
        seen = seen_by_car.setdefault(car_id, set())
        if marker in seen:
            continue
        seen.add(marker)
        payload.setdefault(car_id, []).append(entry)
    for car_id, entries in payload.items():
        entries.sort(key=lambda item: (item.get("engine", ""), item.get("volume", ""), item.get("hp", ""), item.get("kw", "")))
    return payload


def _load_attributes_by_car_ids(passanger_car_ids: list[int]) -> dict[int, dict[str, str]]:
    if not passanger_car_ids:
        return {}

    columns = set(_table_columns("passanger_car_attributes"))
    link_column = "passangercarid" if "passangercarid" in columns else ("id" if "id" in columns else None)
    if link_column is None:
        return {}

    select_columns = [column for column in ("displaytitle", "displayvalue", "value", "description", link_column) if column in columns]
    if link_column not in select_columns:
        select_columns.append(link_column)

    rows = _fetch_rows(
        f"""
        SELECT {", ".join(f'"{column}"' for column in select_columns)}
        FROM "passanger_car_attributes"
        WHERE "{link_column}" = ANY(%s)
        """,
        [passanger_car_ids],
    )

    payload: dict[int, dict[str, str]] = {}
    for row in rows:
        car_id = _coerce_int(row.get(link_column))
        if car_id is None:
            continue
        title = _safe_name(row.get("displaytitle"), row.get("description")).lower()
        value = _safe_name(row.get("displayvalue"), row.get("value"), row.get("description"))
        value_lower = value.lower()
        if not value:
            continue
        current = payload.setdefault(car_id, {"volume": "", "hp": "", "kw": ""})
        normalized_value = _normalize_measurement_value(value)
        if not normalized_value:
            continue
        if not current["volume"] and any(token in title for token in ("объем", "об’єм", "объем двигателя", "capacity", "cc", "cм3", "см3")):
            current["volume"] = normalized_value
        hp_in_title = any(token in title for token in ("hp", "л.с", "лс", "ps"))
        hp_in_value = any(token in value_lower for token in (" hp", "ps", "л.с", "лс"))
        if not current["hp"] and (hp_in_title or hp_in_value):
            current["hp"] = normalized_value
        kw_in_title = "kw" in title
        kw_in_value = "kw" in value_lower
        if not current["kw"] and (kw_in_title or kw_in_value):
            current["kw"] = normalized_value

    return payload


def _build_engine_filter_sql(*, engine_term: str, link_column: str | None) -> tuple[str, list[Any]]:
    if not engine_term or not link_column:
        return "", []
    engine_columns = set(_table_columns("engines"))
    search_columns = [column for column in ("description", "fulldescription", "code") if column in engine_columns]
    if not search_columns:
        return "", []
    search_predicate = " OR ".join(
        f'COALESCE(CAST(e."{column}" AS text), \'\') ILIKE %s'
        for column in search_columns
    )
    return (
        f"""
        EXISTS (
            SELECT 1
            FROM "passanger_car_engines" pce
            LEFT JOIN "engines" e ON e."id" = pce."engineid"
            WHERE pce."{link_column}" = pc."id"
              AND ({search_predicate})
        )
        """,
        [f"%{engine_term}%"] * len(search_columns),
    )


def list_admin_vehicle_catalog(
    *,
    manufacturer_id: int | None = None,
    model_id: int | None = None,
    year: int | None = None,
    q: str = "",
    modification: str = "",
    volume: str = "",
    engine: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 25), 500), 1)
    offset = (page - 1) * page_size
    scope_rows = _load_admin_vehicle_scope_rows(manufacturer_id=manufacturer_id, model_id=model_id)
    results = _build_admin_vehicle_results(scope_rows)
    results = _apply_post_filters(
        results,
        year=year,
        q=q,
        modification=modification,
        volume=volume,
        engine=engine,
    )
    total = len(results)
    return {
        "count": total,
        "results": results[offset: offset + page_size],
    }
