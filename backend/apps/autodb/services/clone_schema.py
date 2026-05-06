from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha1
from typing import Any

from django.db import connections, transaction

from apps.autodb.services.remote_client import AutoDbProRemoteClient


@dataclass(frozen=True)
class RemoteColumn:
    name: str
    data_type: str
    column_type: str
    is_nullable: bool
    character_maximum_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None
    datetime_precision: int | None
    ordinal_position: int


@dataclass(frozen=True)
class CloneSchemaInfo:
    table: str
    columns: list[RemoteColumn]
    primary_key_columns: list[str]
    unique_keys: list[list[str]]


class AutoDbCloneSchemaService:
    SERVICE_COLUMNS: dict[str, str] = {
        "_synced_at": "TIMESTAMPTZ",
        "_sync_batch_id": "VARCHAR(64)",
        "_source_hash": "VARCHAR(64)",
        "_deleted_at": "TIMESTAMPTZ",
    }

    def __init__(self, *, remote_client: AutoDbProRemoteClient | None = None, db_alias: str = "auto_db_pro"):
        self.remote_client = remote_client or AutoDbProRemoteClient.from_settings()
        self.db_alias = db_alias

    def introspect_table(self, table: str) -> CloneSchemaInfo:
        rows = self.remote_client.get_table_schema(table)
        columns = [self._to_column(row) for row in rows]
        primary_key_columns = self.remote_client.get_primary_key_columns(table)
        unique_keys = self.remote_client.get_unique_key_columns(table)
        return CloneSchemaInfo(
            table=table,
            columns=columns,
            primary_key_columns=primary_key_columns,
            unique_keys=unique_keys,
        )

    def ensure_table(self, table: str, *, force_recreate: bool = False) -> CloneSchemaInfo:
        info = self.introspect_table(table)
        table_name = self._quote_pg_identifier(table)

        with transaction.atomic(using=self.db_alias):
            with connections[self.db_alias].cursor() as cursor:
                if force_recreate:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

                if not self._table_exists(table):
                    ddl_parts = [self._build_column_ddl(column) for column in info.columns]
                    ddl_parts.extend(f"{self._quote_pg_identifier(name)} {column_type}" for name, column_type in self.SERVICE_COLUMNS.items())
                    ddl = f"CREATE TABLE {table_name} ({', '.join(ddl_parts)})"
                    cursor.execute(ddl)
                else:
                    existing_columns = self._get_local_columns(table)
                    for column in info.columns:
                        if column.name in existing_columns:
                            continue
                        cursor.execute(
                            f"ALTER TABLE {table_name} ADD COLUMN {self._build_column_ddl(column)}"
                        )
                    for service_name, service_type in self.SERVICE_COLUMNS.items():
                        if service_name in existing_columns:
                            continue
                        cursor.execute(
                            f"ALTER TABLE {table_name} ADD COLUMN {self._quote_pg_identifier(service_name)} {service_type}"
                        )

                self._ensure_pk_or_unique_indexes(cursor=cursor, info=info)

        return info

    def _ensure_pk_or_unique_indexes(self, *, cursor, info: CloneSchemaInfo) -> None:
        table_name = self._quote_pg_identifier(info.table)

        if info.primary_key_columns:
            constraint_name = self._quote_pg_identifier(f"{info.table}_pk")
            columns_sql = ", ".join(self._quote_pg_identifier(col) for col in info.primary_key_columns)
            cursor.execute(
                f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name}"
            )
            cursor.execute(
                f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} PRIMARY KEY ({columns_sql})"
            )
            return

        for unique_columns in info.unique_keys:
            if not unique_columns:
                continue
            index_name = self._quote_pg_identifier(self._stable_index_name(info.table, unique_columns))
            columns_sql = ", ".join(self._quote_pg_identifier(col) for col in unique_columns)
            cursor.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"
            )

        # Hash fallback for tables without known keys.
        if not info.unique_keys:
            hash_idx = self._quote_pg_identifier(f"{info.table}_source_hash_uq")
            cursor.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {hash_idx} ON {table_name} ({self._quote_pg_identifier('_source_hash')})"
            )

    def _table_exists(self, table: str) -> bool:
        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = %s
                LIMIT 1
                """,
                [table],
            )
            return cursor.fetchone() is not None

    def _get_local_columns(self, table: str) -> set[str]:
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
            return {str(item[0]) for item in cursor.fetchall()}

    def _build_column_ddl(self, column: RemoteColumn) -> str:
        column_name = self._quote_pg_identifier(column.name)
        pg_type = self._mysql_type_to_pg(column)
        null_sql = "NULL" if column.is_nullable else "NOT NULL"
        return f"{column_name} {pg_type} {null_sql}"

    def _mysql_type_to_pg(self, column: RemoteColumn) -> str:
        data_type = (column.data_type or "").strip().lower()
        column_type = (column.column_type or "").strip().lower()

        if data_type in {"bigint"}:
            return "BIGINT"
        if data_type in {"int", "integer", "mediumint"}:
            return "INTEGER"
        if data_type in {"smallint"}:
            return "SMALLINT"
        if data_type == "tinyint":
            return "SMALLINT"
        if data_type == "decimal":
            precision = column.numeric_precision
            scale = column.numeric_scale
            if precision is not None and scale is not None:
                return f"NUMERIC({precision},{scale})"
            return "NUMERIC"
        if data_type in {"double", "double precision"}:
            return "DOUBLE PRECISION"
        if data_type == "float":
            return "DOUBLE PRECISION"
        if data_type in {"datetime", "timestamp"}:
            return "TIMESTAMP"
        if data_type == "date":
            return "DATE"
        if data_type in {"time"}:
            return "TIME"
        if data_type in {"json"}:
            return "JSONB"
        if data_type in {"char", "varchar"}:
            length = column.character_maximum_length
            if length is not None and 0 < int(length) <= 65535:
                return f"VARCHAR({int(length)})"
            match = re.search(r"\((\d+)\)", column_type)
            if match:
                return f"VARCHAR({int(match.group(1))})"
            return "TEXT"
        if data_type in {"tinytext", "text", "mediumtext", "longtext"}:
            return "TEXT"
        if data_type in {"blob", "tinyblob", "mediumblob", "longblob", "binary", "varbinary"}:
            return "BYTEA"

        return "TEXT"

    def _to_column(self, row: dict[str, Any]) -> RemoteColumn:
        return RemoteColumn(
            name=str(row.get("column_name") or "").strip(),
            data_type=str(row.get("data_type") or "").strip(),
            column_type=str(row.get("column_type") or "").strip(),
            is_nullable=str(row.get("is_nullable") or "").strip().upper() == "YES",
            character_maximum_length=self._to_int(row.get("character_maximum_length")),
            numeric_precision=self._to_int(row.get("numeric_precision")),
            numeric_scale=self._to_int(row.get("numeric_scale")),
            datetime_precision=self._to_int(row.get("datetime_precision")),
            ordinal_position=max(self._to_int(row.get("ordinal_position")) or 0, 0),
        )

    def _stable_index_name(self, table: str, columns: list[str]) -> str:
        seed = f"{table}:{','.join(columns)}".encode("utf-8")
        suffix = sha1(seed).hexdigest()[:10]  # noqa: S324
        return f"{table}_{suffix}_uq"

    def _quote_pg_identifier(self, identifier: str) -> str:
        value = str(identifier or "").strip()
        if not value:
            raise ValueError("Identifier cannot be blank")
        escaped = value.replace('"', '""')
        return f'"{escaped}"'

    def _to_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
