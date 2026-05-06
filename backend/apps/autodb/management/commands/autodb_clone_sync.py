from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.clone_indexes import AutoDbCloneIndexService
from apps.autodb.services.clone_sync import AutoDbCloneSyncService
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready


class Command(BaseCommand):
    help = "Raw clone sync: remote Auto-DB Pro table -> local Auto_DB_Pro table with the same names and columns."

    def add_arguments(self, parser):
        parser.add_argument("--only", type=str, default="", help="Sync only one table name.")
        parser.add_argument("--vehicle-catalog", action="store_true", help="Sync only vehicle catalog table set.")
        parser.add_argument("--article-catalog", action="store_true", help="Sync only article catalog table set.")
        parser.add_argument("--ensure-indexes", action="store_true", help="Create technical indexes for raw clone vehicle catalog tables.")
        parser.add_argument("--batch-size", type=int, default=0, help="Batch size.")
        parser.add_argument("--limit", type=int, default=0, help="Limit rows per table.")
        parser.add_argument("--dry-run", action="store_true", help="Read source rows but do not write local DB.")
        parser.add_argument("--resume", action="store_true", help="Resume from previous sync state.")
        parser.add_argument("--force-recreate-table", action="store_true", help="Drop and recreate local clone table before sync.")
        parser.add_argument("--schema-only", action="store_true", help="Create/alter local clone schema only.")
        parser.add_argument("--data-only", action="store_true", help="Sync data only (assume schema exists).")
        parser.add_argument("--start-from-id", type=int, default=0, help="Start from numeric primary key value.")
        parser.add_argument("--progress-every-batches", type=int, default=0, help="Print progress every N processed batches.")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        ensure_indexes = bool(options.get("ensure_indexes"))

        if not bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False)):
            raise CommandError("Auto-DB Pro remote is disabled. Set AUTODB_PRO_REMOTE_ENABLED=true.")

        if bool(options.get("schema_only")) and bool(options.get("data_only")):
            raise CommandError("--schema-only and --data-only cannot be used together.")

        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds} "
                f"error={readiness.error_message or '-'}"
            )

        only = str(options.get("only") or "").strip() or None
        service = AutoDbCloneSyncService()
        tables = service.resolve_tables(
            only=only,
            vehicle_catalog=bool(options.get("vehicle_catalog")),
            article_catalog=bool(options.get("article_catalog")),
        )

        batch_size_opt = int(options.get("batch_size") or 0)
        batch_size = batch_size_opt if batch_size_opt > 0 else int(getattr(settings, "AUTODB_PRO_REMOTE_BATCH_SIZE", 100))
        limit_opt = int(options.get("limit") or 0)
        limit = limit_opt if limit_opt > 0 else None
        start_from_id_opt = int(options.get("start_from_id") or 0)
        start_from_id = start_from_id_opt if start_from_id_opt > 0 else None

        self.stdout.write(
            f"Auto_DB_Pro clone sync started tables={','.join(tables)} batch_size={batch_size} "
            f"resume={bool(options.get('resume'))} dry_run={bool(options.get('dry_run'))} "
            f"wait_for_autodb={wait_for_autodb}"
        )

        progress_every_batches = max(int(options.get("progress_every_batches") or 0), 0)
        results = service.sync(
            tables=tables,
            batch_size=batch_size,
            limit=limit,
            resume=bool(options.get("resume")),
            dry_run=bool(options.get("dry_run")),
            force_recreate_table=bool(options.get("force_recreate_table")),
            schema_only=bool(options.get("schema_only")),
            data_only=bool(options.get("data_only")),
            start_from_id=start_from_id,
            progress_every_batches=progress_every_batches,
            progress_callback=self._on_progress if progress_every_batches > 0 else None,
        )

        for result in results:
            self.stdout.write(
                f"[{result.table}] status={result.status} processed={result.processed_rows} "
                f"failed={result.failed_rows} total={result.total_rows}"
            )

        if ensure_indexes:
            index_service = AutoDbCloneIndexService()
            index_results = index_service.ensure_indexes(tables=tables)
            self.stdout.write("Auto_DB_Pro clone indexes:")
            for item in index_results:
                column_label = ",".join(item.columns)
                suffix = f" ({item.message})" if item.message else ""
                self.stdout.write(f"- {item.table}.{column_label}: {item.status} [{item.index_name}]{suffix}")

        failed_statuses = {"failed", "permission_denied", "paused"}
        failed_tables = [item.table for item in results if item.status in failed_statuses]
        if failed_tables:
            raise CommandError(
                "Auto_DB_Pro clone sync failed for table(s): "
                + ", ".join(failed_tables)
            )

        self.stdout.write(self.style.SUCCESS("Auto_DB_Pro clone sync finished"))

    def _on_progress(
        self,
        *,
        table: str,
        batch_no: int,
        processed_rows: int,
        failed_rows: int,
        total_rows: int,
        last_cursor: str,
    ) -> None:
        self.stdout.write(
            f"[{table}] progress batch={batch_no} processed={processed_rows} "
            f"failed={failed_rows} total={total_rows} cursor={last_cursor}"
        )
