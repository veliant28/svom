from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.autodb.models import (
    AutoDbCountry,
    AutoDbCountryGroup,
    AutoDbEngine,
    AutoDbLanguage,
    AutoDbPassengerCar,
    AutoDbPassengerCarEngine,
    AutoDbPassengerCarTree,
    AutoDbProductGroup,
    AutoDbSyncState,
    AutoDbVehicleAttribute,
    AutoDbVehicleManufacturer,
    AutoDbVehicleModel,
)
from apps.autodb.services.remote_client import AutoDbProRemoteClient
from apps.autodb.services.vehicle_catalog_mappers import AutoDbMappingError, TABLE_MAPPERS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TableSyncConfig:
    table: str
    model: Any
    unique_fields: tuple[str, ...]
    pk_candidates: tuple[str, ...]


@dataclass(frozen=True)
class TableSyncResult:
    table: str
    processed_rows: int
    failed_rows: int
    total_rows: int
    status: str


@dataclass(frozen=True)
class SyncRunResult:
    results: list[TableSyncResult]

    @property
    def processed_rows(self) -> int:
        return sum(item.processed_rows for item in self.results)

    @property
    def failed_rows(self) -> int:
        return sum(item.failed_rows for item in self.results)


class AutoDbVehicleCatalogSyncService:
    TABLE_ORDER = (
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
    )

    TABLE_CONFIG: dict[str, TableSyncConfig] = {
        "countries": TableSyncConfig(
            table="countries",
            model=AutoDbCountry,
            unique_fields=("autodb_country_id",),
            pk_candidates=("isocodeno", "id", "country_id"),
        ),
        "country_groups": TableSyncConfig(
            table="country_groups",
            model=AutoDbCountryGroup,
            unique_fields=("autodb_country_group_id",),
            pk_candidates=("id", "country_group_id"),
        ),
        "languages": TableSyncConfig(
            table="languages",
            model=AutoDbLanguage,
            unique_fields=("autodb_language_id",),
            pk_candidates=("id", "language_id"),
        ),
        "manufacturers": TableSyncConfig(
            table="manufacturers",
            model=AutoDbVehicleManufacturer,
            unique_fields=("autodb_manufacturer_id",),
            pk_candidates=("id", "manufacturer_id"),
        ),
        "models": TableSyncConfig(
            table="models",
            model=AutoDbVehicleModel,
            unique_fields=("autodb_model_id",),
            pk_candidates=("id", "model_id", "modelid"),
        ),
        "engines": TableSyncConfig(
            table="engines",
            model=AutoDbEngine,
            unique_fields=("autodb_engine_id",),
            pk_candidates=("id", "engine_id"),
        ),
        "passanger_cars": TableSyncConfig(
            table="passanger_cars",
            model=AutoDbPassengerCar,
            unique_fields=("autodb_vehicle_id",),
            pk_candidates=("id", "passangercarid", "passanger_car_id", "vehicle_id", "ktype"),
        ),
        "passanger_car_engines": TableSyncConfig(
            table="passanger_car_engines",
            model=AutoDbPassengerCarEngine,
            unique_fields=("source_row_id",),
            pk_candidates=("id", "row_id", "passangercarid", "passanger_car_id", "vehicle_id"),
        ),
        "passanger_car_attributes": TableSyncConfig(
            table="passanger_car_attributes",
            model=AutoDbVehicleAttribute,
            unique_fields=("source_row_id",),
            pk_candidates=("id", "row_id", "passangercarid", "passanger_car_id", "vehicle_id"),
        ),
        "prd": TableSyncConfig(
            table="prd",
            model=AutoDbProductGroup,
            unique_fields=("autodb_prd_id",),
            pk_candidates=("id", "prd_id", "category_id"),
        ),
        "passanger_car_trees": TableSyncConfig(
            table="passanger_car_trees",
            model=AutoDbPassengerCarTree,
            unique_fields=("source_row_id",),
            pk_candidates=("id", "row_id", "passangercarid", "passanger_car_id", "vehicle_id"),
        ),
    }

    def __init__(
        self,
        *,
        remote_client: AutoDbProRemoteClient | None = None,
        db_alias: str = "auto_db_pro",
        progress_log_every: int = 1000,
    ) -> None:
        self.remote_client = remote_client or AutoDbProRemoteClient.from_settings()
        self.db_alias = db_alias
        self.progress_log_every = max(int(progress_log_every), 1)

    def sync(
        self,
        *,
        only: str | None = None,
        batch_size: int,
        resume: bool,
        force: bool,
        dry_run: bool,
        limit: int | None,
        start_from_id: int | None,
    ) -> SyncRunResult:
        batch = max(int(batch_size), 1)
        requested_tables = self._resolve_tables(only)
        results: list[TableSyncResult] = []

        for table in requested_tables:
            try:
                result = self._sync_table(
                    table=table,
                    batch_size=batch,
                    resume=resume,
                    force=force,
                    dry_run=dry_run,
                    limit=limit,
                    start_from_id=start_from_id,
                )
            except Exception as exc:  # noqa: BLE001
                if not dry_run:
                    self.mark_failed(table=table, error=str(exc))
                if only:
                    raise
                logger.error("Auto_DB_Pro vehicle sync table failed table=%s error=%s", table, exc)
                result = TableSyncResult(
                    table=table,
                    processed_rows=0,
                    failed_rows=0,
                    total_rows=0,
                    status=AutoDbSyncState.Status.FAILED,
                )
            results.append(result)

        return SyncRunResult(results=results)

    def _resolve_tables(self, only: str | None) -> list[str]:
        if only:
            table = str(only).strip()
            if table not in self.TABLE_CONFIG:
                raise ValueError(f"Unsupported vehicle catalog table: {table}")
            return [table]
        return list(self.TABLE_ORDER)

    def _sync_table(
        self,
        *,
        table: str,
        batch_size: int,
        resume: bool,
        force: bool,
        dry_run: bool,
        limit: int | None,
        start_from_id: int | None,
    ) -> TableSyncResult:
        config = self.TABLE_CONFIG[table]
        mapper = TABLE_MAPPERS[table]

        state: AutoDbSyncState | None = None
        if not dry_run:
            state = self._load_or_create_state(table)
            if force:
                self._reset_state(state)

        pk_column = self.remote_client.resolve_pk_column(table, config.pk_candidates)
        last_pk, offset = self._resolve_resume_cursor(
            state=state,
            resume=resume,
            start_from_id=start_from_id,
            pk_column=pk_column,
        )

        total_rows = self.remote_client.count_table(table, pk_column=pk_column, start_from_id=start_from_id)
        processed_rows = 0
        failed_rows = 0

        if not dry_run and state is not None:
            state.status = AutoDbSyncState.Status.RUNNING
            state.started_at = timezone.now()
            state.finished_at = None
            state.total_rows = int(total_rows)
            state.last_error = ""
            state.save(
                using=self.db_alias,
                update_fields=["status", "started_at", "finished_at", "total_rows", "last_error", "updated_at"],
            )

        while True:
            remaining = None
            if limit is not None:
                remaining = max(int(limit) - processed_rows, 0)
                if remaining <= 0:
                    break

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

            processed_rows += len(rows)
            mapped_rows: list[dict[str, Any]] = []

            for row in rows:
                try:
                    mapped = mapper(row)
                    mapped_rows.append(self._with_import_metadata(config.model, mapped))
                except AutoDbMappingError as exc:
                    failed_rows += 1
                    logger.warning("Auto_DB_Pro sync mapper error table=%s: %s", table, exc)
                except Exception as exc:  # noqa: BLE001
                    failed_rows += 1
                    logger.warning("Auto_DB_Pro sync unexpected mapper error table=%s: %s", table, exc)

            if not dry_run and mapped_rows:
                mapped_rows, skipped_fk_rows = self._filter_invalid_foreign_keys(table=table, rows=mapped_rows)
                failed_rows += skipped_fk_rows
                failed_rows += self._upsert_batch(config=config, rows=mapped_rows)

            if pk_column:
                candidate = rows[-1].get(pk_column)
                if candidate not in (None, ""):
                    last_pk = int(candidate)
            else:
                offset += len(rows)

            if processed_rows % self.progress_log_every == 0 or len(rows) < batch_size:
                logger.info(
                    "Auto_DB_Pro vehicle sync progress table=%s processed=%s failed=%s total=%s",
                    table,
                    processed_rows,
                    failed_rows,
                    total_rows,
                )

            if not dry_run and state is not None:
                state.processed_rows = processed_rows
                state.failed_rows = failed_rows
                state.last_pk = last_pk
                state.last_offset = offset
                state.metadata = {
                    "pk_column": pk_column,
                    "batch_size": batch_size,
                    "limit": limit,
                }
                state.save(
                    using=self.db_alias,
                    update_fields=[
                        "processed_rows",
                        "failed_rows",
                        "last_pk",
                        "last_offset",
                        "metadata",
                        "updated_at",
                    ],
                )

        status = AutoDbSyncState.Status.COMPLETED
        if failed_rows > 0:
            status = AutoDbSyncState.Status.PAUSED

        if not dry_run and state is not None:
            state.status = status
            state.finished_at = timezone.now()
            state.processed_rows = processed_rows
            state.failed_rows = failed_rows
            state.last_pk = last_pk
            state.last_offset = offset
            state.save(
                using=self.db_alias,
                update_fields=[
                    "status",
                    "finished_at",
                    "processed_rows",
                    "failed_rows",
                    "last_pk",
                    "last_offset",
                    "updated_at",
                ],
            )

        return TableSyncResult(
            table=table,
            processed_rows=processed_rows,
            failed_rows=failed_rows,
            total_rows=total_rows,
            status=status if not dry_run else "dry_run",
        )

    def mark_failed(self, *, table: str, error: str) -> None:
        state = self._load_or_create_state(table)
        state.status = AutoDbSyncState.Status.FAILED
        state.finished_at = timezone.now()
        state.last_error = str(error or "")[:4000]
        state.save(using=self.db_alias, update_fields=["status", "finished_at", "last_error", "updated_at"])

    def _resolve_resume_cursor(
        self,
        *,
        state: AutoDbSyncState | None,
        resume: bool,
        start_from_id: int | None,
        pk_column: str | None,
    ) -> tuple[int | None, int]:
        if start_from_id is not None:
            return int(start_from_id) - 1, 0

        if not resume or state is None:
            return None, 0

        if pk_column and state.last_pk is not None:
            return int(state.last_pk), 0

        return None, int(state.last_offset or 0)

    def _with_import_metadata(self, model: Any, row: dict[str, Any]) -> dict[str, Any]:
        now = timezone.now()
        field_names = {field.name for field in model._meta.concrete_fields}
        payload = dict(row)
        if "imported_at" in field_names:
            payload["imported_at"] = now
        if "source_payload" in field_names and "source_payload" not in payload:
            payload["source_payload"] = {}
        return payload

    def _upsert_batch(self, *, config: TableSyncConfig, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        rows = self._deduplicate_rows(config=config, rows=rows)
        model = config.model
        update_fields = sorted(set(rows[0].keys()) - set(config.unique_fields) - {"id"})
        failed_rows = 0

        try:
            instances = [model(**row) for row in rows]
            with transaction.atomic(using=self.db_alias):
                model.objects.using(self.db_alias).bulk_create(
                    instances,
                    batch_size=len(instances),
                    update_conflicts=True,
                    update_fields=update_fields,
                    unique_fields=list(config.unique_fields),
                )
            return 0
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Auto_DB_Pro sync bulk upsert fallback table=%s reason=%s",
                config.table,
                exc,
            )

        for row in rows:
            try:
                lookup = {field: row[field] for field in config.unique_fields}
                defaults = {k: v for k, v in row.items() if k not in lookup}
                if "id" in defaults and defaults["id"] in (None, ""):
                    defaults.pop("id")
                with transaction.atomic(using=self.db_alias):
                    model.objects.using(self.db_alias).update_or_create(**lookup, defaults=defaults)
            except Exception as exc:  # noqa: BLE001
                failed_rows += 1
                logger.warning(
                    "Auto_DB_Pro sync row upsert failed table=%s lookup=%s reason=%s",
                    config.table,
                    lookup,
                    exc,
                )

        return failed_rows

    def _deduplicate_rows(self, *, config: TableSyncConfig, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            key = tuple(row.get(field) for field in config.unique_fields)
            deduped[key] = row
        return list(deduped.values())

    def _filter_invalid_foreign_keys(self, *, table: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        if not rows:
            return rows, 0

        filtered = rows
        failed_rows = 0

        if table == "models":
            manufacturer_ids = {int(item) for item in AutoDbVehicleManufacturer.objects.using(self.db_alias).values_list("id", flat=True)}
            for row in filtered:
                manufacturer_id = row.get("vehicle_manufacturer_id")
                if manufacturer_id is not None and int(manufacturer_id) not in manufacturer_ids:
                    row["vehicle_manufacturer_id"] = None

        if table == "passanger_cars":
            model_ids = {int(item) for item in AutoDbVehicleModel.objects.using(self.db_alias).values_list("id", flat=True)}
            manufacturer_ids = {int(item) for item in AutoDbVehicleManufacturer.objects.using(self.db_alias).values_list("id", flat=True)}
            for row in filtered:
                model_id = row.get("model_id")
                if model_id is not None and int(model_id) not in model_ids:
                    row["model_id"] = None
                manufacturer_id = row.get("vehicle_manufacturer_id")
                if manufacturer_id is not None and int(manufacturer_id) not in manufacturer_ids:
                    row["vehicle_manufacturer_id"] = None

        if table == "passanger_car_engines":
            car_ids = {int(item) for item in AutoDbPassengerCar.objects.using(self.db_alias).values_list("id", flat=True)}
            valid_rows: list[dict[str, Any]] = []
            for row in filtered:
                car_id = row.get("passenger_car_id")
                if car_id is None or int(car_id) not in car_ids:
                    failed_rows += 1
                    logger.warning("Auto_DB_Pro sync skipped passanger_car_engines row due missing passenger car id=%s", car_id)
                    continue
                valid_rows.append(row)
            filtered = valid_rows

        if table == "passanger_car_attributes":
            car_ids = {int(item) for item in AutoDbPassengerCar.objects.using(self.db_alias).values_list("id", flat=True)}
            valid_rows = []
            for row in filtered:
                car_id = row.get("vehicle_id")
                if car_id is None or int(car_id) not in car_ids:
                    failed_rows += 1
                    logger.warning("Auto_DB_Pro sync skipped passanger_car_attributes row due missing passenger car id=%s", car_id)
                    continue
                valid_rows.append(row)
            filtered = valid_rows

        if table == "passanger_car_trees":
            car_ids = {int(item) for item in AutoDbPassengerCar.objects.using(self.db_alias).values_list("id", flat=True)}
            valid_rows = []
            for row in filtered:
                car_id = row.get("vehicle_id")
                if car_id is None or int(car_id) not in car_ids:
                    failed_rows += 1
                    logger.warning("Auto_DB_Pro sync skipped passanger_car_trees row due missing passenger car id=%s", car_id)
                    continue
                valid_rows.append(row)
            filtered = valid_rows

        return filtered, failed_rows

    def _load_or_create_state(self, table: str) -> AutoDbSyncState:
        state, _ = AutoDbSyncState.objects.using(self.db_alias).get_or_create(source_table=table)
        return state

    def _reset_state(self, state: AutoDbSyncState) -> None:
        state.status = AutoDbSyncState.Status.PENDING
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
        state.save(
            using=self.db_alias,
            update_fields=[
                "status",
                "last_pk",
                "last_offset",
                "last_cursor",
                "total_rows",
                "processed_rows",
                "failed_rows",
                "started_at",
                "finished_at",
                "last_error",
                "metadata",
                "updated_at",
            ],
        )
