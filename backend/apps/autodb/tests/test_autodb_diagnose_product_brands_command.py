from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_brand_enrichment import ProductBrandDiagnostics


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported")


class AutoDbDiagnoseProductBrandsCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_diagnose_product_brands.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_diagnose_product_brands.AutoDbProductBrandEnrichmentService")
    def test_diagnose_summary(self, service_cls_mock, _ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet(
            [
                SimpleNamespace(id="p1", autodb_supplier_id=324),
                SimpleNamespace(id="p2", autodb_supplier_id=None),
            ]
        )
        service.diagnose_product.side_effect = [
            ProductBrandDiagnostics(
                product_id="p1",
                product_name="Prod 1",
                current_brand_id="b1",
                current_brand_name="Legacy 1",
                autodb_supplier_id=324,
                autodb_article_key="324:WIX123",
                autodb_supplier_name="WIX FILTERS",
                raw_supplier_brand_examples=("WIX",),
                proposed_brand_name="WIX FILTERS",
                proposed_brand_source="autodb_pro",
                status="ok",
                reason="",
                would_update=True,
            ),
            ProductBrandDiagnostics(
                product_id="p2",
                product_name="Prod 2",
                current_brand_id="b2",
                current_brand_name="Legacy 2",
                autodb_supplier_id=None,
                autodb_article_key="",
                autodb_supplier_name="",
                raw_supplier_brand_examples=("RAW",),
                proposed_brand_name="RAW",
                proposed_brand_source="supplier_fallback",
                status="skipped_no_autodb_supplier_id",
                reason="product_not_linked_to_autodb_supplier",
                would_update=False,
            ),
        ]
        out = StringIO()
        call_command("autodb_diagnose_product_brands", "--all", "--limit", "2", stdout=out)
        output = out.getvalue()
        self.assertIn("- processed: 2", output)
        self.assertIn("- linked_products: 1", output)
        self.assertIn("- products_with_autodb_supplier_id: 1", output)
        self.assertIn("- products_missing_autodb_supplier_id: 1", output)
        self.assertIn("- products_where_brand_would_update: 1", output)
        self.assertIn("- UTR calls=0", output)
