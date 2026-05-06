from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import (
    LocalAutoDbReadinessResult,
    check_local_autodb_ready,
    wait_for_local_autodb_ready,
)


class _OkCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query):
        return None

    def fetchone(self):
        return (1,)


class _FailCursor:
    def __init__(self, message: str):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query):
        raise RuntimeError(self.message)

    def fetchone(self):
        return None


class _Conn:
    def __init__(self, cursor_obj):
        self._cursor_obj = cursor_obj
        self.settings_dict = {"HOST": "127.0.0.1", "PORT": "5434", "NAME": "Auto_DB_Pro", "PASSWORD": ""}

    def cursor(self):
        return self._cursor_obj


class LocalAutoDbReadinessTests(SimpleTestCase):
    @patch("apps.autodb.services.local_db_readiness.connections", {"auto_db_pro": _Conn(_OkCursor())})
    def test_detects_ready_local_db(self):
        result = check_local_autodb_ready()

        self.assertTrue(result.ready)
        self.assertEqual(result.reason, "ready")
        self.assertEqual(result.host, "127.0.0.1")
        self.assertEqual(result.port, "5434")
        self.assertEqual(result.database, "Auto_DB_Pro")

    @patch(
        "apps.autodb.services.local_db_readiness.connections",
        {"auto_db_pro": _Conn(_FailCursor("FATAL: the database system is not yet accepting connections"))},
    )
    def test_handles_recovery_not_accepting_connections(self):
        result = check_local_autodb_ready()

        self.assertFalse(result.ready)
        self.assertEqual(result.reason, "db_starting_or_recovering")
        self.assertIn("not yet accepting connections", result.error_message.lower())

    @patch("apps.autodb.services.local_db_readiness.time.sleep")
    @patch("apps.autodb.services.local_db_readiness._check_local_autodb_ready")
    def test_wait_retries_until_ready(self, check_mock, _sleep_mock):
        check_mock.side_effect = [
            LocalAutoDbReadinessResult(
                ready=False,
                reason="db_starting_or_recovering",
                error_message="starting",
                host="127.0.0.1",
                port="5434",
                database="Auto_DB_Pro",
                attempts=1,
                waited_seconds=0.0,
            ),
            LocalAutoDbReadinessResult(
                ready=True,
                reason="ready",
                error_message="",
                host="127.0.0.1",
                port="5434",
                database="Auto_DB_Pro",
                attempts=2,
                waited_seconds=0.1,
            ),
        ]

        result = wait_for_local_autodb_ready(timeout_seconds=60, interval_seconds=0.1)

        self.assertTrue(result.ready)
        self.assertGreaterEqual(result.attempts, 2)
