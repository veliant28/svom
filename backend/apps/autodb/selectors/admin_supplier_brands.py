from __future__ import annotations

from typing import Any, Iterable

from django.db import connections

DB_ALIAS = "auto_db_pro"


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


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def list_admin_supplier_brands(
    *,
    q: str = "",
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 20), 200), 1)
    offset = (page - 1) * page_size

    where_parts: list[str] = []
    params: list[Any] = []

    term = _safe_str(q)
    if term:
        where_parts.append(
            """(
                COALESCE(CAST(s."description" AS text), '') ILIKE %s
                OR COALESCE(CAST(s."matchcode" AS text), '') ILIKE %s
                OR COALESCE(CAST(s."id" AS text), '') ILIKE %s
            )"""
        )
        wildcard = f"%{term}%"
        params.extend([wildcard, wildcard, wildcard])

    if is_active is True:
        where_parts.append('COALESCE(s."nbrofarticles", 0) > 0')
    elif is_active is False:
        where_parts.append('COALESCE(s."nbrofarticles", 0) <= 0')

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    count_rows = _fetch_rows(
        f"""
        SELECT COUNT(*) AS total
        FROM "suppliers" s
        {where_sql}
        """,
        params,
    )
    total = _coerce_int((count_rows[0] if count_rows else {}).get("total")) or 0
    if total <= 0:
        return {"count": 0, "results": []}

    rows = _fetch_rows(
        f"""
        SELECT
            s."id" AS supplier_id,
            s."description" AS supplier_description,
            s."matchcode" AS supplier_matchcode,
            s."nbrofarticles" AS supplier_article_count,
            s."hasnewversionarticles" AS supplier_has_new_version
        FROM "suppliers" s
        {where_sql}
        ORDER BY
            COALESCE(
                NULLIF(TRIM(CAST(s."description" AS text)), ''),
                NULLIF(TRIM(CAST(s."matchcode" AS text)), ''),
                CAST(s."id" AS text)
            ) ASC,
            s."id" ASC
        LIMIT %s OFFSET %s
        """,
        [*params, page_size, offset],
    )

    results: list[dict[str, Any]] = []
    for row in rows:
        supplier_id = _coerce_int(row.get("supplier_id"))
        if supplier_id is None:
            continue
        name = _safe_str(row.get("supplier_description"))
        matchcode = _safe_str(row.get("supplier_matchcode"))
        article_count = _coerce_int(row.get("supplier_article_count")) or 0
        results.append(
            {
                "id": supplier_id,
                "name": name or matchcode or str(supplier_id),
                "matchcode": matchcode,
                "article_count": max(article_count, 0),
                "is_active": article_count > 0,
            }
        )

    return {
        "count": total,
        "results": results,
    }


def get_admin_supplier_brand_name_by_id(supplier_id: int) -> str:
    resolved_id = _coerce_int(supplier_id)
    if resolved_id is None:
        return ""

    rows = _fetch_rows(
        """
        SELECT
            s."description" AS supplier_description,
            s."matchcode" AS supplier_matchcode
        FROM "suppliers" s
        WHERE s."id" = %s
        LIMIT 1
        """,
        [resolved_id],
    )
    if not rows:
        return ""
    row = rows[0]
    return _safe_str(row.get("supplier_description")) or _safe_str(row.get("supplier_matchcode"))
