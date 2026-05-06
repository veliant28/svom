from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.autodb.services.remote_client import AutoDbProRemoteClient, AutoDbProRemoteClientError


@override_settings(
    AUTODB_PRO_REMOTE_HOST="db.auto-db.pro",
    AUTODB_PRO_REMOTE_PORT=3306,
    AUTODB_PRO_REMOTE_DATABASE="db",
    AUTODB_PRO_REMOTE_USER="user",
    AUTODB_PRO_REMOTE_PASSWORD="secret-password",
    AUTODB_PRO_REMOTE_CONNECT_TIMEOUT=10,
    AUTODB_PRO_REMOTE_READ_TIMEOUT=30,
)
class AutoDbProRemoteClientTests(SimpleTestCase):
    @patch("apps.autodb.services.remote_client.mysql.connector.connect")
    def test_error_does_not_expose_password(self, connect_mock):
        connect_mock.side_effect = RuntimeError("auth failed for secret-password")
        client = AutoDbProRemoteClient.from_settings()

        with self.assertRaises(AutoDbProRemoteClientError) as exc_ctx:
            client.select("SELECT 1")

        message = str(exc_ctx.exception)
        self.assertNotIn("secret-password", message)
        self.assertIn("***", message)

    def test_non_select_query_is_rejected(self):
        client = AutoDbProRemoteClient.from_settings()
        with self.assertRaises(AutoDbProRemoteClientError):
            client.select("DELETE FROM articles")

    def test_non_whitelisted_table_is_rejected(self):
        client = AutoDbProRemoteClient.from_settings()
        with self.assertRaises(AutoDbProRemoteClientError):
            client.count_table("totally_unknown_table")

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="db.auto-db.pro",
        AUTODB_PRO_REMOTE_PORT=3306,
        AUTODB_PRO_REMOTE_DATABASE="db",
        AUTODB_PRO_REMOTE_USER="",
        AUTODB_PRO_REMOTE_PASSWORD="secret-password",
    )
    def test_enabled_remote_without_user_fails_fast(self):
        with self.assertRaises(AutoDbProRemoteClientError) as exc_ctx:
            AutoDbProRemoteClient.from_settings()
        self.assertIn("AUTODB_PRO_REMOTE_USER", str(exc_ctx.exception))

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="db.auto-db.pro",
        AUTODB_PRO_REMOTE_PORT=3306,
        AUTODB_PRO_REMOTE_DATABASE="db",
        AUTODB_PRO_REMOTE_USER="user",
        AUTODB_PRO_REMOTE_PASSWORD="",
    )
    def test_enabled_remote_without_password_fails_fast(self):
        with self.assertRaises(AutoDbProRemoteClientError) as exc_ctx:
            AutoDbProRemoteClient.from_settings()
        self.assertIn("AUTODB_PRO_REMOTE_PASSWORD", str(exc_ctx.exception))
