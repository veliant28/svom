from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService


class AutoDbArticleEnrichmentServiceTests(SimpleTestCase):
    def test_targeted_enrichment_reads_only_related_tables(self):
        storage = Mock()
        storage.get_remote_columns.return_value = ["articleid", "supplierid"]
        storage.get_local_columns.return_value = []
        storage.fetch_remote_rows_exact.side_effect = lambda **kwargs: [{"articleid": kwargs["filters"].get("articleid", 0)}]
        storage.upsert_rows.return_value = 0

        service = AutoDbArticleEnrichmentService(storage=storage)
        result = service.enrich_article(article_id=321, supplier_id=11)

        self.assertIn("article_attributes", result.populated_tables)
        self.assertNotIn("suppliers", result.populated_tables)
        self.assertEqual(storage.fetch_remote_rows_exact.call_count, len(service.RELATED_TABLES) - 1)
        called_tables = {call.kwargs["table"] for call in storage.fetch_remote_rows_exact.call_args_list}
        self.assertEqual(called_tables, set(service.RELATED_TABLES) - {"article_m"})

    def test_skips_table_when_relation_columns_are_missing(self):
        storage = Mock()
        storage.get_remote_columns.return_value = ["id"]
        storage.get_local_columns.return_value = []
        storage.fetch_remote_rows_exact.return_value = []

        service = AutoDbArticleEnrichmentService(storage=storage)
        result = service.enrich_article(article_id=12, supplier_id=2, tables=["article_m"])

        self.assertIn("article_m", result.skipped_tables)
        self.assertTrue(result.warnings)
        storage.fetch_remote_rows_exact.assert_not_called()
