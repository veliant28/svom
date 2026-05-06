from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.product_name_enrichment import ProductNameSourceDiagnostics
from apps.autodb.services.product_name_translation import ProductNameTranslationResult


class AutoDbDiagnoseProductNameCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_diagnose_product_name.Product.objects.select_related")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_name.AutoDbProductNameEnrichmentService")
    def test_outputs_source_and_cleanup(self, service_cls_mock, select_related_mock):
        product = SimpleNamespace(
            id="p1",
            name="old",
            name_uk="old",
            name_ru="old",
            name_en="old",
            autodb_supplier_id=15,
            autodb_article_number="0127",
            autodb_article_key="15:0127",
        )
        select_related_mock.return_value.get.return_value = product

        service = service_cls_mock.return_value
        service.build_diagnostics.return_value = ProductNameSourceDiagnostics(
            source_kind="autodb_pro",
            source_reason="articles.normalized_description",
            source_title_before_cleanup="Свічка запалювання SIFR6A11",
            source_title_after_cleanup="Свічка запалювання",
            supplier_fallback_used=False,
            supplier_fallback_reason="",
            suffix_candidates=("0127", "SIFR6A11"),
            article_row={"NormalizedDescription": "Свічка запалювання SIFR6A11"},
            article_number_row={},
            article_prd_rows=(),
            article_links_rows=(),
            prd_rows=(),
            article_inf_rows=(),
            raw_offer_rows=(),
        )
        service.translator.translate_product_name.return_value = ProductNameTranslationResult(
            uk="Свічка запалювання",
            ru="Свеча зажигания",
            en="Spark plug",
            status="translated",
        )

        out = StringIO()
        call_command("autodb_diagnose_product_name", "--product-id", "p1", stdout=out)

        output = out.getvalue()
        self.assertIn("title_before_cleanup: Свічка запалювання SIFR6A11", output)
        self.assertIn("title_after_cleanup: Свічка запалювання", output)
        self.assertIn("status=translated", output)
