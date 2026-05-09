from __future__ import annotations

from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.autodb.services.linked_product_related_enrichment import (
    AutoDbLinkedProductRelatedEnrichmentService,
    LinkedProductRelatedLocalState,
    estimate_remote_queries_for_tables,
    extract_related_tables,
    is_related_local_complete,
    is_remote_quota_error,
)


class LinkedProductRelatedEnrichmentServiceTests(SimpleTestCase):
    def test_extract_related_tables_deduplicates_and_skips_empty(self):
        tables = extract_related_tables(["article_prd", "", "article_links", "article_prd", "prd"])
        self.assertEqual(tables, ["article_prd", "article_links", "prd"])

    def test_enrich_related_skips_when_remote_disabled(self):
        article_enrichment = Mock()
        service = AutoDbLinkedProductRelatedEnrichmentService(article_enrichment=article_enrichment)

        result = service.enrich_related(
            supplier_id=324,
            article_number="WL7042",
            tables=["article_prd", "prd"],
            dry_run=True,
            allow_remote=False,
        )

        self.assertIsNone(result)
        article_enrichment.enrich_article.assert_not_called()

    def test_enrich_related_passes_dry_run_to_article_service(self):
        article_enrichment = Mock()
        expected = object()
        article_enrichment.enrich_article.return_value = expected
        service = AutoDbLinkedProductRelatedEnrichmentService(article_enrichment=article_enrichment)

        result = service.enrich_related(
            supplier_id=324,
            article_number="WL7042",
            tables=["article_prd", "prd"],
            dry_run=True,
            allow_remote=True,
        )

        self.assertIs(result, expected)
        article_enrichment.enrich_article.assert_called_once_with(
            supplier_id=324,
            article_number="WL7042",
            tables=["article_prd", "prd"],
            dry_run=True,
        )

    def test_estimate_remote_queries_for_tables(self):
        self.assertEqual(estimate_remote_queries_for_tables(["article_prd", "article_links", "prd"]), 3)
        self.assertEqual(estimate_remote_queries_for_tables(["article_prd"]), 1)
        self.assertEqual(estimate_remote_queries_for_tables([]), 0)

    def test_is_related_local_complete(self):
        local = LinkedProductRelatedLocalState(
            article_exists=True,
            article_prd_rows=2,
            article_links_rows=3,
            prd_rows=4,
        )
        self.assertTrue(is_related_local_complete(state=local, tables=["article_prd", "article_links", "prd"]))
        self.assertTrue(is_related_local_complete(state=local, tables=["articles"]))
        self.assertFalse(is_related_local_complete(state=local, tables=["article_prd", "article_images"]))

    def test_is_remote_quota_error(self):
        self.assertTrue(is_remote_quota_error("1226 (42000): User has exceeded the 'max_questions' resource"))
        self.assertTrue(is_remote_quota_error("max_questions exceeded"))
        self.assertFalse(is_remote_quota_error("connection reset by peer"))
