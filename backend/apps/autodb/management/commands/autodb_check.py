from __future__ import annotations

from dataclasses import dataclass
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from apps.autodb.models import AutoDbSyncState
from apps.autodb.selectors import list_passanger_cars, list_vehicle_manufacturers, list_vehicle_models
from apps.autodb.services.clone_indexes import AutoDbCloneIndexService
from apps.autodb.services.local_db_readiness import check_local_autodb_ready
from apps.autodb.services.remote_config import AutoDbRemoteConfigSnapshot, AutoDbRemoteConfigValidator
from apps.autodb.services.remote_client import AutoDbProRemoteClient, AutoDbProRemoteClientError


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    message: str = ""


@dataclass(frozen=True)
class SyncStateSnapshot:
    table: str
    status: str
    processed_rows: int
    failed_rows: int
    total_rows: int
    last_cursor: str
    last_pk: int | None
    last_offset: int


class Command(BaseCommand):
    help = "Checks default DB, local Auto_DB_Pro DB, remote Auto-DB Pro, raw clone counts and sync states."

    VEHICLE_RAW_CLONE_TABLES = (
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
    ARTICLE_RAW_CLONE_TABLES = (
        "suppliers",
        "supplier_details",
        "articles",
        "article_numbers",
        "article_attributes",
        "article_images",
        "article_inf",
        "article_li",
        "article_links",
        "article_prd",
        "article_oe",
        "article_cross",
        "article_ean",
        "article_nn",
        "article_m",
        "article_acc",
        "article_parts",
    )

    def handle(self, *args, **options):
        remote_snapshot = AutoDbRemoteConfigValidator.snapshot()
        default_result = self._check_django_connection("default")
        local_result = self._check_django_connection("auto_db_pro")
        remote_result = self._check_remote()

        self.stdout.write("remote Auto-DB Pro config:")
        self.stdout.write(f"- enabled: {'true' if remote_snapshot.enabled else 'false'}")
        self.stdout.write(f"- host: {remote_snapshot.host or '-'}")
        self.stdout.write(f"- port: {remote_snapshot.port}")
        self.stdout.write(f"- database: {remote_snapshot.database or '-'}")
        self.stdout.write(f"- user: {remote_snapshot.user or '-'}")
        self.stdout.write(f"- password_set: {'yes' if remote_snapshot.password_set else 'no'}")
        self.stdout.write(f"- connect_timeout: {remote_snapshot.connect_timeout}")
        self.stdout.write(f"- read_timeout: {remote_snapshot.read_timeout}")
        for warning in self._collect_remote_config_warnings(remote_snapshot):
            self.stdout.write(f"- warning: {warning}")

        self.stdout.write(self._fmt_result("default DB", default_result))
        self.stdout.write(self._fmt_result("local Auto_DB_Pro DB", local_result))
        self.stdout.write(self._fmt_result("remote Auto-DB Pro", remote_result))

        if local_result.ok:
            self.stdout.write("Auto_DB_Pro raw clone table counts:")
            for label, count in self._collect_raw_counts(self.VEHICLE_RAW_CLONE_TABLES).items():
                self.stdout.write(f"- {label}: {count}")
            self.stdout.write("Auto_DB_Pro article raw clone table counts:")
            for label, count in self._collect_raw_counts(self.ARTICLE_RAW_CLONE_TABLES).items():
                self.stdout.write(f"- {label}: {count}")

            self.stdout.write("Auto_DB_Pro sync states:")
            states = self._collect_sync_states()
            permission_denied_tables: list[str] = []
            for snapshot in states:
                self.stdout.write(
                    f"- {snapshot.table}: status={snapshot.status} processed={snapshot.processed_rows} "
                    f"failed={snapshot.failed_rows} total={snapshot.total_rows} "
                    f"last_cursor={snapshot.last_cursor} last_pk={snapshot.last_pk or '-'} "
                    f"last_offset={snapshot.last_offset}"
                )
                if snapshot.status == "permission_denied":
                    permission_denied_tables.append(snapshot.table)

            denied_label = ",".join(permission_denied_tables) if permission_denied_tables else "-"
            self.stdout.write(f"Auto_DB_Pro permission_denied tables: {denied_label}")

            self.stdout.write("Auto_DB_Pro clone indexes:")
            for index_status in self._collect_index_status():
                columns = ",".join(index_status.columns)
                suffix = f" ({index_status.message})" if index_status.message else ""
                self.stdout.write(
                    f"- {index_status.table}.{columns}: {index_status.status} "
                    f"[{index_status.index_name}]{suffix}"
                )

            self.stdout.write("Auto_DB_Pro selector smoke:")
            for line in self._collect_selector_smoke():
                self.stdout.write(f"- {line}")

    def _fmt_result(self, label: str, result: CheckResult) -> str:
        status = "OK" if result.ok else "FAIL"
        suffix = f" ({result.message})" if result.message else ""
        return f"{label}: {status}{suffix}"

    def _check_django_connection(self, alias: str) -> CheckResult:
        if alias == "auto_db_pro":
            readiness = check_local_autodb_ready()
            if readiness.ready:
                return CheckResult(ok=True)

            prefix = "local Auto_DB_Pro DB is starting/recovering, retry later"
            if readiness.reason not in {"db_starting_or_recovering", "connection_refused", "connection_unavailable"}:
                prefix = "local Auto_DB_Pro DB is unavailable"
            detail = (
                f"{prefix}; host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason}"
            )
            if readiness.error_message:
                detail = f"{detail}; error={readiness.error_message}"
            return CheckResult(ok=False, message=detail)
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return CheckResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            return CheckResult(ok=False, message=self._sanitize_message(str(exc)))

    def _check_remote(self) -> CheckResult:
        snapshot = AutoDbRemoteConfigValidator.snapshot()
        if not snapshot.enabled:
            return CheckResult(ok=True, message="disabled")
        errors = snapshot.validation_errors(require_enabled=False)
        if errors:
            return CheckResult(
                ok=False,
                message=self._sanitize_remote_message(
                    "Remote Auto-DB Pro is enabled but config is invalid: " + "; ".join(errors)
                ),
            )

        try:
            client = AutoDbProRemoteClient.from_settings()
            ok = client.check_connection()
            return CheckResult(ok=ok, message="SELECT 1" if ok else "unexpected response")
        except AutoDbProRemoteClientError as exc:
            return CheckResult(ok=False, message=self._sanitize_remote_message(str(exc)))
        except Exception as exc:  # noqa: BLE001
            return CheckResult(ok=False, message=self._sanitize_remote_message(str(exc)))

    def _collect_raw_counts(self, tables: tuple[str, ...]) -> dict[str, int]:
        counts: dict[str, int] = {}
        with connections["auto_db_pro"].cursor() as cursor:
            for table in tables:
                if not self._table_exists(cursor, table):
                    counts[table] = -1
                    continue
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                row = cursor.fetchone()
                counts[table] = int(row[0]) if row else 0
        return counts

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

    def _collect_sync_states(self) -> list[SyncStateSnapshot]:
        snapshots: list[SyncStateSnapshot] = []
        for table in self.VEHICLE_RAW_CLONE_TABLES:
            state = (
                AutoDbSyncState.objects.using("auto_db_pro")
                .filter(source_table=table)
                .order_by("-updated_at")
                .first()
            )
            if not state:
                snapshots.append(
                    SyncStateSnapshot(
                        table=table,
                        status="no_state",
                        processed_rows=0,
                        failed_rows=0,
                        total_rows=0,
                        last_cursor="-",
                        last_pk=None,
                        last_offset=0,
                    )
                )
                continue

            snapshots.append(
                SyncStateSnapshot(
                    table=table,
                    status=str(state.status),
                    processed_rows=int(state.processed_rows or 0),
                    failed_rows=int(state.failed_rows or 0),
                    total_rows=int(state.total_rows or 0),
                    last_cursor=str(state.last_cursor or "-"),
                    last_pk=state.last_pk,
                    last_offset=int(state.last_offset or 0),
                )
            )
        return snapshots

    def _collect_index_status(self):
        return AutoDbCloneIndexService().collect_vehicle_catalog_index_status(tables=list(self.VEHICLE_RAW_CLONE_TABLES))

    def _collect_selector_smoke(self) -> list[str]:
        lines: list[str] = []
        try:
            manufacturers = list_vehicle_manufacturers()
            if not manufacturers:
                lines.append("manufacturers: warning (empty result)")
                return lines
            lines.append(f"manufacturers: ok ({min(len(manufacturers), 5)} sampled)")

            manufacturer_id = manufacturers[0].get("id")
            models = list_vehicle_models(manufacturer_id=manufacturer_id)
            if not models:
                lines.append(f"models: warning (empty for manufacturer_id={manufacturer_id})")
                return lines
            lines.append(f"models: ok ({min(len(models), 5)} sampled for manufacturer_id={manufacturer_id})")

            model_id = models[0].get("id")
            passanger_cars = list_passanger_cars(model_id=model_id)
            if not passanger_cars:
                lines.append(f"passanger_cars: warning (empty for model_id={model_id})")
                return lines
            lines.append(f"passanger_cars: ok ({min(len(passanger_cars), 5)} sampled for model_id={model_id})")
            return lines
        except Exception as exc:  # noqa: BLE001
            lines.append(f"warning ({self._sanitize_message(str(exc))})")
            return lines

    def _sanitize_message(self, message: str) -> str:
        password = str(getattr(settings, "AUTODB_PRO_REMOTE_PASSWORD", "") or "")
        if password:
            message = message.replace(password, "***")
        return message

    def _collect_remote_config_warnings(self, snapshot: AutoDbRemoteConfigSnapshot) -> list[str]:
        warnings: list[str] = []
        if not snapshot.enabled:
            return warnings
        for error in snapshot.validation_errors(require_enabled=False):
            warnings.append(error + ".")
        if snapshot.os_user_fallback_risk():
            warnings.append("Remote Auto-DB Pro user looks like local OS user; env may not be loaded.")
        return warnings

    def _sanitize_remote_message(self, message: str) -> str:
        sanitized = self._sanitize_message(message)
        match = re.search(r"for user '([^']+)'", sanitized)
        if match:
            attempted_user = match.group(1).strip()
            if attempted_user:
                sanitized += f" (attempted_user={attempted_user})"
        return sanitized
