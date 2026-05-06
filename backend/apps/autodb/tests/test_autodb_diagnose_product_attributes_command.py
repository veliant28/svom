from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.product_attribute_enrichment import ProductAttributeDiagnostics


class AutoDbDiagnoseProductAttributesCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_diagnose_product_attributes.Product.objects.select_related")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_attributes.AutoDbProductAttributeEnrichmentService")
    def test_outputs_diagnostics(self, service_cls_mock, select_related_mock):
        product = SimpleNamespace(id="p1", name="Test product")
        select_related_mock.return_value.prefetch_related.return_value.get.return_value = product

        service = service_cls_mock.return_value
        service.build_diagnostics.return_value = ProductAttributeDiagnostics(
            product_id="p1",
            bridge_supplier_id=300,
            bridge_article_number="820099",
            bridge_article_key="300:820099",
            raw_rows=(
                {
                    "supplierid": 300,
                    "datasupplierarticlenumber": "820099",
                    "id": 1,
                    "displaytitle": "Диаметр",
                    "displayvalue": "25 мм",
                },
            ),
            proposals=(
                {
                    "attribute_name": "Диаметр",
                    "attribute_value": "25 мм",
                    "autodb_attribute_id": 1,
                },
            ),
            current_attributes=(
                {
                    "product_attribute_id": "pa1",
                    "attribute_name": "Материал",
                    "value": "Сталь",
                    "source": "manual",
                    "manual_locked": True,
                },
            ),
            skipped_reason="",
        )

        out = StringIO()
        call_command("autodb_diagnose_product_attributes", "--product-id", "p1", stdout=out)

        output = out.getvalue()
        self.assertIn("bridge.autodb_article_key: 300:820099", output)
        self.assertIn("attribute_name=Диаметр", output)
        self.assertIn("UTR calls: 0", output)
