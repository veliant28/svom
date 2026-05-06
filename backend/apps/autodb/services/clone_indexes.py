from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from django.db import connections


@dataclass(frozen=True)
class IndexTarget:
    table: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class IndexEnsureResult:
    table: str
    columns: tuple[str, ...]
    index_name: str
    status: str
    message: str = ""


class AutoDbCloneIndexService:
    """Creates technical indexes for raw clone tables without altering source schema."""

    VEHICLE_INDEX_TARGETS: tuple[IndexTarget, ...] = (
        IndexTarget("manufacturers", ("id",)),
        IndexTarget("manufacturers", ("description",)),
        IndexTarget("manufacturers", ("fulldescription",)),
        IndexTarget("manufacturers", ("ispassengercar",)),
        IndexTarget("models", ("id",)),
        IndexTarget("models", ("manufacturerid",)),
        IndexTarget("models", ("description",)),
        IndexTarget("models", ("fulldescription",)),
        IndexTarget("passanger_cars", ("id",)),
        IndexTarget("passanger_cars", ("modelid",)),
        IndexTarget("passanger_cars", ("constructioninterval",)),
        IndexTarget("passanger_cars", ("description",)),
        IndexTarget("passanger_cars", ("fulldescription",)),
        IndexTarget("engines", ("id",)),
        IndexTarget("passanger_car_engines", ("passangercarid",)),
        IndexTarget("passanger_car_engines", ("engineid",)),
        IndexTarget("passanger_car_attributes", ("passangercarid",)),
        IndexTarget("passanger_car_attributes", ("attributetype",)),
        IndexTarget("passanger_car_attributes", ("displaytitle",)),
        IndexTarget("prd", ("id",)),
        IndexTarget("prd", ("parentid",)),
        IndexTarget("prd", ("description",)),
        IndexTarget("prd", ("fulldescription",)),
        IndexTarget("passanger_car_trees", ("passangercarid",)),
        IndexTarget("passanger_car_trees", ("searchtreeid",)),
        IndexTarget("passanger_car_trees", ("parentid",)),
        IndexTarget("passanger_car_trees", ("id",)),
    )
    ARTICLE_INDEX_TARGETS: tuple[IndexTarget, ...] = (
        IndexTarget("suppliers", ("id",)),
        IndexTarget("suppliers", ("description",)),
        IndexTarget("suppliers", ("matchcode",)),
        IndexTarget("articles", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("articles", ("supplierid",)),
        IndexTarget("articles", ("datasupplierarticlenumber",)),
        IndexTarget("articles", ("normalizeddescription",)),
        IndexTarget("article_numbers", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_attributes", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_li", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_li", ("linkagetypeid", "linkageid")),
        IndexTarget("article_li", ("linkageid",)),
        IndexTarget("article_links", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_links", ("productid",)),
        IndexTarget("article_links", ("linkageid",)),
        IndexTarget("article_prd", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_prd", ("productid",)),
        IndexTarget("article_images", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_inf", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_oe", ("supplierid", "datasupplierarticlenumber")),
        IndexTarget("article_oe", ("oenbr",)),
        IndexTarget("article_oe", ("oenbr_clr",)),
        IndexTarget("article_cross", ("supplierid", "partsdatasupplierarticlenumber")),
        IndexTarget("article_cross", ("partsdatasupplierarticlenumber",)),
        IndexTarget("article_cross", ("oenbr",)),
        IndexTarget("article_ean", ("supplierid",)),
        IndexTarget("article_ean", ("datasupplierarticlenumber",)),
        IndexTarget("article_ean", ("ean",)),
    )

    def __init__(self, *, db_alias: str = "auto_db_pro"):
        self.db_alias = db_alias

    def ensure_vehicle_catalog_indexes(self, *, tables: list[str] | None = None) -> list[IndexEnsureResult]:
        return self._ensure_targets(targets=self.VEHICLE_INDEX_TARGETS, tables=tables)

    def ensure_article_catalog_indexes(self, *, tables: list[str] | None = None) -> list[IndexEnsureResult]:
        return self._ensure_targets(targets=self.ARTICLE_INDEX_TARGETS, tables=tables)

    def ensure_indexes(self, *, tables: list[str] | None = None) -> list[IndexEnsureResult]:
        combined = self.VEHICLE_INDEX_TARGETS + self.ARTICLE_INDEX_TARGETS
        return self._ensure_targets(targets=combined, tables=tables)

    def collect_vehicle_catalog_index_status(self, *, tables: list[str] | None = None) -> list[IndexEnsureResult]:
        return self._collect_targets_status(targets=self.VEHICLE_INDEX_TARGETS, tables=tables)

    def collect_article_catalog_index_status(self, *, tables: list[str] | None = None) -> list[IndexEnsureResult]:
        return self._collect_targets_status(targets=self.ARTICLE_INDEX_TARGETS, tables=tables)

    def _ensure_targets(self, *, targets: tuple[IndexTarget, ...], tables: list[str] | None = None) -> list[IndexEnsureResult]:
        requested = {name for name in (tables or [])}
        results: list[IndexEnsureResult] = []

        with connections[self.db_alias].cursor() as cursor:
            for target in targets:
                if requested and target.table not in requested:
                    continue

                index_name = self._build_index_name(target.table, target.columns)
                if not self._table_exists(cursor, target.table):
                    results.append(
                        IndexEnsureResult(
                            table=target.table,
                            columns=target.columns,
                            index_name=index_name,
                            status="skipped_missing_table",
                            message="table does not exist",
                        )
                    )
                    continue

                existing_columns = self._get_local_columns(cursor, target.table)
                resolved_columns = self._resolve_columns_case_insensitive(
                    existing_columns=existing_columns,
                    requested_columns=target.columns,
                )
                missing_columns = [name for name in target.columns if name.lower() not in {col.lower() for col in resolved_columns}]
                if missing_columns:
                    results.append(
                        IndexEnsureResult(
                            table=target.table,
                            columns=target.columns,
                            index_name=index_name,
                            status="skipped_missing_column",
                            message=f"missing columns: {', '.join(missing_columns)}",
                        )
                    )
                    continue

                if self._index_exists(cursor, index_name):
                    results.append(
                        IndexEnsureResult(
                            table=target.table,
                            columns=target.columns,
                            index_name=index_name,
                            status="exists",
                        )
                    )
                    continue

                columns_sql = ", ".join(self._q(col) for col in resolved_columns)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {self._q(index_name)} ON {self._q(target.table)} ({columns_sql})"
                )
                results.append(
                    IndexEnsureResult(
                        table=target.table,
                        columns=target.columns,
                        index_name=index_name,
                        status="created",
                    )
                )
        return results

    def _collect_targets_status(self, *, targets: tuple[IndexTarget, ...], tables: list[str] | None = None) -> list[IndexEnsureResult]:
        requested = {name for name in (tables or [])}
        statuses: list[IndexEnsureResult] = []

        with connections[self.db_alias].cursor() as cursor:
            for target in targets:
                if requested and target.table not in requested:
                    continue
                index_name = self._build_index_name(target.table, target.columns)
                if not self._table_exists(cursor, target.table):
                    statuses.append(
                        IndexEnsureResult(
                            table=target.table,
                            columns=target.columns,
                            index_name=index_name,
                            status="missing_table",
                            message="table does not exist",
                        )
                    )
                    continue

                existing_columns = self._get_local_columns(cursor, target.table)
                resolved_columns = self._resolve_columns_case_insensitive(
                    existing_columns=existing_columns,
                    requested_columns=target.columns,
                )
                missing_columns = [name for name in target.columns if name.lower() not in {col.lower() for col in resolved_columns}]
                if missing_columns:
                    statuses.append(
                        IndexEnsureResult(
                            table=target.table,
                            columns=target.columns,
                            index_name=index_name,
                            status="missing_column",
                            message=f"missing columns: {', '.join(missing_columns)}",
                        )
                    )
                    continue

                status = "present" if self._index_exists(cursor, index_name) else "missing"
                statuses.append(
                    IndexEnsureResult(
                        table=target.table,
                        columns=target.columns,
                        index_name=index_name,
                        status=status,
                    )
                )
        return statuses

    def _table_exists(self, cursor, table: str) -> bool:
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

    def _get_local_columns(self, cursor, table: str) -> set[str]:
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

    def _resolve_columns_case_insensitive(self, *, existing_columns: set[str], requested_columns: tuple[str, ...]) -> tuple[str, ...]:
        by_lower = {name.lower(): name for name in existing_columns}
        resolved: list[str] = []
        for name in requested_columns:
            match = by_lower.get(name.lower())
            if match:
                resolved.append(match)
        return tuple(resolved)

    def _index_exists(self, cursor, index_name: str) -> bool:
        cursor.execute(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND indexname = %s
            LIMIT 1
            """,
            [index_name],
        )
        return cursor.fetchone() is not None

    def _build_index_name(self, table: str, columns: tuple[str, ...]) -> str:
        base = f"ix_autodb_clone_{table}_{'_'.join(columns)}"
        if len(base) <= 63:
            return base

        digest = sha1(base.encode("utf-8")).hexdigest()[:8]  # noqa: S324
        truncated = base[: 63 - len(digest) - 1]
        return f"{truncated}_{digest}"

    def _q(self, identifier: str) -> str:
        escaped = str(identifier).replace('"', '""')
        return f'"{escaped}"'
