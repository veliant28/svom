from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_brand_enrichment import ProductBrandEnrichmentResult


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def iterator(self, chunk_size=200):
        return iter(self._items)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return _FakeQuerySet(self._items[item])
        raise TypeError("Only slicing is supported")


class AutoDbUpdateProductBrandsCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_update_product_brands.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_update_product_brands.AutoDbProductBrandEnrichmentService")
    def test_summary_and_utr_zero(self, service_cls_mock, _ready_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet(
            [
                SimpleNamespace(id="p1", autodb_supplier_id=324),
                SimpleNamespace(id="p2", autodb_supplier_id=15),
            ]
        )
        service.enrich_product.side_effect = [
            ProductBrandEnrichmentResult(
                product_id="p1",
                status="updated",
                old_brand_name="Legacy",
                new_brand_name="WIX FILTERS",
                brand_source="autodb_pro",
                autodb_supplier_id=324,
                autodb_supplier_name="WIX FILTERS",
                source_hash="h1",
                raw_supplier_brand_examples=("WIX",),
                reason="resolved_autodb_supplier_name",
            ),
            ProductBrandEnrichmentResult(
                product_id="p2",
                status="skipped_hash_unchanged",
                old_brand_name="NGK",
                new_brand_name="NGK",
                brand_source="autodb_pro",
                autodb_supplier_id=15,
                autodb_supplier_name="NGK",
                source_hash="h2",
                raw_supplier_brand_examples=(),
                reason="brand_hash_unchanged",
            ),
        ]
        out = StringIO()
        call_command("autodb_update_product_brands", "--only-linked", "--limit", "2", "--dry-run", stdout=out)
        output = out.getvalue()
        self.assertIn("- processed: 2", output)
        self.assertIn("- updated: 1", output)
        self.assertIn("- skipped_hash_unchanged: 1", output)
        self.assertIn("- UTR calls=0", output)
        self.assertIn("- price/stock changed=0", output)
