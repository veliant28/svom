from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_category_enrichment import ProductCategoryEnrichmentResult


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported in fake queryset")


class AutoDbUpdateProductCategoriesCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_update_product_categories.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_update_product_categories.AutoDbProductCategoryEnrichmentService")
    @patch("apps.autodb.management.commands.autodb_update_product_categories.Command._build_queryset")
    def test_dry_run_outputs_summary(self, build_qs_mock, service_cls_mock, _ready_mock):
        build_qs_mock.return_value = _FakeQuerySet([SimpleNamespace(id="p1"), SimpleNamespace(id="p2")])
        service = service_cls_mock.return_value
        service.enrich_product.side_effect = [
            ProductCategoryEnrichmentResult(
                product_id="p1",
                status="updated",
                old_category_id="c1",
                old_category_name="Legacy",
                new_category_id="c2",
                new_category_name="Свічки запалювання",
                chosen_prd_id=101,
                chosen_source="article_prd",
                created_category=True,
                reused_category=False,
                parent_missing=False,
                translation_pending=False,
            ),
            ProductCategoryEnrichmentResult(
                product_id="p2",
                status="skipped_suspicious_link",
                old_category_id="c1",
                old_category_name="Legacy",
                new_category_id="c1",
                new_category_name="Legacy",
                chosen_prd_id=None,
                chosen_source="",
                warning="conflict",
            ),
        ]
        out = StringIO()

        call_command("autodb_update_product_categories", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("Auto_DB_Pro product category update summary", output)
        self.assertIn("- processed: 2", output)
        self.assertIn("- updated: 1", output)
        self.assertIn("- created_categories: 1", output)
        self.assertIn("- skipped_suspicious_link: 1", output)
        self.assertIn("UTR calls: 0", output)

    @patch(
        "apps.autodb.management.commands.autodb_update_product_categories.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_update_product_categories.AutoDbProductCategoryEnrichmentService")
    @patch("apps.autodb.management.commands.autodb_update_product_categories.Command._build_queryset")
    def test_failed_counter_increments(self, build_qs_mock, service_cls_mock, _ready_mock):
        build_qs_mock.return_value = _FakeQuerySet([SimpleNamespace(id="p1")])
        service = service_cls_mock.return_value
        service.enrich_product.side_effect = RuntimeError("boom")
        out = StringIO()

        call_command("autodb_update_product_categories", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("status=failed", output)
        self.assertIn("- failed: 1", output)
