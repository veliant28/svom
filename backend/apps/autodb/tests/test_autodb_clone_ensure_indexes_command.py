from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.clone_indexes import IndexEnsureResult


class AutoDbCloneEnsureIndexesCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_clone_ensure_indexes.AutoDbCloneIndexService.ensure_vehicle_catalog_indexes")
    def test_only_forwards_table_filter(self, ensure_mock):
        ensure_mock.return_value = [
            IndexEnsureResult(
                table="manufacturers",
                columns=("id",),
                index_name="ix_autodb_clone_manufacturers_id",
                status="created",
            )
        ]
        out = StringIO()

        call_command("autodb_clone_ensure_indexes", "--only", "manufacturers", stdout=out)

        ensure_mock.assert_called_once_with(tables=["manufacturers"])
        self.assertIn("ensure finished", out.getvalue().lower())

    @patch("apps.autodb.management.commands.autodb_clone_ensure_indexes.AutoDbCloneIndexService.ensure_article_catalog_indexes")
    def test_article_catalog_scope_uses_article_indexes(self, ensure_mock):
        ensure_mock.return_value = []
        out = StringIO()

        call_command("autodb_clone_ensure_indexes", "--article-catalog", stdout=out)

        ensure_mock.assert_called_once_with(tables=[])
