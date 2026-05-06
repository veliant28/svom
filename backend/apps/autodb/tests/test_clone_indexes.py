from unittest.mock import patch

from django.test import SimpleTestCase

from apps.autodb.services.clone_indexes import AutoDbCloneIndexService, IndexTarget


class _FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple | list | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((str(sql), params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class AutoDbCloneIndexServiceTests(SimpleTestCase):
    def test_ensure_indexes_creates_only_when_columns_exist(self):
        cursor = _FakeCursor()
        service = AutoDbCloneIndexService()
        service.VEHICLE_INDEX_TARGETS = (
            IndexTarget("manufacturers", ("id",)),
            IndexTarget("manufacturers", ("missing_col",)),
        )

        with (
            patch("apps.autodb.services.clone_indexes.connections", {"auto_db_pro": _FakeConnection(cursor)}),
            patch.object(service, "_table_exists", return_value=True),
            patch.object(service, "_index_exists", return_value=False),
            patch.object(service, "_get_local_columns", return_value={"id"}),
        ):
            results = service.ensure_vehicle_catalog_indexes(tables=["manufacturers"])

        self.assertEqual(results[0].status, "created")
        self.assertEqual(results[1].status, "skipped_missing_column")
        self.assertTrue(any("CREATE INDEX IF NOT EXISTS" in sql for sql, _ in cursor.executed))

    def test_ensure_indexes_is_safe_when_index_exists(self):
        cursor = _FakeCursor()
        service = AutoDbCloneIndexService()
        service.VEHICLE_INDEX_TARGETS = (IndexTarget("engines", ("id",)),)

        with (
            patch("apps.autodb.services.clone_indexes.connections", {"auto_db_pro": _FakeConnection(cursor)}),
            patch.object(service, "_table_exists", return_value=True),
            patch.object(service, "_get_local_columns", return_value={"id"}),
            patch.object(service, "_index_exists", return_value=True),
        ):
            results = service.ensure_vehicle_catalog_indexes(tables=["engines"])

        self.assertEqual(results[0].status, "exists")
        self.assertFalse(any("CREATE INDEX IF NOT EXISTS" in sql for sql, _ in cursor.executed))

    def test_collect_index_status_reports_missing_columns(self):
        cursor = _FakeCursor()
        service = AutoDbCloneIndexService()
        service.VEHICLE_INDEX_TARGETS = (IndexTarget("prd", ("parentid",)),)

        with (
            patch("apps.autodb.services.clone_indexes.connections", {"auto_db_pro": _FakeConnection(cursor)}),
            patch.object(service, "_table_exists", return_value=True),
            patch.object(service, "_get_local_columns", return_value={"id"}),
        ):
            statuses = service.collect_vehicle_catalog_index_status(tables=["prd"])

        self.assertEqual(statuses[0].status, "missing_column")
