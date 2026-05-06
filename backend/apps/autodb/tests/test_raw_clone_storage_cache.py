from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage


class AutoDbRawCloneStorageCacheTests(SimpleTestCase):
    def test_remote_columns_are_cached_per_table(self):
        schema_service = Mock()
        col = Mock()
        col.name = "supplierid"
        info = Mock()
        info.columns = [col]
        schema_service.introspect_table.return_value = info

        storage = AutoDbRawCloneStorage(remote_client=Mock(), schema_service=schema_service)

        first = storage.get_remote_columns("articles")
        second = storage.get_remote_columns("articles")

        self.assertEqual(first, ["supplierid"])
        self.assertEqual(second, ["supplierid"])
        schema_service.introspect_table.assert_called_once_with("articles")

    def test_ensure_table_uses_existing_local_schema_without_remote_call(self):
        schema_service = Mock()
        col = Mock()
        col.name = "supplierid"
        info_remote = Mock()
        info_remote.columns = [col]
        schema_service.introspect_table.return_value = info_remote
        storage = AutoDbRawCloneStorage(remote_client=Mock(), schema_service=schema_service)
        storage.get_local_columns = Mock(return_value={"id", "description"})

        info = storage.ensure_table("suppliers")

        self.assertEqual(info.table, "suppliers")
        self.assertEqual(sorted(col.name for col in info.columns), ["description", "id"])
        schema_service.ensure_table.assert_not_called()
        remote_cols = storage.get_remote_columns("suppliers")
        self.assertEqual(remote_cols, ["supplierid"])
        schema_service.introspect_table.assert_called_once_with("suppliers")
