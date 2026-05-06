from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.autodb.management.commands.autodb_check import CheckResult, Command, SyncStateSnapshot
from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.remote_config import AutoDbRemoteConfigSnapshot
from apps.autodb.services.clone_indexes import IndexEnsureResult


@override_settings(AUTODB_PRO_REMOTE_ENABLED=False)
class AutoDbCheckCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_check.Command._collect_selector_smoke", return_value=["manufacturers: ok"])
    @patch("apps.autodb.management.commands.autodb_check.Command._collect_index_status", return_value=[])
    @patch(
        "apps.autodb.management.commands.autodb_check.Command._collect_sync_states",
        return_value=[
            SyncStateSnapshot(
                table="manufacturers",
                status="no_state",
                processed_rows=0,
                failed_rows=0,
                total_rows=0,
                last_cursor="-",
                last_pk=None,
                last_offset=0,
            )
        ],
    )
    @patch("apps.autodb.management.commands.autodb_check.Command._collect_raw_counts", return_value={"manufacturers": 0})
    @patch("apps.autodb.management.commands.autodb_check.Command._check_django_connection", return_value=CheckResult(ok=True))
    @patch("apps.autodb.management.commands.autodb_check.AutoDbProRemoteClient.from_settings")
    def test_remote_disabled_does_not_fail(self, remote_factory, _check_db, _collect_counts, _collect_states, _collect_indexes, _selector_smoke):
        out = StringIO()
        call_command("autodb_check", stdout=out)

        output = out.getvalue()
        self.assertIn("default DB: OK", output)
        self.assertIn("local Auto_DB_Pro DB: OK", output)
        self.assertIn("remote Auto-DB Pro: OK (disabled)", output)
        remote_factory.assert_not_called()

    @patch(
        "apps.autodb.management.commands.autodb_check.Command._collect_index_status",
        return_value=[
            IndexEnsureResult(
                table="manufacturers",
                columns=("id",),
                index_name="ix_autodb_clone_manufacturers_id",
                status="present",
            )
        ],
    )
    @patch("apps.autodb.management.commands.autodb_check.Command._collect_selector_smoke", return_value=["manufacturers: ok"])
    @patch(
        "apps.autodb.management.commands.autodb_check.Command._collect_sync_states",
        return_value=[
            SyncStateSnapshot(
                table="country_groups",
                status="permission_denied",
                processed_rows=0,
                failed_rows=0,
                total_rows=0,
                last_cursor="-",
                last_pk=None,
                last_offset=0,
            )
        ],
    )
    @patch("apps.autodb.management.commands.autodb_check.Command._collect_raw_counts", return_value={"country_groups": -1})
    @patch("apps.autodb.management.commands.autodb_check.Command._check_django_connection", return_value=CheckResult(ok=True))
    def test_output_includes_permission_denied_and_index_status(self, _check_db, _collect_counts, _collect_states, _collect_indexes, _selector_smoke):
        out = StringIO()
        call_command("autodb_check", stdout=out)

        output = out.getvalue()
        self.assertIn("permission_denied tables: country_groups", output)
        self.assertIn("ix_autodb_clone_manufacturers_id", output)

    @patch("apps.autodb.management.commands.autodb_check.list_vehicle_manufacturers", return_value=[])
    def test_selector_smoke_warns_on_empty_data(self, manufacturers_mock):
        lines = Command()._collect_selector_smoke()

        self.assertEqual(lines, ["manufacturers: warning (empty result)"])
        manufacturers_mock.assert_called_once()

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="db.auto-db.pro",
        AUTODB_PRO_REMOTE_PORT=3306,
        AUTODB_PRO_REMOTE_DATABASE="db",
        AUTODB_PRO_REMOTE_USER="vs",
        AUTODB_PRO_REMOTE_PASSWORD="secret-password",
    )
    @patch("apps.autodb.management.commands.autodb_check.AutoDbRemoteConfigValidator.snapshot")
    def test_remote_config_warns_for_os_user_fallback_risk(self, snapshot_mock):
        snapshot_mock.return_value = AutoDbRemoteConfigSnapshot(
            enabled=True,
            host="db.auto-db.pro",
            port=3306,
            database="db",
            user="vs",
            password="secret-password",
            connect_timeout=10,
            read_timeout=30,
            batch_size=100,
        )
        out = StringIO()
        with (
            patch("apps.autodb.management.commands.autodb_check.Command._check_django_connection", return_value=CheckResult(ok=True)),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_raw_counts", return_value={}),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_sync_states", return_value=[]),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_index_status", return_value=[]),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_selector_smoke", return_value=[]),
            patch("apps.autodb.management.commands.autodb_check.AutoDbProRemoteClient.from_settings") as remote_factory,
        ):
            remote_factory.side_effect = RuntimeError("auth failed for secret-password for user 'vs'")
            call_command("autodb_check", stdout=out)

        output = out.getvalue()
        self.assertIn("warning: Remote Auto-DB Pro user looks like local OS user", output)
        self.assertIn("password_set: yes", output)
        self.assertNotIn("secret-password", output)

    @patch("apps.autodb.management.commands.autodb_check.AutoDbRemoteConfigValidator.snapshot")
    def test_uses_shared_remote_config_validator(self, snapshot_mock):
        snapshot_mock.return_value = AutoDbRemoteConfigSnapshot(
            enabled=False,
            host="",
            port=3306,
            database="",
            user="",
            password="",
            connect_timeout=10,
            read_timeout=30,
            batch_size=100,
        )
        out = StringIO()
        with (
            patch("apps.autodb.management.commands.autodb_check.Command._check_django_connection", return_value=CheckResult(ok=True)),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_raw_counts", return_value={}),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_sync_states", return_value=[]),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_index_status", return_value=[]),
            patch("apps.autodb.management.commands.autodb_check.Command._collect_selector_smoke", return_value=[]),
        ):
            call_command("autodb_check", stdout=out)

        self.assertGreaterEqual(snapshot_mock.call_count, 1)

    @patch("apps.autodb.management.commands.autodb_check.check_local_autodb_ready")
    def test_local_db_recovery_is_reported_clearly(self, ready_mock):
        ready_mock.return_value = LocalAutoDbReadinessResult(
            ready=False,
            reason="db_starting_or_recovering",
            error_message="the database system is not yet accepting connections",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        )
        result = Command()._check_django_connection("auto_db_pro")

        self.assertFalse(result.ok)
        self.assertIn("starting/recovering", result.message)
        self.assertIn("127.0.0.1", result.message)
