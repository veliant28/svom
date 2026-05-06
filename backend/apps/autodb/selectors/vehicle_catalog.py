from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Iterable

from django.core.cache import cache
from django.db import connections

from apps.autodb.services.construction_interval import parse_construction_interval_years

logger = logging.getLogger(__name__)

DB_ALIAS = "auto_db_pro"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_PREFIX = "autodb:vehicle_catalog"
_SEARCH_LIMIT = 50


@lru_cache(maxsize=64)
def _table_columns(table: str) -> tuple[str, ...]:
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
    return tuple(str(row[0]) for row in rows)


def _reset_schema_cache() -> None:
    _table_columns.cache_clear()
    _passanger_car_engines_link_column.cache_clear()


def clear_vehicle_catalog_selector_cache() -> None:
    cache.set(f"{_CACHE_PREFIX}:version", _cache_version() + 1, None)


def _cache_version() -> int:
    value = cache.get(f"{_CACHE_PREFIX}:version")
    if value is None:
        return 1
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 1


def _cache_key(*parts: Any) -> str:
    scope = ":".join(str(part) for part in parts)
    return f"{_CACHE_PREFIX}:v{_cache_version()}:{scope}"


def _fetch_rows(sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    with connections[DB_ALIAS].cursor() as cursor:
        cursor.execute(sql, list(params or []))
        columns = [str(col[0]) for col in (cursor.description or [])]
        raw_rows = cursor.fetchall()
    return [dict(zip(columns, row, strict=False)) for row in raw_rows]


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_name(*candidates: Any) -> str:
    for item in candidates:
        value = _coerce_str(item)
        if value:
            return value
    return ""


def _order_expr(columns: set[str], preferred: tuple[str, ...]) -> str:
    parts: list[str] = []
    for column in preferred:
        if column in columns:
            parts.append(f'NULLIF(TRIM(CAST("{column}" AS text)), \'\')')
    if not parts:
        return '"id"'
    return f"COALESCE({', '.join(parts)})"


def _manufacturer_where_clause(columns: set[str]) -> str:
    if "ispassengercar" not in columns:
        return ""
    return """
    WHERE LOWER(CAST("ispassengercar" AS text)) IN ('1', 'true', 't', 'yes', 'y')
    """


def list_vehicle_manufacturers() -> list[dict[str, Any]]:
    cache_key = _cache_key("manufacturers")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    table = "manufacturers"
    columns = set(_table_columns(table))
    if "id" not in columns:
        return []

    select_columns = ["id"]
    if "description" in columns:
        select_columns.append("description")
    if "fulldescription" in columns:
        select_columns.append("fulldescription")
    if "ispassengercar" in columns:
        select_columns.append("ispassengercar")

    order_by = _order_expr(columns, ("fulldescription", "description"))
    sql = (
        f'SELECT {", ".join(f"\"{col}\"" for col in select_columns)} '
        f'FROM "{table}" '
        f"{_manufacturer_where_clause(columns)} "
        f"ORDER BY {order_by} ASC"
    )

    rows = _fetch_rows(sql)
    payload: list[dict[str, Any]] = []
    for row in rows:
        manufacturer_id = _coerce_int(row.get("id"))
        if manufacturer_id is None:
            continue
        description = _safe_name(row.get("description"))
        full_description = _safe_name(row.get("fulldescription"))
        name = _safe_name(full_description, description, manufacturer_id)
        payload.append(
            {
                "id": manufacturer_id,
                "name": name,
                "description": description,
                "full_description": full_description,
            }
        )

    cache.set(cache_key, payload, _CACHE_TTL_SECONDS)
    return payload


def get_vehicle_manufacturer(manufacturer_id: int | str) -> dict[str, Any] | None:
    manufacturer_id_int = _coerce_int(manufacturer_id)
    if manufacturer_id_int is None:
        return None
    for row in list_vehicle_manufacturers():
        if _coerce_int(row.get("id")) == manufacturer_id_int:
            return row
    return None


def list_vehicle_models(manufacturer_id: int | str) -> list[dict[str, Any]]:
    manufacturer_id_int = _coerce_int(manufacturer_id)
    if manufacturer_id_int is None:
        return []

    cache_key = _cache_key("models", manufacturer_id_int)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    table = "models"
    columns = set(_table_columns(table))
    required = {"id", "manufacturerid"}
    if not required.issubset(columns):
        return []

    select_columns = ["id", "manufacturerid"]
    if "description" in columns:
        select_columns.append("description")
    if "fulldescription" in columns:
        select_columns.append("fulldescription")
    if "constructioninterval" in columns:
        select_columns.append("constructioninterval")

    order_by = _order_expr(columns, ("fulldescription", "description"))
    sql = (
        f'SELECT {", ".join(f"\"{col}\"" for col in select_columns)} '
        'FROM "models" '
        'WHERE "manufacturerid" = %s '
        f"ORDER BY {order_by} ASC"
    )
    rows = _fetch_rows(sql, [manufacturer_id_int])

    payload: list[dict[str, Any]] = []
    for row in rows:
        model_id = _coerce_int(row.get("id"))
        raw_manufacturer_id = _coerce_int(row.get("manufacturerid"))
        if model_id is None or raw_manufacturer_id is None:
            continue

        description = _safe_name(row.get("description"))
        full_description = _safe_name(row.get("fulldescription"))
        name = _safe_name(full_description, description, model_id)

        payload.append(
            {
                "id": model_id,
                "manufacturer_id": raw_manufacturer_id,
                "name": name,
                "description": description,
                "full_description": full_description,
                "construction_interval": _safe_name(row.get("constructioninterval")),
            }
        )

    cache.set(cache_key, payload, _CACHE_TTL_SECONDS)
    return payload


def get_vehicle_model(*, manufacturer_id: int | str, model_id: int | str) -> dict[str, Any] | None:
    model_id_int = _coerce_int(model_id)
    if model_id_int is None:
        return None
    for row in list_vehicle_models(manufacturer_id=manufacturer_id):
        if _coerce_int(row.get("id")) == model_id_int:
            return row
    return None


def _build_passanger_car_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    passanger_car_id = _coerce_int(row.get("id"))
    model_id = _coerce_int(row.get("modelid"))
    if passanger_car_id is None or model_id is None:
        return None

    description = _safe_name(row.get("description"))
    full_description = _safe_name(row.get("fulldescription"))
    name = _safe_name(full_description, description, passanger_car_id)
    construction_interval_raw = _safe_name(row.get("constructioninterval"))
    parsed = parse_construction_interval_years(construction_interval_raw)

    return {
        "id": passanger_car_id,
        "model_id": model_id,
        "name": name,
        "description": description,
        "full_description": full_description,
        "construction_interval": construction_interval_raw,
        "year_from": parsed.year_from,
        "year_to": parsed.year_to,
        "raw_construction_interval": parsed.raw_construction_interval,
    }


def list_passanger_cars(model_id: int | str) -> list[dict[str, Any]]:
    model_id_int = _coerce_int(model_id)
    if model_id_int is None:
        return []

    cache_key = _cache_key("passanger_cars", model_id_int)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    table = "passanger_cars"
    columns = set(_table_columns(table))
    required = {"id", "modelid"}
    if not required.issubset(columns):
        return []

    select_columns = ["id", "modelid"]
    for column in ("description", "fulldescription", "constructioninterval"):
        if column in columns:
            select_columns.append(column)

    order_by = _order_expr(columns, ("constructioninterval", "description", "fulldescription"))
    sql = (
        f'SELECT {", ".join(f"\"{col}\"" for col in select_columns)} '
        'FROM "passanger_cars" '
        'WHERE "modelid" = %s '
        f"ORDER BY {order_by} ASC"
    )
    rows = _fetch_rows(sql, [model_id_int])

    payload: list[dict[str, Any]] = []
    for row in rows:
        mapped = _build_passanger_car_payload(row)
        if mapped:
            payload.append(mapped)

    cache.set(cache_key, payload, _CACHE_TTL_SECONDS)
    return payload


def get_passanger_car(passanger_car_id: int | str) -> dict[str, Any] | None:
    passanger_car_id_int = _coerce_int(passanger_car_id)
    if passanger_car_id_int is None:
        return None

    table = "passanger_cars"
    columns = set(_table_columns(table))
    required = {"id", "modelid"}
    if not required.issubset(columns):
        return None

    select_columns = ["id", "modelid"]
    for column in ("description", "fulldescription", "constructioninterval"):
        if column in columns:
            select_columns.append(column)

    sql = (
        f'SELECT {", ".join(f"\"{col}\"" for col in select_columns)} '
        'FROM "passanger_cars" '
        'WHERE "id" = %s '
        "LIMIT 1"
    )
    rows = _fetch_rows(sql, [passanger_car_id_int])
    if not rows:
        return None
    return _build_passanger_car_payload(rows[0])


def list_passanger_car_attributes(passanger_car_id: int | str) -> list[dict[str, Any]]:
    passanger_car_id_int = _coerce_int(passanger_car_id)
    if passanger_car_id_int is None:
        return []

    table = "passanger_car_attributes"
    columns = set(_table_columns(table))
    if "passangercarid" not in columns:
        return []

    preferred_columns = (
        "id",
        "passangercarid",
        "attributetype",
        "displaytitle",
        "displayvalue",
        "unit",
        "measureunit",
        "description",
        "value",
    )
    select_columns = [column for column in preferred_columns if column in columns]
    if not select_columns:
        return []

    order_by = _order_expr(columns, ("displaytitle", "attributetype"))
    sql = (
        f'SELECT {", ".join(f"\"{col}\"" for col in select_columns)} '
        'FROM "passanger_car_attributes" '
        'WHERE "passangercarid" = %s '
        f"ORDER BY {order_by} ASC"
    )
    rows = _fetch_rows(sql, [passanger_car_id_int])

    payload: list[dict[str, Any]] = []
    for row in rows:
        title = _safe_name(row.get("displaytitle"), row.get("attributetype"), row.get("description"))
        value = _safe_name(row.get("displayvalue"), row.get("value"), row.get("description"))
        attr_type = _safe_name(row.get("attributetype"))
        unit = _safe_name(row.get("unit"), row.get("measureunit"))
        payload.append(
            {
                "title": title,
                "value": value,
                "type": attr_type,
                "unit": unit,
                "source": {k: row.get(k) for k in select_columns},
            }
        )
    return payload


@lru_cache(maxsize=1)
def _passanger_car_engines_link_column() -> str | None:
    columns = set(_table_columns("passanger_car_engines"))
    if "engineid" not in columns:
        return None
    if "passangercarid" in columns:
        return "passangercarid"
    if "id" not in columns:
        return None

    rows = _fetch_rows(
        'SELECT COUNT(*)::bigint AS total_rows, '
        'SUM(CASE WHEN pc."id" IS NULL THEN 1 ELSE 0 END)::bigint AS missing_rows '
        'FROM "passanger_car_engines" pce '
        'LEFT JOIN "passanger_cars" pc ON pc."id" = pce."id"'
    )
    if not rows:
        return None

    total_rows = _coerce_int(rows[0].get("total_rows")) or 0
    missing_rows = _coerce_int(rows[0].get("missing_rows")) or 0
    if total_rows > 0 and missing_rows == 0:
        return "id"

    logger.warning(
        "Auto_DB_Pro passanger_car_engines link is unresolved. missing_rows=%s total_rows=%s",
        missing_rows,
        total_rows,
    )
    return None


def list_passanger_car_engines(passanger_car_id: int | str) -> list[dict[str, Any]]:
    passanger_car_id_int = _coerce_int(passanger_car_id)
    if passanger_car_id_int is None:
        return []

    link_column = _passanger_car_engines_link_column()
    if link_column is None:
        logger.warning(
            "Auto_DB_Pro passanger_car_engines relation to passanger_cars is not confirmed; returning empty list."
        )
        return []

    engine_rows = _fetch_rows(
        f'SELECT DISTINCT "engineid" FROM "passanger_car_engines" WHERE "{link_column}" = %s',
        [passanger_car_id_int],
    )
    engine_ids = [engine_id for row in engine_rows if (engine_id := _coerce_int(row.get("engineid"))) is not None]
    if not engine_ids:
        return []

    placeholders = ", ".join(["%s"] * len(engine_ids))
    engine_data = _fetch_rows(
        f'SELECT "id", "description" FROM "engines" WHERE "id" IN ({placeholders}) ORDER BY "description" ASC',
        engine_ids,
    )
    return [
        {
            "id": _coerce_int(row.get("id")),
            "description": _safe_name(row.get("description")),
        }
        for row in engine_data
        if _coerce_int(row.get("id")) is not None
    ]


def search_vehicle_manufacturers(query: str) -> list[dict[str, Any]]:
    normalized = _coerce_str(query)
    if not normalized:
        return []

    columns = set(_table_columns("manufacturers"))
    if "id" not in columns:
        return []

    where_parts: list[str] = []
    params: list[Any] = []
    needle = f"%{normalized}%"
    select_columns = ["id"]

    if "description" in columns:
        select_columns.append("description")
        where_parts.append('CAST("description" AS text) ILIKE %s')
        params.append(needle)
    if "fulldescription" in columns:
        select_columns.append("fulldescription")
        where_parts.append('CAST("fulldescription" AS text) ILIKE %s')
        params.append(needle)
    if not where_parts:
        return []

    passenger_filter = _manufacturer_where_clause(columns)
    select_clause = ", ".join(f'"{column}"' for column in select_columns)
    sql = (
        f"SELECT {select_clause} "
        'FROM "manufacturers" '
        f"{passenger_filter} "
        f"AND ({' OR '.join(where_parts)}) "
        f"ORDER BY {_order_expr(columns, ('fulldescription', 'description'))} ASC "
        f"LIMIT {_SEARCH_LIMIT}"
    ) if passenger_filter else (
        f"SELECT {select_clause} "
        'FROM "manufacturers" '
        f"WHERE ({' OR '.join(where_parts)}) "
        f"ORDER BY {_order_expr(columns, ('fulldescription', 'description'))} ASC "
        f"LIMIT {_SEARCH_LIMIT}"
    )

    rows = _fetch_rows(sql, params)
    payload: list[dict[str, Any]] = []
    for row in rows:
        manufacturer_id = _coerce_int(row.get("id"))
        if manufacturer_id is None:
            continue
        description = _safe_name(row.get("description"))
        full_description = _safe_name(row.get("fulldescription"))
        payload.append(
            {
                "id": manufacturer_id,
                "name": _safe_name(full_description, description, manufacturer_id),
                "description": description,
                "full_description": full_description,
            }
        )
    return payload


def search_vehicle_models(manufacturer_id: int | str, query: str) -> list[dict[str, Any]]:
    manufacturer_id_int = _coerce_int(manufacturer_id)
    normalized = _coerce_str(query)
    if manufacturer_id_int is None or not normalized:
        return []

    columns = set(_table_columns("models"))
    if not {"id", "manufacturerid"}.issubset(columns):
        return []

    where_parts: list[str] = []
    params: list[Any] = [manufacturer_id_int]
    needle = f"%{normalized}%"

    if "description" in columns:
        where_parts.append('CAST("description" AS text) ILIKE %s')
        params.append(needle)
    if "fulldescription" in columns:
        where_parts.append('CAST("fulldescription" AS text) ILIKE %s')
        params.append(needle)
    if not where_parts:
        return []

    select_columns = ["id", "manufacturerid", "description", "fulldescription", "constructioninterval"]
    select_columns = [col for col in select_columns if col in columns]

    sql = (
        f'SELECT {", ".join(f"\"{col}\"" for col in select_columns)} '
        'FROM "models" '
        'WHERE "manufacturerid" = %s '
        f"AND ({' OR '.join(where_parts)}) "
        f"ORDER BY {_order_expr(columns, ('fulldescription', 'description'))} ASC "
        f"LIMIT {_SEARCH_LIMIT}"
    )

    rows = _fetch_rows(sql, params)
    payload: list[dict[str, Any]] = []
    for row in rows:
        model_id = _coerce_int(row.get("id"))
        if model_id is None:
            continue
        description = _safe_name(row.get("description"))
        full_description = _safe_name(row.get("fulldescription"))
        payload.append(
            {
                "id": model_id,
                "manufacturer_id": manufacturer_id_int,
                "name": _safe_name(full_description, description, model_id),
                "description": description,
                "full_description": full_description,
                "construction_interval": _safe_name(row.get("constructioninterval")),
            }
        )
    return payload


def search_passanger_cars(model_id: int | str, query: str) -> list[dict[str, Any]]:
    model_id_int = _coerce_int(model_id)
    normalized = _coerce_str(query)
    if model_id_int is None or not normalized:
        return []

    columns = set(_table_columns("passanger_cars"))
    if not {"id", "modelid"}.issubset(columns):
        return []

    where_parts: list[str] = []
    params: list[Any] = [model_id_int]
    needle = f"%{normalized}%"

    if "description" in columns:
        where_parts.append('CAST("description" AS text) ILIKE %s')
        params.append(needle)
    if "fulldescription" in columns:
        where_parts.append('CAST("fulldescription" AS text) ILIKE %s')
        params.append(needle)
    if "constructioninterval" in columns:
        where_parts.append('CAST("constructioninterval" AS text) ILIKE %s')
        params.append(needle)
    if not where_parts:
        return []

    select_columns = ["id", "modelid", "description", "fulldescription", "constructioninterval"]
    select_columns = [col for col in select_columns if col in columns]

    sql = (
        f'SELECT {", ".join(f"\"{col}\"" for col in select_columns)} '
        'FROM "passanger_cars" '
        'WHERE "modelid" = %s '
        f"AND ({' OR '.join(where_parts)}) "
        f"ORDER BY {_order_expr(columns, ('constructioninterval', 'description', 'fulldescription'))} ASC "
        f"LIMIT {_SEARCH_LIMIT}"
    )
    rows = _fetch_rows(sql, params)

    payload: list[dict[str, Any]] = []
    for row in rows:
        mapped = _build_passanger_car_payload(row)
        if mapped:
            payload.append(mapped)
    return payload
