from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from django.conf import settings
from django.db import connections, transaction
from django.utils import timezone

from apps.autodb.models import AutoDbSyncState
from apps.autodb.services.clone_schema import AutoDbCloneSchemaService
from apps.autodb.services.remote_client import (
    ARTICLE_CATALOG_TABLE_WHITELIST,
    VEHICLE_CATALOG_TABLE_WHITELIST,
    AutoDbProRemoteClient,
    AutoDbProRemoteClientError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloneTableResult:
    table: str
    status: str
    total_rows: int
    processed_rows: int
    failed_rows: int


class AutoDbCloneSyncService:
    VEHICLE_TABLES = tuple(sorted(VEHICLE_CATALOG_TABLE_WHITELIST))
    ARTICLE_TABLES = tuple(sorted(ARTICLE_CATALOG_TABLE_WHITELIST))
    KEYSET_CURSOR_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
        "passanger_car_trees": ("id", "passangercarid", "searchtreeid"),
    }

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

    def resolve_tables(self, *, only: str | None, vehicle_catalog: bool, article_catalog: bool) -> list[str]:
        if only:
            return [only]

        tables: list[str] = []
        if vehicle_catalog:
            tables.extend(self.VEHICLE_TABLES)
        if article_catalog:
            tables.extend(self.ARTICLE_TABLES)
        if not tables:
            tables.extend(self.VEHICLE_TABLES)
        return tables

    def sync(
        self,
        *,
        tables: list[str],
        batch_size: int,
        limit: int | None,
        resume: bool,
        dry_run: bool,
        force_recreate_table: bool,
        schema_only: bool,
        data_only: bool,
        start_from_id: int | None,
        progress_every_batches: int = 0,
        progress_callback: Callable[..., None] | None = None,
    ) -> list[CloneTableResult]:
        results: list[CloneTableResult] = []
        for table in tables:
            try:
                result = self._sync_table(
                    table=table,
                    batch_size=max(int(batch_size), 1),
                    limit=limit,
                    resume=resume,
                    dry_run=dry_run,
                    force_recreate_table=force_recreate_table,
                    schema_only=schema_only,
                    data_only=data_only,
                    start_from_id=start_from_id,
                    progress_every_batches=progress_every_batches,
                    progress_callback=progress_callback,
                )
            except AutoDbProRemoteClientError as exc:
                status = "permission_denied" if self._is_permission_denied(exc) else "failed"
                existing_state = self._get_or_create_state(table)
                self._mark_state(
                    table=table,
                    status=status,
                    error=str(exc),
                    processed_rows=int(existing_state.processed_rows or 0),
                    failed_rows=int(existing_state.failed_rows or 0),
                    total_rows=int(existing_state.total_rows or 0),
                    last_pk=existing_state.last_pk,
                    last_offset=int(existing_state.last_offset or 0),
                    last_cursor=str(existing_state.last_cursor or ""),
                    finished_at=timezone.now(),
                )
                logger.error("Auto_DB_Pro clone sync skipped table=%s error=%s", table, exc)
                result = CloneTableResult(
                    table=table,
                    status=status,
                    total_rows=int(existing_state.total_rows or 0),
                    processed_rows=int(existing_state.processed_rows or 0),
                    failed_rows=int(existing_state.failed_rows or 0),
                )
            results.append(result)
        return results

    def _sync_table(
        self,
        *,
        table: str,
        batch_size: int,
        limit: int | None,
        resume: bool,
        dry_run: bool,
        force_recreate_table: bool,
        schema_only: bool,
        data_only: bool,
        start_from_id: int | None,
        progress_every_batches: int,
        progress_callback: Callable[..., None] | None,
    ) -> CloneTableResult:
        info = self.schema_service.introspect_table(table)
        if not data_only:
            self.schema_service.ensure_table(table, force_recreate=force_recreate_table)

        if schema_only:
            self._mark_state(table=table, status="schema_only", error="", processed_rows=0, failed_rows=0)
            return CloneTableResult(table=table, status="schema_only", total_rows=0, processed_rows=0, failed_rows=0)

        state = self._get_or_create_state(table)
        if force_recreate_table:
            self._reset_state(state)

        pk_column, pk_is_numeric = self._resolve_pk(info)
        if not pk_is_numeric:
            pk_column = None

        keyset_columns = self.KEYSET_CURSOR_TABLE_COLUMNS.get(table)
        last_pk = state.last_pk if resume and pk_column and state.last_pk is not None else None
        offset = int(state.last_offset or 0) if resume and not pk_column else 0
        keyset_cursor = (
            self._parse_keyset_cursor(raw_cursor=state.last_cursor, expected_size=len(keyset_columns))
            if resume and keyset_columns
            else None
        )
        base_processed = int(state.processed_rows or 0) if resume else 0
        base_failed = int(state.failed_rows or 0) if resume else 0

        skip_total_count = bool(getattr(settings, "AUTODB_PRO_REMOTE_SKIP_TOTAL_COUNT", False))
        total_rows = 0
        if not skip_total_count:
            try:
                total_rows = self.remote_client.count_table(table, pk_column=pk_column, start_from_id=start_from_id)
            except AutoDbProRemoteClientError as exc:
                logger.warning(
                    "Auto_DB_Pro clone sync failed to count rows for table=%s; continue with unknown total. error=%s",
                    table,
                    exc,
                )
        processed_rows = 0
        failed_rows = 0
        batch_no = 0
        sync_batch_id = timezone.now().strftime("%Y%m%d%H%M%S")
        initial_cursor = (
            self._render_keyset_cursor(values=keyset_cursor)
            if keyset_columns and keyset_cursor is not None
            else self._render_cursor(pk_column=pk_column, last_pk=last_pk, offset=offset)
        )

        self._mark_state(
            table=table,
            status="running",
            error="",
            processed_rows=base_processed,
            failed_rows=base_failed,
            total_rows=total_rows,
            started_at=timezone.now(),
            last_pk=last_pk,
            last_offset=offset,
            last_cursor=initial_cursor,
            metadata={
                "batch_no": 0,
                "batch_size": batch_size,
            },
        )

        while True:
            if limit is not None and processed_rows >= int(limit):
                break

            remaining = None
            if limit is not None:
                remaining = max(int(limit) - processed_rows, 0)
                if remaining <= 0:
                    break

            if keyset_columns:
                rows = self.remote_client.fetch_batch_keyset(
                    table,
                    cursor_columns=keyset_columns,
                    last_values=keyset_cursor,
                    batch_size=batch_size,
                    remaining=remaining,
                )
            else:
                rows = self.remote_client.fetch_batch(
                    table,
                    pk_column=pk_column,
                    last_pk=last_pk,
                    offset=offset,
                    batch_size=batch_size,
                    remaining=remaining,
                    start_from_id=start_from_id,
                )
            if not rows:
                break

            batch_no += 1
            now = timezone.now()
            write_rows = [self._prepare_row(row=row, synced_at=now, sync_batch_id=sync_batch_id) for row in rows]
            if not dry_run:
                failed_rows += self._upsert_rows(table=table, rows=write_rows, info=info)

            processed_rows += len(rows)
            if keyset_columns:
                keyset_cursor = tuple(rows[-1].get(col) for col in keyset_columns)
                offset += len(rows)
            elif pk_column:
                candidate = rows[-1].get(pk_column)
                try:
                    last_pk = int(candidate) if candidate is not None else last_pk
                except (TypeError, ValueError):
                    last_pk = last_pk
            else:
                offset += len(rows)

            total_processed = base_processed + processed_rows
            total_failed = base_failed + failed_rows
            last_cursor = (
                self._render_keyset_cursor(values=keyset_cursor)
                if keyset_columns and keyset_cursor is not None
                else self._render_cursor(pk_column=pk_column, last_pk=last_pk, offset=offset)
            )
            self._mark_state(
                table=table,
                status="running",
                error="",
                processed_rows=total_processed,
                failed_rows=total_failed,
                total_rows=total_rows,
                last_pk=last_pk,
                last_offset=offset,
                last_cursor=last_cursor,
                metadata={
                    "batch_no": batch_no,
                    "batch_size": batch_size,
                },
            )
            if progress_every_batches > 0 and progress_callback and batch_no % progress_every_batches == 0:
                progress_callback(
                    table=table,
                    batch_no=batch_no,
                    processed_rows=total_processed,
                    failed_rows=total_failed,
                    total_rows=total_rows,
                    last_cursor=last_cursor,
                )

        final_status = "completed" if failed_rows == 0 else "paused"
        if dry_run:
            final_status = "dry_run"

        final_processed = base_processed + processed_rows
        final_failed = base_failed + failed_rows
        final_cursor = (
            self._render_keyset_cursor(values=keyset_cursor)
            if keyset_columns and keyset_cursor is not None
            else self._render_cursor(pk_column=pk_column, last_pk=last_pk, offset=offset)
        )
        self._mark_state(
            table=table,
            status=final_status,
            error="",
            processed_rows=final_processed,
            failed_rows=final_failed,
            total_rows=total_rows,
            finished_at=timezone.now(),
            last_pk=last_pk,
            last_offset=offset,
            last_cursor=final_cursor,
            metadata={
                "batch_no": batch_no,
                "batch_size": batch_size,
            },
        )

        return CloneTableResult(
            table=table,
            status=final_status,
            total_rows=total_rows,
            processed_rows=final_processed,
            failed_rows=final_failed,
        )

    def _prepare_row(self, *, row: dict[str, Any], synced_at: datetime, sync_batch_id: str) -> dict[str, Any]:
        payload = dict(row)
        payload["_synced_at"] = synced_at
        payload["_sync_batch_id"] = sync_batch_id
        payload["_source_hash"] = hashlib.sha1(  # noqa: S324
            json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        payload["_deleted_at"] = None
        return payload

    def _upsert_rows(self, *, table: str, rows: list[dict[str, Any]], info) -> int:
        if not rows:
            return 0

        columns = list(rows[0].keys())
        conflict_columns = info.primary_key_columns or (info.unique_keys[0] if info.unique_keys else ["_source_hash"])
        update_columns = [col for col in columns if col not in conflict_columns]

        columns_sql = ", ".join(self._q(col) for col in columns)
        values_sql = ", ".join(["%s"] * len(columns))
        conflict_sql = ", ".join(self._q(col) for col in conflict_columns)
        update_sql = ", ".join(f"{self._q(col)} = EXCLUDED.{self._q(col)}" for col in update_columns)

        sql = (
            f"INSERT INTO {self._q(table)} ({columns_sql}) VALUES ({values_sql}) "
            f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {update_sql}"
        )

        values = [tuple(row.get(col) for col in columns) for row in rows]
        failed = 0
        with transaction.atomic(using=self.db_alias):
            with connections[self.db_alias].cursor() as cursor:
                try:
                    cursor.executemany(sql, values)
                    return 0
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Auto_DB_Pro clone batch upsert fallback to row-by-row table=%s reason=%s",
                        table,
                        exc,
                    )
                for item in values:
                    try:
                        cursor.execute(sql, item)
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        logger.warning("Auto_DB_Pro clone row upsert failed table=%s reason=%s", table, exc)
        return failed

    def _resolve_pk(self, info) -> tuple[str | None, bool]:
        numeric_types = {"tinyint", "smallint", "int", "integer", "mediumint", "bigint"}
        if info.primary_key_columns and len(info.primary_key_columns) == 1:
            pk_column = info.primary_key_columns[0]
            remote_col = next((col for col in info.columns if col.name == pk_column), None)
            if remote_col is not None:
                return pk_column, remote_col.data_type.lower() in numeric_types

        return None, False

    def _get_or_create_state(self, table: str) -> AutoDbSyncState:
        state, _ = AutoDbSyncState.objects.using(self.db_alias).get_or_create(source_table=table)
        return state

    def _reset_state(self, state: AutoDbSyncState) -> None:
        state.status = "pending"
        state.last_pk = None
        state.last_offset = 0
        state.last_cursor = ""
        state.total_rows = 0
        state.processed_rows = 0
        state.failed_rows = 0
        state.started_at = None
        state.finished_at = None
        state.last_error = ""
        state.metadata = {}
        state.save(using=self.db_alias)

    def _mark_state(
        self,
        *,
        table: str,
        status: str,
        error: str,
        processed_rows: int,
        failed_rows: int,
        total_rows: int | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        last_pk: int | None = None,
        last_offset: int | None = None,
        last_cursor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        state = self._get_or_create_state(table)
        state.status = status
        state.last_error = error[:4000]
        state.processed_rows = int(processed_rows)
        state.failed_rows = int(failed_rows)
        if total_rows is not None:
            state.total_rows = int(total_rows)
        if started_at is not None:
            state.started_at = started_at
        if finished_at is not None:
            state.finished_at = finished_at
        state.last_pk = int(last_pk) if last_pk is not None else None
        state.last_offset = int(last_offset) if last_offset is not None else 0
        if last_cursor is not None:
            state.last_cursor = str(last_cursor)
        state.metadata = {
            "updated_at": datetime.now(UTC).isoformat(),
            "status": status,
        }
        if metadata:
            state.metadata.update(metadata)
        state.save(using=self.db_alias)

    def _is_permission_denied(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "select command denied" in message or "permission denied" in message

    def _q(self, identifier: str) -> str:
        escaped = str(identifier).replace('"', '""')
        return f'"{escaped}"'

    def _render_cursor(self, *, pk_column: str | None, last_pk: int | None, offset: int) -> str:
        if pk_column:
            return f"{pk_column}:{last_pk if last_pk is not None else '-'}"
        return f"offset:{max(int(offset), 0)}"

    def _render_keyset_cursor(self, *, values: tuple[Any, ...] | None) -> str:
        if not values:
            return ""
        return "keyset:" + json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))

    def _parse_keyset_cursor(self, *, raw_cursor: str, expected_size: int) -> tuple[Any, ...] | None:
        value = str(raw_cursor or "").strip()
        if not value.startswith("keyset:"):
            return None
        try:
            decoded = json.loads(value[7:])
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(decoded, list) or len(decoded) != expected_size:
            return None
        return tuple(decoded)
