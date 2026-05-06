from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.services.clone_sync import AutoDbCloneSyncService, CloneTableResult
from apps.autodb.services.remote_client import AutoDbProRemoteClientError


class AutoDbCloneSyncServiceTests(SimpleTestCase):
    def test_resolve_tables_vehicle_default(self):
        service = AutoDbCloneSyncService(remote_client=Mock(), schema_service=Mock())
        tables = service.resolve_tables(only=None, vehicle_catalog=False, article_catalog=False)
        self.assertIn("manufacturers", tables)

    def test_resolve_tables_only(self):
        service = AutoDbCloneSyncService(remote_client=Mock(), schema_service=Mock())
        self.assertEqual(service.resolve_tables(only="models", vehicle_catalog=True, article_catalog=True), ["models"])

    def test_permission_denied_does_not_break_multi_table_sync(self):
        service = AutoDbCloneSyncService(remote_client=Mock(), schema_service=Mock())

        with patch.object(service, "_sync_table", side_effect=[AutoDbProRemoteClientError("SELECT command denied"), CloneTableResult("models", "completed", 1, 1, 0)]), patch.object(
            service, "_mark_state"
        ):
            results = service.sync(
                tables=["country_groups", "models"],
                batch_size=100,
                limit=None,
                resume=False,
                dry_run=False,
                force_recreate_table=False,
                schema_only=False,
                data_only=False,
                start_from_id=None,
            )

        self.assertEqual(results[0].status, "permission_denied")
        self.assertEqual(results[1].status, "completed")

    def test_resume_uses_saved_cursor_and_accumulates_processed_rows(self):
        remote_client = Mock()
        schema_service = Mock()
        service = AutoDbCloneSyncService(remote_client=remote_client, schema_service=schema_service)

        id_column = Mock()
        id_column.name = "id"
        id_column.data_type = "int"
        info = Mock()
        info.primary_key_columns = ["id"]
        info.unique_keys = [["id"]]
        info.columns = [id_column]
        schema_service.introspect_table.return_value = info

        state = Mock()
        state.last_pk = 100
        state.last_offset = 0
        state.processed_rows = 100
        state.failed_rows = 0
        state.status = "running"

        remote_client.count_table.return_value = 102
        remote_client.fetch_batch_keyset.side_effect = [
            [{"id": 101}, {"id": 102}],
            [],
        ]

        progress_callback = Mock()
        with (
            patch.object(service, "_get_or_create_state", return_value=state),
            patch.object(service, "_mark_state"),
            patch.object(service, "_upsert_rows", return_value=0),
        ):
            result = service._sync_table(
                table="passanger_car_trees",
                batch_size=100,
                limit=None,
                resume=True,
                dry_run=False,
                force_recreate_table=False,
                schema_only=False,
                data_only=True,
                start_from_id=None,
                progress_every_batches=1,
                progress_callback=progress_callback,
            )

        first_fetch_call = remote_client.fetch_batch_keyset.call_args_list[0]
        self.assertEqual(first_fetch_call.kwargs["cursor_columns"], ("id", "passangercarid", "searchtreeid"))
        self.assertEqual(result.processed_rows, 102)
        progress_callback.assert_called_once()
