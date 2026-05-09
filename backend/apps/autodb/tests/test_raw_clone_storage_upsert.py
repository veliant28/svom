from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage


class AutoDbRawCloneStorageUpsertTests(SimpleTestCase):
    @patch("apps.autodb.services.raw_clone_storage.transaction.atomic")
    @patch("apps.autodb.services.raw_clone_storage.transaction.savepoint")
    @patch("apps.autodb.services.raw_clone_storage.transaction.savepoint_commit")
    @patch("apps.autodb.services.raw_clone_storage.transaction.savepoint_rollback")
    @patch("apps.autodb.services.raw_clone_storage.connections")
    def test_upsert_rows_rolls_back_failed_bulk_and_recovers_row_mode(
        self,
        connections_mock,
        rollback_mock,
        commit_mock,
        savepoint_mock,
        atomic_mock,
    ):
        cursor = Mock()
        cursor.executemany.side_effect = RuntimeError("bulk failed")
        cursor.execute.side_effect = [None, RuntimeError("row failed")]

        conn_ctx = Mock()
        conn_ctx.__enter__ = Mock(return_value=cursor)
        conn_ctx.__exit__ = Mock(return_value=False)
        connection = Mock()
        connection.cursor.return_value = conn_ctx
        connections_mock.__getitem__.return_value = connection

        sid_values = ["bulk-sp", "row-1-sp", "row-2-sp"]
        savepoint_mock.side_effect = sid_values

        atomic_ctx = Mock()
        atomic_ctx.__enter__ = Mock(return_value=None)
        atomic_ctx.__exit__ = Mock(return_value=False)
        atomic_mock.return_value = atomic_ctx

        storage = AutoDbRawCloneStorage(remote_client=Mock(), schema_service=Mock(), db_alias="auto_db_pro")
        schema_info = Mock()
        schema_info.columns = [Mock(name="supplierid"), Mock(name="datasupplierarticlenumber")]
        schema_info.columns[0].name = "supplierid"
        schema_info.columns[1].name = "datasupplierarticlenumber"
        schema_info.primary_key_columns = ["supplierid", "datasupplierarticlenumber"]
        schema_info.unique_keys = []
        storage.ensure_table = Mock(return_value=schema_info)

        failed = storage.upsert_rows(
            table="article_prd",
            rows=[
                {"supplierid": 324, "datasupplierarticlenumber": "WL7042"},
                {"supplierid": 324, "datasupplierarticlenumber": "WP9357"},
            ],
        )

        self.assertEqual(failed, 1)
        self.assertEqual(cursor.executemany.call_count, 1)
        self.assertEqual(cursor.execute.call_count, 2)
        rollback_mock.assert_any_call("bulk-sp", using="auto_db_pro")
        commit_mock.assert_any_call("row-1-sp", using="auto_db_pro")
        rollback_mock.assert_any_call("row-2-sp", using="auto_db_pro")

    @patch("apps.autodb.services.raw_clone_storage.transaction.atomic")
    @patch("apps.autodb.services.raw_clone_storage.transaction.savepoint")
    @patch("apps.autodb.services.raw_clone_storage.transaction.savepoint_commit")
    @patch("apps.autodb.services.raw_clone_storage.transaction.savepoint_rollback")
    @patch("apps.autodb.services.raw_clone_storage.connections")
    def test_upsert_rows_maps_remote_keys_case_insensitively(
        self,
        connections_mock,
        _rollback_mock,
        _commit_mock,
        savepoint_mock,
        atomic_mock,
    ):
        captured = {}

        class _Cursor:
            def executemany(self, sql, values):
                captured["sql"] = sql
                captured["values"] = values

        cursor = _Cursor()
        conn_ctx = Mock()
        conn_ctx.__enter__ = Mock(return_value=cursor)
        conn_ctx.__exit__ = Mock(return_value=False)
        connection = Mock()
        connection.cursor.return_value = conn_ctx
        connections_mock.__getitem__.return_value = connection

        atomic_ctx = Mock()
        atomic_ctx.__enter__ = Mock(return_value=None)
        atomic_ctx.__exit__ = Mock(return_value=False)
        atomic_mock.return_value = atomic_ctx
        savepoint_mock.return_value = "bulk-sp"

        storage = AutoDbRawCloneStorage(remote_client=Mock(), schema_service=Mock(), db_alias="auto_db_pro")
        schema_info = Mock()
        supplier_col = Mock()
        supplier_col.name = "supplierid"
        article_col = Mock()
        article_col.name = "datasupplierarticlenumber"
        product_col = Mock()
        product_col.name = "productId"
        schema_info.columns = [supplier_col, article_col, product_col]
        schema_info.primary_key_columns = ["supplierid", "datasupplierarticlenumber", "productId"]
        schema_info.unique_keys = []
        storage.ensure_table = Mock(return_value=schema_info)

        failed = storage.upsert_rows(
            table="article_prd",
            rows=[{"supplierid": 324, "datasupplierarticlenumber": "WL7042", "productid": 8}],
        )

        self.assertEqual(failed, 0)
        self.assertIn('"productId"', captured["sql"])
        inserted = captured["values"][0]
        self.assertIn(8, inserted)
