from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.product_category_enrichment import ProductCategoryDiagnostics


class AutoDbDiagnoseProductCategoryCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_diagnose_product_category.Product.objects.select_related")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_category.AutoDbProductCategoryEnrichmentService")
    def test_outputs_diagnostics(self, service_cls_mock, select_related_mock):
        product = SimpleNamespace(
            id="p1",
            name="Test",
            category=SimpleNamespace(id="c1", name="Legacy", source="legacy", autodb_prd_id=None),
        )
        select_related_mock.return_value.get.return_value = product

        service = service_cls_mock.return_value
        service.build_diagnostics.return_value = ProductCategoryDiagnostics(
            product_id="p1",
            bridge_supplier_id=15,
            bridge_article_number="0127",
            bridge_article_key="15:0127",
            article_prd_rows=({"supplierid": 15, "datasupplierarticlenumber": "0127", "productid": 101},),
            article_links_rows=(),
            article_row={"supplierid": 15, "datasupplierarticlenumber": "0127", "NormalizedDescription": "Свічка запалювання"},
            prd_rows=({"id": 101, "description": "Свічки запалювання", "parentid": None},),
            autodb_article_title="Свічка запалювання",
            autodb_prd_title="Свічки запалювання",
            chosen_prd_id=101,
            chosen_source="article_prd",
            chosen_prd_row={"id": 101, "description": "Свічки запалювання"},
            current_category_id="c1",
            current_category_name="Legacy",
            current_category_source="legacy",
            current_category_autodb_prd_id=None,
            proposed_category_id="",
            proposed_category_name="",
            proposed_category_source="",
            proposed_category_autodb_prd_id=None,
            suspicious_link=False,
            suspicious_reason="",
            skipped_reason="",
        )

        out = StringIO()
        call_command("autodb_diagnose_product_category", "--product-id", "p1", stdout=out)

        output = out.getvalue()
        self.assertIn("chosen_prd_id: 101", output)
        self.assertIn("chosen_source: article_prd", output)
        self.assertIn("UTR calls: 0", output)

    @patch("apps.autodb.management.commands.autodb_diagnose_product_category.Command._link_quality_status", return_value="trusted")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_category.AutoDbProductCategoryEnrichmentService")
    def test_batch_mode_outputs_summary(self, service_cls_mock, _quality_mock):
        class _FakeQuerySet:
            def __init__(self, items):
                self._items = list(items)

            def iterator(self, chunk_size=200):
                return iter(self._items)

            def __getitem__(self, item):
                if isinstance(item, slice):
                    return _FakeQuerySet(self._items[item])
                raise TypeError("Only slicing is supported")

        product = SimpleNamespace(
            id="p-batch-1",
            name="Свічка",
            get_localized_name=lambda locale=None: "Свічка",
            category=SimpleNamespace(source="legacy"),
            category_manually_locked=False,
        )
        service = service_cls_mock.return_value
        service.build_queryset.return_value = _FakeQuerySet([product])
        service.build_diagnostics.return_value = ProductCategoryDiagnostics(
            product_id="p-batch-1",
            bridge_supplier_id=15,
            bridge_article_number="0127",
            bridge_article_key="15:0127",
            article_prd_rows=({"productid": 101},),
            article_links_rows=(),
            article_row={"supplierid": 15},
            prd_rows=({"id": 101, "description": "Свічки"},),
            autodb_article_title="Свічка",
            autodb_prd_title="Свічки",
            chosen_prd_id=101,
            chosen_source="article_prd",
            chosen_prd_row={"id": 101},
            current_category_id="c1",
            current_category_name="Legacy",
            current_category_source="legacy",
            current_category_autodb_prd_id=None,
            proposed_category_id="",
            proposed_category_name="",
            proposed_category_source="",
            proposed_category_autodb_prd_id=None,
            suspicious_link=False,
            suspicious_reason="",
            skipped_reason="",
        )
        service.enrich_product.return_value = SimpleNamespace(status="updated")

        out = StringIO()
        call_command(
            "autodb_diagnose_product_category",
            "--only-linked",
            "--limit",
            "10",
            stdout=out,
        )
        output = out.getvalue()
        self.assertIn("total_checked: 1", output)
        self.assertIn("category_update_possible: 1", output)
        self.assertIn("UTR calls: 0", output)
