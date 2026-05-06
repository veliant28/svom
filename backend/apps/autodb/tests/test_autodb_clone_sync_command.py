from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.clone_indexes import IndexEnsureResult
from apps.autodb.services.clone_sync import CloneTableResult


class AutoDbCloneSyncCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_clone_sync.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_BATCH_SIZE=250,
        AUTODB_PRO_REMOTE_HOST="remote.example",
        AUTODB_PRO_REMOTE_DATABASE="autodb",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    @patch("apps.autodb.management.commands.autodb_clone_sync.AutoDbCloneSyncService.sync")
    @patch("apps.autodb.management.commands.autodb_clone_sync.AutoDbCloneSyncService.resolve_tables")
    def test_only_and_limit_arguments(self, resolve_mock, sync_mock, _ready_mock):
        resolve_mock.return_value = ["manufacturers"]
        sync_mock.return_value = [CloneTableResult(table="manufacturers", status="completed", total_rows=3, processed_rows=3, failed_rows=0)]
        out = StringIO()

        call_command("autodb_clone_sync", "--only", "manufacturers", "--limit", "100", stdout=out)

        sync_mock.assert_called_once_with(
            tables=["manufacturers"],
            batch_size=250,
            limit=100,
            resume=False,
            dry_run=False,
            force_recreate_table=False,
            schema_only=False,
            data_only=False,
            start_from_id=None,
            progress_every_batches=0,
            progress_callback=None,
        )

    @patch(
        "apps.autodb.management.commands.autodb_clone_sync.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_BATCH_SIZE=200,
        AUTODB_PRO_REMOTE_HOST="remote.example",
        AUTODB_PRO_REMOTE_DATABASE="autodb",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    @patch("apps.autodb.management.commands.autodb_clone_sync.AutoDbCloneIndexService.ensure_indexes")
    @patch("apps.autodb.management.commands.autodb_clone_sync.AutoDbCloneSyncService.sync")
    @patch("apps.autodb.management.commands.autodb_clone_sync.AutoDbCloneSyncService.resolve_tables")
    def test_ensure_indexes_option_runs_index_service(self, resolve_mock, sync_mock, ensure_indexes_mock, _ready_mock):
        resolve_mock.return_value = ["manufacturers"]
        sync_mock.return_value = [CloneTableResult(table="manufacturers", status="completed", total_rows=1, processed_rows=1, failed_rows=0)]
        ensure_indexes_mock.return_value = [
            IndexEnsureResult(
                table="manufacturers",
                columns=("id",),
                index_name="ix_autodb_clone_manufacturers_id",
                status="created",
            )
        ]
        out = StringIO()

        call_command("autodb_clone_sync", "--ensure-indexes", stdout=out)

        ensure_indexes_mock.assert_called_once_with(tables=["manufacturers"])
        self.assertIn("clone indexes", out.getvalue().lower())
