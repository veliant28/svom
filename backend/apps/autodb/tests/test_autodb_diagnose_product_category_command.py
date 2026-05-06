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
