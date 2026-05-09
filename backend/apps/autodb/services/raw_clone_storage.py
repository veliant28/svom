from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from apps.autodb.services.clone_schema import AutoDbCloneSchemaService, CloneSchemaInfo, RemoteColumn
from apps.autodb.services.remote_client import AutoDbProRemoteClient, AutoDbProRemoteClientError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AutoDbRawCloneStorage:
    def __init__(
        self,
        *,
        remote_client: AutoDbProRemoteClient | None = None,
        schema_service: AutoDbCloneSchemaService | None = None,
        db_alias: str = "auto_db_pro",
    ):
        self.remote_client = remote_client or AutoDbProRemoteClient.from_settings()
        self.schema_service = schema_service or AutoDbCloneSchemaService(remote_client=self.remote_client, db_alias=db_alias)
        self.db_alias = db_alias
        self._schema_cache: dict[str, CloneSchemaInfo] = {}
        self._remote_columns_cache: dict[str, list[str]] = {}
        self._local_columns_cache: dict[str, set[str]] = {}

    def ensure_table(self, table: str) -> CloneSchemaInfo:
        cached = self._schema_cache.get(table)
        if cached is not None:
            return cached
        local_columns = sorted(self.get_local_columns(table))
        if local_columns:
            primary_key_columns, unique_keys = self._get_local_keys(table)
            info = CloneSchemaInfo(
                table=table,
                columns=[
                    RemoteColumn(
                        name=column,
                        data_type="text",
                        column_type="text",
                        is_nullable=True,
                        character_maximum_length=None,
                        numeric_precision=None,
                        numeric_scale=None,
                        datetime_precision=None,
                        ordinal_position=index + 1,
                    )
                    for index, column in enumerate(local_columns)
                ],
                primary_key_columns=primary_key_columns,
                unique_keys=unique_keys,
            )
            self._schema_cache[table] = info
            self._local_columns_cache[table] = set(local_columns)
            return info
        info = self.schema_service.ensure_table(table)
        self._schema_cache[table] = info
        self._remote_columns_cache[table] = [item.name for item in info.columns]
        self._local_columns_cache.pop(table, None)
        return info

    def get_remote_columns(self, table: str) -> list[str]:
        cached = self._remote_columns_cache.get(table)
        if cached is not None:
            return list(cached)
        info = self.schema_service.introspect_table(table)
        columns = [item.name for item in info.columns]
        self._remote_columns_cache[table] = columns
        return list(columns)

    def get_local_columns(self, table: str, *, force_refresh: bool = False) -> set[str]:
        if not force_refresh:
            cached = self._local_columns_cache.get(table)
            if cached is not None:
                return set(cached)
        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                """,
                [table],
            )
            columns = {str(item[0]) for item in cursor.fetchall()}
            self._local_columns_cache[table] = set(columns)
            return columns

    def fetch_local_rows(
        self,
        *,
        table: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        order_by: str | None = None,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_identifier(table)
        table_columns = self.get_local_columns(table)
        if not table_columns:
            return []
        by_lower = {name.lower(): name for name in table_columns}

        select_columns = []
        for column in (columns or sorted(table_columns)):
            found = by_lower.get(str(column).lower())
            if found:
                select_columns.append(found)
        if not select_columns:
            return []

        params: list[Any] = []
        where_sql = ""
        if filters:
            parts: list[str] = []
            for key, value in filters.items():
                resolved = by_lower.get(str(key).lower())
                if not resolved:
                    continue
                parts.append(f"{self._q(resolved)} = %s")
                params.append(value)
            if parts:
                where_sql = " WHERE " + " AND ".join(parts)

        order_sql = ""
        if order_by:
            resolved = by_lower.get(str(order_by).lower())
            if resolved:
                order_sql = f" ORDER BY {self._q(resolved)} ASC"

        sql = (
            f"SELECT {', '.join(self._q(col) for col in select_columns)} "
            f"FROM {self._q(table)}"
            f"{where_sql}{order_sql} LIMIT %s"
        )
        params.append(max(int(limit), 1))

        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(sql, params)
            description = [str(item[0]) for item in (cursor.description or [])]
            return [dict(zip(description, row, strict=False)) for row in cursor.fetchall()]

    def fetch_local_rows_in(
        self,
        *,
        table: str,
        column: str,
        values: list[Any],
        extra_filters: dict[str, Any] | None = None,
        limit: int = 1000,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_identifier(table)
        raw_values = [item for item in values if item is not None and str(item).strip() != ""]
        if not raw_values:
            return []

        table_columns = self.get_local_columns(table)
        if not table_columns:
            return []
        by_lower = {name.lower(): name for name in table_columns}
        resolved_column = by_lower.get(str(column).lower())
        if not resolved_column:
            return []

        select_columns = []
        for item in (columns or sorted(table_columns)):
            found = by_lower.get(str(item).lower())
            if found:
                select_columns.append(found)
        if not select_columns:
            return []

        placeholders = ", ".join(["%s"] * len(raw_values))
        where_parts = [f"{self._q(resolved_column)} IN ({placeholders})"]
        params: list[Any] = list(raw_values)
        for key, value in (extra_filters or {}).items():
            resolved = by_lower.get(str(key).lower())
            if not resolved:
                continue
            where_parts.append(f"{self._q(resolved)} = %s")
            params.append(value)

        sql = (
            f"SELECT {', '.join(self._q(col) for col in select_columns)} "
            f"FROM {self._q(table)} "
            f"WHERE {' AND '.join(where_parts)} "
            f"LIMIT %s"
        )
        params.append(max(int(limit), 1))
        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(sql, params)
            description = [str(item[0]) for item in (cursor.description or [])]
            return [dict(zip(description, row, strict=False)) for row in cursor.fetchall()]

    def fetch_remote_rows_exact(
        self,
        *,
        table: str,
        filters: dict[str, Any],
        limit: int = 100,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_identifier(table)
        remote_columns = self.get_remote_columns(table)
        remote_column_set = set(remote_columns)

        where_parts: list[str] = []
        params: list[Any] = []
        for key, value in (filters or {}).items():
            if key not in remote_column_set:
                continue
            where_parts.append(f"{self._quote_mysql_identifier(key)} = %s")
            params.append(value)

        if not where_parts:
            return []

        selected = [column for column in (columns or remote_columns) if column in remote_column_set]
        if not selected:
            selected = remote_columns

        sql = (
            f"SELECT {', '.join(self._quote_mysql_identifier(col) for col in selected)} "
            f"FROM {self._quote_mysql_identifier(table)} "
            f"WHERE {' AND '.join(where_parts)} LIMIT {max(int(limit), 1)}"
        )
        return self.remote_client.select(sql, tuple(params))

    def fetch_remote_rows_in(
        self,
        *,
        table: str,
        column: str,
        values: list[Any],
        extra_filters: dict[str, Any] | None = None,
        limit: int = 1000,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_identifier(table)
        raw_values = [item for item in values if item is not None and str(item).strip() != ""]
        if not raw_values:
            return []

        remote_columns = self.get_remote_columns(table)
        by_lower = {name.lower(): name for name in remote_columns}
        resolved_column = by_lower.get(str(column).lower())
        if not resolved_column:
            return []

        selected = []
        for item in (columns or remote_columns):
            found = by_lower.get(str(item).lower())
            if found:
                selected.append(found)
        if not selected:
            selected = remote_columns

        placeholders = ", ".join(["%s"] * len(raw_values))
        where_parts = [f"{self._quote_mysql_identifier(resolved_column)} IN ({placeholders})"]
        params: list[Any] = list(raw_values)
        for key, value in (extra_filters or {}).items():
            resolved = by_lower.get(str(key).lower())
            if not resolved:
                continue
            where_parts.append(f"{self._quote_mysql_identifier(resolved)} = %s")
            params.append(value)

        sql = (
            f"SELECT {', '.join(self._quote_mysql_identifier(col) for col in selected)} "
            f"FROM {self._quote_mysql_identifier(table)} "
            f"WHERE {' AND '.join(where_parts)} LIMIT {max(int(limit), 1)}"
        )
        return self.remote_client.select(sql, tuple(params))

    def fetch_remote_rows_by_composite_keys(
        self,
        *,
        table: str,
        first_column: str,
        second_column: str,
        keys: list[tuple[Any, Any]],
        limit: int = 10000,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_identifier(table)
        if not keys:
            return []

        remote_columns = self.get_remote_columns(table)
        by_lower = {name.lower(): name for name in remote_columns}
        first = by_lower.get(str(first_column).lower())
        second = by_lower.get(str(second_column).lower())
        if not first or not second:
            return []

        selected = []
        for item in (columns or remote_columns):
            found = by_lower.get(str(item).lower())
            if found:
                selected.append(found)
        if not selected:
            selected = remote_columns

        parts: list[str] = []
        params: list[Any] = []
        for first_value, second_value in keys:
            parts.append(
                f"({self._quote_mysql_identifier(first)} = %s AND {self._quote_mysql_identifier(second)} = %s)"
            )
            params.extend([first_value, second_value])
        if not parts:
            return []

        sql = (
            f"SELECT {', '.join(self._quote_mysql_identifier(col) for col in selected)} "
            f"FROM {self._quote_mysql_identifier(table)} "
            f"WHERE {' OR '.join(parts)} LIMIT {max(int(limit), 1)}"
        )
        return self.remote_client.select(sql, tuple(params))

    def fetch_remote_rows_like(
        self,
        *,
        table: str,
        column: str,
        value: str,
        limit: int = 100,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_identifier(table)
        self._validate_identifier(column)
        needle = str(value or "").strip()
        if not needle:
            return []

        remote_columns = self.get_remote_columns(table)
        remote_column_set = set(remote_columns)
        if column not in remote_column_set:
            return []

        selected = [item for item in (columns or remote_columns) if item in remote_column_set]
        if not selected:
            selected = remote_columns

        sql = (
            f"SELECT {', '.join(self._quote_mysql_identifier(col) for col in selected)} "
            f"FROM {self._quote_mysql_identifier(table)} "
            f"WHERE CAST({self._quote_mysql_identifier(column)} AS CHAR) LIKE %s "
            f"LIMIT {max(int(limit), 1)}"
        )
        return self.remote_client.select(sql, (f"%{needle}%",))

    def upsert_rows(self, *, table: str, rows: list[dict[str, Any]], sync_batch_id: str | None = None) -> int:
        if not rows:
            return 0

        schema_info = self.ensure_table(table)
        remote_columns = {item.name for item in schema_info.columns}
        metadata = {
            "_synced_at": timezone.now(),
            "_sync_batch_id": sync_batch_id or timezone.now().strftime("%Y%m%d%H%M%S"),
            "_deleted_at": None,
        }

        payload_rows: list[dict[str, Any]] = []
        for row in rows:
            row_lookup = {str(key).lower(): key for key in row.keys()}
            payload: dict[str, Any] = {}
            for key in remote_columns:
                raw_key = row_lookup.get(str(key).lower())
                if raw_key is None:
                    continue
                payload[key] = row.get(raw_key)

            if not payload:
                continue
            source_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
            payload["_source_hash"] = hashlib.sha1(source_json.encode("utf-8")).hexdigest()  # noqa: S324
            payload.update(metadata)
            payload_rows.append(payload)

        if not payload_rows:
            return len(rows)

        columns = list(payload_rows[0].keys())
        conflict_columns = schema_info.primary_key_columns or (schema_info.unique_keys[0] if schema_info.unique_keys else ["_source_hash"])
        update_columns = [column for column in columns if column not in conflict_columns]

        columns_sql = ", ".join(self._q(col) for col in columns)
        values_sql = ", ".join(["%s"] * len(columns))
        conflict_sql = ", ".join(self._q(col) for col in conflict_columns)
        update_sql = ", ".join(f"{self._q(col)} = EXCLUDED.{self._q(col)}" for col in update_columns)

        sql = (
            f"INSERT INTO {self._q(table)} ({columns_sql}) VALUES ({values_sql}) "
            f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {update_sql}"
        )
        values = [tuple(row.get(col) for col in columns) for row in payload_rows]

        failed = 0
        with transaction.atomic(using=self.db_alias):
            with connections[self.db_alias].cursor() as cursor:
                bulk_sid = transaction.savepoint(using=self.db_alias)
                try:
                    cursor.executemany(sql, values)
                    transaction.savepoint_commit(bulk_sid, using=self.db_alias)
                    return 0
                except Exception:  # noqa: BLE001
                    transaction.savepoint_rollback(bulk_sid, using=self.db_alias)

                for item in values:
                    row_sid = transaction.savepoint(using=self.db_alias)
                    try:
                        cursor.execute(sql, item)
                        transaction.savepoint_commit(row_sid, using=self.db_alias)
                    except Exception:  # noqa: BLE001
                        transaction.savepoint_rollback(row_sid, using=self.db_alias)
                        failed += 1
        return failed

    def column_exists(self, *, table: str, column: str) -> bool:
        if not column:
            return False
        by_lower = {name.lower() for name in self.get_local_columns(table)}
        return str(column).lower() in by_lower

    def first_existing_column(self, *, table: str, candidates: list[str]) -> str | None:
        columns = self.get_local_columns(table)
        by_lower = {name.lower(): name for name in columns}
        for candidate in candidates:
            found = by_lower.get(str(candidate).lower())
            if found:
                return found
        return None

    def _q(self, identifier: str) -> str:
        self._validate_identifier(identifier)
        escaped = str(identifier).replace('"', '""')
        return f'"{escaped}"'

    def _quote_mysql_identifier(self, identifier: str) -> str:
        self._validate_identifier(identifier)
        return f"`{identifier}`"

    def _validate_identifier(self, identifier: str) -> None:
        value = str(identifier or "").strip()
        if not _IDENTIFIER_RE.match(value):
            raise AutoDbProRemoteClientError("Invalid SQL identifier.")

    def _get_local_keys(self, table: str) -> tuple[list[str], list[list[str]]]:
        self._validate_identifier(table)
        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT tc.constraint_name, tc.constraint_type, kcu.column_name, kcu.ordinal_position
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_schema = kcu.constraint_schema
                 AND tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.table_schema = current_schema()
                  AND tc.table_name = %s
                  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
                ORDER BY tc.constraint_name, kcu.ordinal_position
                """,
                [table],
            )
            rows = cursor.fetchall()

        by_constraint: dict[str, tuple[str, list[str]]] = {}
        for constraint_name, constraint_type, column_name, _ordinal_position in rows:
            name = str(constraint_name)
            kind = str(constraint_type)
            entry = by_constraint.get(name)
            if entry is None:
                entry = (kind, [])
                by_constraint[name] = entry
            entry[1].append(str(column_name))

        primary: list[str] = []
        unique_keys: list[list[str]] = []
        for kind, columns in by_constraint.values():
            if not columns:
                continue
            if kind == "PRIMARY KEY":
                primary = list(columns)
            elif kind == "UNIQUE":
                unique_keys.append(list(columns))
        return primary, unique_keys
