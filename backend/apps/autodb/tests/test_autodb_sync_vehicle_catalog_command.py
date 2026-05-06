from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class AutoDbSyncVehicleCatalogCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_sync_vehicle_catalog.call_command")
    def test_wrapper_forwards_arguments(self, clone_call_mock):
        out = StringIO()

        call_command(
            "autodb_sync_vehicle_catalog",
            "--only",
            "manufacturers",
            "--limit",
            "100",
            "--batch-size",
            "250",
            "--resume",
            "--force",
            "--dry-run",
            "--start-from-id",
            "10",
            stdout=out,
        )

        clone_call_mock.assert_called_once_with(
            "autodb_clone_sync",
            vehicle_catalog=True,
            resume=True,
            dry_run=True,
            force_recreate_table=True,
            only="manufacturers",
            batch_size=250,
            limit=100,
            start_from_id=10,
        )
        self.assertIn("deprecated", out.getvalue().lower())
