from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import TestCase

from apps.autodb.models import AutoDbSyncState
from apps.autodb.services.clone_runtime_status import _resolve_active_sync_pid, get_passanger_car_trees_runtime_status


class CloneRuntimeStatusTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def test_running_state_without_process_is_reconciled_to_paused(self):
        AutoDbSyncState.objects.using("auto_db_pro").create(
            source_table="passanger_car_trees",
            status=AutoDbSyncState.Status.RUNNING,
            processed_rows=13870000,
            total_rows=14983071,
            failed_rows=0,
            last_cursor="keyset:[102811,17994,1]",
        )

        with (
            patch("apps.autodb.services.clone_runtime_status._resolve_active_sync_pid", return_value=None),
            patch("apps.autodb.services.clone_runtime_status._count_table_rows", return_value=13880539),
        ):
            result = get_passanger_car_trees_runtime_status(reconcile=True)

        self.assertEqual(result.actual_status, "paused")
        self.assertTrue(result.reconciled)
        state = AutoDbSyncState.objects.using("auto_db_pro").get(source_table="passanger_car_trees")
        self.assertEqual(state.status, AutoDbSyncState.Status.PAUSED)

    def test_running_state_with_completed_counts_is_reconciled_to_completed(self):
        AutoDbSyncState.objects.using("auto_db_pro").create(
            source_table="passanger_car_trees",
            status=AutoDbSyncState.Status.RUNNING,
            processed_rows=100,
            total_rows=100,
            failed_rows=0,
            last_cursor="keyset:[1,2,3]",
        )

        with (
            patch("apps.autodb.services.clone_runtime_status._resolve_active_sync_pid", return_value=None),
            patch("apps.autodb.services.clone_runtime_status._count_table_rows", return_value=100),
        ):
            result = get_passanger_car_trees_runtime_status(reconcile=True)

        self.assertEqual(result.actual_status, "completed")
        self.assertTrue(result.reconciled)
        state = AutoDbSyncState.objects.using("auto_db_pro").get(source_table="passanger_car_trees")
        self.assertEqual(state.status, AutoDbSyncState.Status.COMPLETED)

    def test_runtime_pid_falls_back_to_wrapper_process_lookup(self):
        manage_py_missing = Mock(returncode=1, stdout="")
        wrapper_running = Mock(returncode=0, stdout="47591\n")
        with (
            patch("apps.autodb.services.clone_runtime_status._read_pid_file", return_value=None),
            patch("apps.autodb.services.clone_runtime_status._pid_exists", return_value=True),
            patch("apps.autodb.services.clone_runtime_status.subprocess.run", side_effect=[manage_py_missing, wrapper_running]),
        ):
            pid = _resolve_active_sync_pid()

        self.assertEqual(pid, 47591)
