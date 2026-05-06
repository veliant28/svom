from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_name_enrichment import ProductNameEnrichmentResult


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported in fake queryset")


class AutoDbUpdateProductNamesCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_update_product_names.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_names.AutoDbProductNameEnrichmentService")
    @patch("apps.autodb.management.commands.autodb_update_product_names.Command._build_queryset")
    def test_dry_run_outputs_summary(self, build_qs_mock, service_cls_mock, _ready_mock):
        build_qs_mock.return_value = _FakeQuerySet([SimpleNamespace(id="1"), SimpleNamespace(id="2")])
        service = service_cls_mock.return_value
        service.enrich_product.side_effect = [
            ProductNameEnrichmentResult(
                product_id="1",
                status="updated",
                old_name="0127 Свічка запалювання SIFR6A11",
                supplier_raw_name="0127 Свічка запалювання SIFR6A11",
                autodb_source_title="Свічка запалювання",
                new_name_uk="Свічка запалювання",
                new_name_ru="Свеча зажигания",
                new_name_en="Spark plug",
                name_source="autodb_pro",
                name_source_hash="abc",
                translation_status="translated",
            ),
            ProductNameEnrichmentResult(
                product_id="2",
                status="skipped_no_autodb_link",
                old_name="legacy name",
                supplier_raw_name="",
                autodb_source_title="",
                new_name_uk="",
                new_name_ru="",
                new_name_en="",
                name_source="",
                name_source_hash="",
                translation_status="",
            ),
        ]
        out = StringIO()

        call_command("autodb_update_product_names", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("Auto_DB_Pro product name update summary", output)
        self.assertIn("- processed: 2", output)
        self.assertIn("- updated: 1", output)
        self.assertIn("- skipped_no_autodb_link: 1", output)
        self.assertIn("UTR calls: 0", output)

    @patch(
        "apps.autodb.management.commands.autodb_update_product_names.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_names.ProductIndexer.reindex_products")
    @patch("apps.autodb.management.commands.autodb_update_product_names.AutoDbProductNameEnrichmentService")
    @patch("apps.autodb.management.commands.autodb_update_product_names.Command._build_queryset")
    def test_update_search_index_only_for_updated_products(self, build_qs_mock, service_cls_mock, reindex_mock, _ready_mock):
        build_qs_mock.return_value = _FakeQuerySet([SimpleNamespace(id="1"), SimpleNamespace(id="2")])
        service = service_cls_mock.return_value
        service.enrich_product.side_effect = [
            ProductNameEnrichmentResult(
                product_id="1",
                status="updated",
                old_name="old",
                supplier_raw_name="raw",
                autodb_source_title="title",
                new_name_uk="name",
                new_name_ru="name",
                new_name_en="name",
                name_source="autodb_pro",
                name_source_hash="h1",
                translation_status="pending",
            ),
            ProductNameEnrichmentResult(
                product_id="2",
                status="skipped_hash_unchanged",
                old_name="old",
                supplier_raw_name="raw",
                autodb_source_title="title",
                new_name_uk="name",
                new_name_ru="name",
                new_name_en="name",
                name_source="autodb_pro",
                name_source_hash="h1",
                translation_status="pending",
            ),
        ]
        reindex_mock.return_value = {"indexed": 1, "errors": 0, "total": 1, "backend": "db"}

        call_command("autodb_update_product_names", "--update-search-index")

        reindex_mock.assert_called_once_with(product_ids=["1"])

    @patch(
        "apps.autodb.management.commands.autodb_update_product_names.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_names.ProductIndexer.reindex_products")
    @patch("apps.autodb.management.commands.autodb_update_product_names.AutoDbProductNameEnrichmentService")
    @patch("apps.autodb.management.commands.autodb_update_product_names.Command._build_queryset")
    def test_dry_run_skips_search_reindex(self, build_qs_mock, service_cls_mock, reindex_mock, _ready_mock):
        build_qs_mock.return_value = _FakeQuerySet([SimpleNamespace(id="1")])
        service = service_cls_mock.return_value
        service.enrich_product.return_value = ProductNameEnrichmentResult(
            product_id="1",
            status="updated",
            old_name="old",
            supplier_raw_name="raw",
            autodb_source_title="title",
            new_name_uk="name",
            new_name_ru="name",
            new_name_en="name",
            name_source="autodb_pro",
            name_source_hash="h1",
            translation_status="translated",
        )
        out = StringIO()

        call_command("autodb_update_product_names", "--dry-run", "--update-search-index", stdout=out)

        reindex_mock.assert_not_called()
        self.assertIn("search reindex: skipped (dry-run)", out.getvalue())
