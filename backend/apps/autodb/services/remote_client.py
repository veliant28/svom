from __future__ import annotations

import getpass
import re
from dataclasses import dataclass
from typing import Any, Iterable

import mysql.connector

from apps.autodb.services.remote_config import AutoDbRemoteConfigValidator


class AutoDbProRemoteClientError(RuntimeError):
    pass


_SELECT_RE = re.compile(r"^\s*select\b", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

VEHICLE_CATALOG_TABLE_WHITELIST = {
    "countries",
    "country_groups",
    "languages",
    "manufacturers",
    "models",
    "engines",
    "passanger_cars",
    "passanger_car_engines",
    "passanger_car_attributes",
    "prd",
    "passanger_car_trees",
}

ARTICLE_CATALOG_TABLE_WHITELIST = {
    "articles",
    "article_acc",
    "article_attributes",
    "article_cross",
    "article_ean",
    "article_images",
    "article_inf",
    "article_li",
    "article_links",
    "article_m",
    "article_nn",
    "article_numbers",
    "article_oe",
    "article_parts",
    "article_prd",
    "suppliers",
    "supplier_details",
}

REMOTE_TABLE_WHITELIST = VEHICLE_CATALOG_TABLE_WHITELIST | ARTICLE_CATALOG_TABLE_WHITELIST


@dataclass(frozen=True)
class AutoDbProRemoteClientConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    connect_timeout: int
    read_timeout: int
    batch_size: int


class AutoDbProRemoteClient:
    def __init__(self, config: AutoDbProRemoteClientConfig | None = None):
        self.config = config or self.from_settings()

    @classmethod
    def from_settings(cls) -> "AutoDbProRemoteClient":
        snapshot = AutoDbRemoteConfigValidator.snapshot()
        missing = snapshot.validation_errors(require_enabled=False)
        if snapshot.enabled and missing:
            raise AutoDbProRemoteClientError(
                "Auto_DB_Pro remote config invalid: " + "; ".join(missing)
            )
        return cls(
            config=AutoDbProRemoteClientConfig(
                host=snapshot.host,
                port=snapshot.port,
                database=snapshot.database,
                user=snapshot.user,
                password=snapshot.password,
                connect_timeout=snapshot.connect_timeout,
                read_timeout=snapshot.read_timeout,
                batch_size=snapshot.batch_size,
            )
        )

    def sanitized_config(self) -> dict[str, Any]:
        return {
            "host": self.config.host,
            "port": int(self.config.port),
            "database": self.config.database,
            "user": self.config.user,
            "password_set": bool(self.config.password),
            "connect_timeout": int(self.config.connect_timeout),
            "read_timeout": int(self.config.read_timeout),
            "batch_size": int(self.config.batch_size),
        }

    def os_user_fallback_risk(self) -> bool:
        local_user = str(getpass.getuser() or "").strip()
        remote_user = str(self.config.user or "").strip()
        return bool(remote_user and local_user and remote_user.lower() == local_user.lower())

    def check_connection(self) -> bool:
        rows = self.select("SELECT 1 AS ok")
        if not rows:
            return False
        first = rows[0]
        if isinstance(first, dict):
            return int(first.get("ok", 0) or 0) == 1
        return True

    def select(self, query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        self._ensure_select_only(query)
        conn = None
        try:
            conn = self._connect()
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())
                rows = cursor.fetchall() or []
            return [dict(item) for item in rows if isinstance(item, dict)]
        except Exception as exc:  # noqa: BLE001
            raise AutoDbProRemoteClientError(self._sanitize_error(exc)) from exc
        finally:
            self._close(conn)

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        self._ensure_table_allowed(table)
        return self.select(
            """
            SELECT
                COLUMN_NAME AS column_name,
                DATA_TYPE AS data_type,
                COLUMN_TYPE AS column_type,
                IS_NULLABLE AS is_nullable,
                COLUMN_DEFAULT AS column_default,
                CHARACTER_MAXIMUM_LENGTH AS character_maximum_length,
                NUMERIC_PRECISION AS numeric_precision,
                NUMERIC_SCALE AS numeric_scale,
                DATETIME_PRECISION AS datetime_precision,
                ORDINAL_POSITION AS ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ORDINAL_POSITION ASC
            """,
            (self.config.database, table),
        )

    def get_primary_key_columns(self, table: str) -> list[str]:
        self._ensure_table_allowed(table)
        rows = self.select(
            """
            SELECT k.COLUMN_NAME AS column_name
            FROM information_schema.table_constraints t
            JOIN information_schema.key_column_usage k
              ON t.constraint_name = k.constraint_name
             AND t.table_schema = k.table_schema
             AND t.table_name = k.table_name
            WHERE t.table_schema = %s
              AND t.table_name = %s
              AND t.constraint_type = 'PRIMARY KEY'
            ORDER BY k.ordinal_position ASC
            """,
            (self.config.database, table),
        )
        return [str(item.get("column_name")) for item in rows if item.get("column_name")]

    def get_unique_key_columns(self, table: str) -> list[list[str]]:
        self._ensure_table_allowed(table)
        rows = self.select(
            """
            SELECT
                s.index_name,
                s.seq_in_index,
                s.column_name
            FROM information_schema.statistics s
            WHERE s.table_schema = %s
              AND s.table_name = %s
              AND s.non_unique = 0
              AND s.index_name <> 'PRIMARY'
            ORDER BY s.index_name, s.seq_in_index
            """,
            (self.config.database, table),
        )
        by_index: dict[str, list[str]] = {}
        for item in rows:
            index_name = str(item.get("index_name") or "").strip()
            column_name = str(item.get("column_name") or "").strip()
            if not index_name or not column_name:
                continue
            by_index.setdefault(index_name, []).append(column_name)
        return [columns for columns in by_index.values() if columns]

    def count_table(self, table: str, *, pk_column: str | None = None, start_from_id: int | None = None) -> int:
        table_name = self._quote_table(table)
        query = f"SELECT COUNT(*) AS total FROM {table_name}"
        params: list[Any] = []

        if pk_column and start_from_id is not None:
            pk_name = self._quote_identifier(pk_column)
            query += f" WHERE {pk_name} >= %s"
            params.append(int(start_from_id))

        rows = self.select(query, tuple(params))
        if not rows:
            return 0
        return int(rows[0].get("total", 0) or 0)

    def fetch_batch(
        self,
        table: str,
        *,
        pk_column: str | None,
        last_pk: int | None,
        offset: int,
        batch_size: int,
        remaining: int | None = None,
        start_from_id: int | None = None,
        columns: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        table_name = self._quote_table(table)
        select_list = "*"
        if columns:
            quoted = [self._quote_identifier(col) for col in columns]
            select_list = ", ".join(quoted)

        limit = max(int(batch_size), 1)
        if remaining is not None:
            limit = min(limit, max(int(remaining), 0))
        if limit <= 0:
            return []

        params: list[Any] = []
        query = f"SELECT {select_list} FROM {table_name}"

        if pk_column:
            pk_name = self._quote_identifier(pk_column)
            conditions: list[str] = []
            if last_pk is not None:
                conditions.append(f"{pk_name} > %s")
                params.append(int(last_pk))
            elif start_from_id is not None:
                conditions.append(f"{pk_name} >= %s")
                params.append(int(start_from_id))

            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += f" ORDER BY {pk_name} ASC"
        else:
            query += " ORDER BY 1 ASC"
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, max(int(offset), 0)])
            return self.select(query, tuple(params))

        query += " LIMIT %s"
        params.append(limit)
        return self.select(query, tuple(params))

    def fetch_batch_keyset(
        self,
        table: str,
        *,
        cursor_columns: tuple[str, ...],
        last_values: tuple[Any, ...] | None,
        batch_size: int,
        remaining: int | None = None,
        columns: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not cursor_columns:
            raise AutoDbProRemoteClientError("Keyset cursor requires at least one column.")

        table_name = self._quote_table(table)
        select_list = "*"
        if columns:
            quoted = [self._quote_identifier(col) for col in columns]
            select_list = ", ".join(quoted)

        limit = max(int(batch_size), 1)
        if remaining is not None:
            limit = min(limit, max(int(remaining), 0))
        if limit <= 0:
            return []

        quoted_columns = [self._quote_identifier(col) for col in cursor_columns]
        query = f"SELECT {select_list} FROM {table_name}"
        params: list[Any] = []

        if last_values is not None:
            if len(last_values) != len(cursor_columns):
                raise AutoDbProRemoteClientError("Invalid keyset cursor values length.")

            comparisons: list[str] = []
            for idx, col_name in enumerate(quoted_columns):
                equal_parts = " AND ".join(f"{quoted_columns[i]} = %s" for i in range(idx))
                if equal_parts:
                    comparisons.append(f"({equal_parts} AND {col_name} > %s)")
                    params.extend(last_values[:idx])
                    params.append(last_values[idx])
                else:
                    comparisons.append(f"({col_name} > %s)")
                    params.append(last_values[idx])

            query += " WHERE " + " OR ".join(comparisons)

        order_clause = ", ".join(f"{col} ASC" for col in quoted_columns)
        query += f" ORDER BY {order_clause} LIMIT %s"
        params.append(limit)
        return self.select(query, tuple(params))

    def get_table_columns(self, table: str) -> list[str]:
        rows = self.fetch_batch(table, pk_column=None, last_pk=None, offset=0, batch_size=1)
        if rows:
            return list(rows[0].keys())

        table_name = self._quote_table(table)
        conn = None
        try:
            conn = self._connect()
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
                return [str(desc[0]) for desc in (cursor.description or [])]
        except Exception as exc:  # noqa: BLE001
            raise AutoDbProRemoteClientError(self._sanitize_error(exc)) from exc
        finally:
            self._close(conn)

    def resolve_pk_column(self, table: str, candidates: Iterable[str]) -> str | None:
        columns = {name.lower(): name for name in self.get_table_columns(table)}
        for candidate in candidates:
            key = str(candidate or "").strip().lower()
            if key and key in columns:
                return columns[key]
        return None

    def _connect(self):
        if not self.config.host:
            raise AutoDbProRemoteClientError(
                "Auto_DB_Pro remote config invalid: AUTODB_PRO_REMOTE_HOST is empty."
            )
        if not self.config.database:
            raise AutoDbProRemoteClientError(
                "Auto_DB_Pro remote config invalid: AUTODB_PRO_REMOTE_DATABASE is empty."
            )
        if not self.config.user:
            raise AutoDbProRemoteClientError(
                "Auto_DB_Pro remote config invalid: AUTODB_PRO_REMOTE_USER is empty."
            )
        if not self.config.password:
            raise AutoDbProRemoteClientError(
                "Auto_DB_Pro remote config invalid: AUTODB_PRO_REMOTE_PASSWORD is empty."
            )
        return mysql.connector.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            connection_timeout=self.config.connect_timeout,
            read_timeout=self.config.read_timeout,
            charset="utf8mb4",
            use_unicode=True,
        )

    def _close(self, conn) -> None:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _quote_table(self, table: str) -> str:
        self._ensure_table_allowed(table)
        return self._quote_identifier(table)

    def _quote_identifier(self, identifier: str) -> str:
        value = str(identifier or "").strip()
        if not _IDENTIFIER_RE.match(value):
            raise AutoDbProRemoteClientError("Invalid SQL identifier.")
        return f"`{value}`"

    def _ensure_table_allowed(self, table: str) -> None:
        table_name = str(table or "").strip()
        if table_name not in REMOTE_TABLE_WHITELIST:
            raise AutoDbProRemoteClientError(f"Table '{table_name}' is not allowed for remote access.")

    def _ensure_select_only(self, query: str) -> None:
        if not _SELECT_RE.match(str(query or "")):
            raise AutoDbProRemoteClientError("Only SELECT statements are allowed for Auto_DB_Pro remote client.")

    def _sanitize_error(self, exc: Exception) -> str:
        message = str(exc)
        password = str(self.config.password or "")
        if password:
            message = message.replace(password, "***")
        return f"Auto_DB_Pro remote query failed: {message}"
