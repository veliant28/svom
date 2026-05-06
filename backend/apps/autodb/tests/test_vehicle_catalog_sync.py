from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.models import AutoDbSyncState
from apps.autodb.services.vehicle_catalog_sync import AutoDbVehicleCatalogSyncService


class AutoDbVehicleCatalogSyncServiceTests(SimpleTestCase):
    def test_dry_run_does_not_write_state(self):
        remote_client = Mock()
        remote_client.resolve_pk_column.return_value = "id"
        remote_client.count_table.return_value = 1
        remote_client.fetch_batch.side_effect = [[{"id": 1, "description": "BMW"}], []]

        service = AutoDbVehicleCatalogSyncService(remote_client=remote_client)

        with patch.object(service, "_load_or_create_state") as state_loader, patch.object(service, "_upsert_batch", return_value=0) as upsert:
            result = service.sync(
                only="manufacturers",
                batch_size=100,
                resume=False,
                force=False,
                dry_run=True,
                limit=None,
                start_from_id=None,
            )

        state_loader.assert_not_called()
        upsert.assert_not_called()
        self.assertEqual(result.results[0].processed_rows, 1)
        self.assertEqual(result.results[0].status, "dry_run")

    def test_repeated_sync_uses_upsert(self):
        remote_client = Mock()
        remote_client.resolve_pk_column.return_value = "id"
        remote_client.count_table.return_value = 1
        remote_client.fetch_batch.side_effect = [[{"id": 1, "description": "BMW"}], [], [{"id": 1, "description": "BMW"}], []]

        service = AutoDbVehicleCatalogSyncService(remote_client=remote_client)
        fake_state = SimpleNamespace(
            source_table="manufacturers",
            status="",
            started_at=None,
            finished_at=None,
            total_rows=0,
            processed_rows=0,
            failed_rows=0,
            last_pk=None,
            last_offset=0,
            last_cursor="",
            metadata={},
            last_error="",
            save=Mock(),
        )

        with patch.object(service, "_load_or_create_state", return_value=fake_state), patch.object(
            service, "_upsert_batch", return_value=0
        ) as upsert:
            service.sync(
                only="manufacturers",
                batch_size=100,
                resume=False,
                force=False,
                dry_run=False,
                limit=None,
                start_from_id=None,
            )
            service.sync(
                only="manufacturers",
                batch_size=100,
                resume=False,
                force=False,
                dry_run=False,
                limit=None,
                start_from_id=None,
            )

        self.assertEqual(upsert.call_count, 2)

    def test_sync_state_is_updated(self):
        remote_client = Mock()
        remote_client.resolve_pk_column.return_value = "id"
        remote_client.count_table.return_value = 1
        remote_client.fetch_batch.side_effect = [[{"id": 1, "description": "BMW"}], []]

        service = AutoDbVehicleCatalogSyncService(remote_client=remote_client)
        fake_state = SimpleNamespace(
            source_table="manufacturers",
            status="",
            started_at=None,
            finished_at=None,
            total_rows=0,
            processed_rows=0,
            failed_rows=0,
            last_pk=None,
            last_offset=0,
            last_cursor="",
            metadata={},
            last_error="",
            save=Mock(),
        )

        with patch.object(service, "_load_or_create_state", return_value=fake_state), patch.object(service, "_upsert_batch", return_value=0):
            result = service.sync(
                only="manufacturers",
                batch_size=100,
                resume=False,
                force=False,
                dry_run=False,
                limit=None,
                start_from_id=None,
            )

        self.assertEqual(result.results[0].processed_rows, 1)
        self.assertEqual(fake_state.status, AutoDbSyncState.Status.COMPLETED)
        self.assertEqual(fake_state.processed_rows, 1)
        self.assertEqual(fake_state.failed_rows, 0)
        self.assertGreaterEqual(fake_state.save.call_count, 2)

    def test_failed_row_does_not_stop_batch(self):
        remote_client = Mock()
        remote_client.resolve_pk_column.return_value = "id"
        remote_client.count_table.return_value = 2
        remote_client.fetch_batch.side_effect = [[{"id": None, "description": "bad"}, {"id": 2, "description": "good"}], []]

        service = AutoDbVehicleCatalogSyncService(remote_client=remote_client)

        with patch.object(service, "_upsert_batch", return_value=0) as upsert:
            result = service.sync(
                only="manufacturers",
                batch_size=100,
                resume=False,
                force=False,
                dry_run=True,
                limit=None,
                start_from_id=None,
            )

        upsert.assert_not_called()
        self.assertEqual(result.results[0].processed_rows, 2)
        self.assertEqual(result.results[0].failed_rows, 1)
