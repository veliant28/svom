from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.services.product_name_enrichment import (
    AutoDbProductNameEnrichmentService,
    ProductNameSourceDiagnostics,
)
from apps.autodb.services.product_name_translation import ProductNameTranslationResult
from apps.catalog.models import Product


def _build_product(**overrides):
    product = SimpleNamespace(
        id="product-1",
        name="0127 Свічка запалювання SIFR6A11",
        article="0127",
        sku="SIFR6A11",
        name_uk="",
        name_ru="",
        name_en="",
        name_source="",
        name_source_hash="",
        name_source_text="",
        name_translation_status="",
        name_translation_error="",
        name_manually_locked=False,
        autodb_supplier_id=15,
        autodb_article_number="0127",
        save=Mock(),
    )
    for key, value in overrides.items():
        setattr(product, key, value)
    return product


def _diag(*, source_kind: str, before: str, after: str, fallback: bool, reason: str) -> ProductNameSourceDiagnostics:
    return ProductNameSourceDiagnostics(
        source_kind=source_kind,
        source_reason=reason,
        source_title_before_cleanup=before,
        source_title_after_cleanup=after,
        supplier_fallback_used=fallback,
        supplier_fallback_reason="autodb_title_missing_or_unusable" if fallback else "",
        suffix_candidates=("0127", "SIFR6A11"),
        article_row={},
        article_number_row={},
        article_prd_rows=(),
        article_links_rows=(),
        prd_rows=(),
        article_inf_rows=(),
        raw_offer_rows=(),
    )


class AutoDbProductNameEnrichmentServiceTests(SimpleTestCase):
    def test_linked_product_uses_autodb_source_not_fallback(self):
        translator = Mock()
        translator.translate_product_name.return_value = ProductNameTranslationResult(
            uk="Свічка запалювання",
            ru="Свеча зажигания",
            en="Spark plug",
            status="translated",
        )
        service = AutoDbProductNameEnrichmentService(translator=translator)
        service._resolve_supplier_raw_name = Mock(return_value="0127 Свічка запалювання SIFR6A11")
        service.build_diagnostics = Mock(
            return_value=_diag(
                source_kind=Product.NAME_SOURCE_AUTODB_PRO,
                before="Свеча зажигания",
                after="Свеча зажигания",
                fallback=False,
                reason="articles.normalized_description",
            )
        )

        product = _build_product()
        result = service.enrich_product(product=product, dry_run=False)

        self.assertEqual(result.status, "updated")
        self.assertEqual(product.name_source, Product.NAME_SOURCE_AUTODB_PRO)
        self.assertFalse(result.supplier_fallback_used)
        self.assertEqual(product.name_uk, "Свічка запалювання")
        self.assertEqual(product.name_ru, "Свеча зажигания")
        self.assertEqual(product.name_en, "Spark plug")

    def test_source_title_with_external_sku_suffix_is_cleaned(self):
        service = AutoDbProductNameEnrichmentService()
        service._resolve_supplier_raw_name = Mock(return_value="")
        service._find_article_row = Mock(return_value={"NormalizedDescription": "Свічка запалювання SIFR6A11"})
        service._find_article_number_row = Mock(return_value={})
        service._find_article_prd_rows = Mock(return_value=[])
        service._find_article_links_rows = Mock(return_value=[])
        service._find_prd_rows = Mock(return_value=[])
        service._find_article_inf_rows = Mock(return_value=[])
        service._collect_raw_offer_rows = Mock(return_value=[{"external_sku": "SIFR6A11", "article": "0127", "raw_payload": {}}])

        diagnostics = service.build_diagnostics(product=_build_product())

        self.assertEqual(diagnostics.source_kind, Product.NAME_SOURCE_AUTODB_PRO)
        self.assertEqual(diagnostics.source_title_before_cleanup, "Свічка запалювання SIFR6A11")
        self.assertEqual(diagnostics.source_title_after_cleanup, "Свічка запалювання")

    def test_source_title_with_article_number_suffix_is_cleaned(self):
        service = AutoDbProductNameEnrichmentService()
        cleaned = service._clean_title(
            title="Свічка запалювання 0127",
            suffix_candidates=("0127",),
            is_fallback=False,
        )
        self.assertEqual(cleaned, "Свічка запалювання")

    def test_combine_base_and_description_deduplicates_typo_near_match(self):
        service = AutoDbProductNameEnrichmentService()
        combined = service._combine_base_and_description(
            base="Комплект пыльника",
            description="Комплект пылника, приводной вал",
        )
        self.assertEqual(combined, "Комплект пылника, приводной вал")

    def test_cleaned_title_translates_to_uk_ru_en(self):
        service = AutoDbProductNameEnrichmentService()
        service._resolve_supplier_raw_name = Mock(return_value="")
        service.build_diagnostics = Mock(
            return_value=_diag(
                source_kind=Product.NAME_SOURCE_AUTODB_PRO,
                before="Свічка запалювання SIFR6A11",
                after="Свічка запалювання",
                fallback=False,
                reason="articles.normalized_description",
            )
        )

        product = _build_product()
        result = service.enrich_product(product=product, dry_run=False)

        self.assertEqual(result.translation_status, "translated")
        self.assertEqual(product.name_uk, "Свічка запалювання")
        self.assertEqual(product.name_ru, "Свеча зажигания")
        self.assertEqual(product.name_en, "Spark plug")

    def test_supplier_fallback_used_only_when_no_autodb_title(self):
        service = AutoDbProductNameEnrichmentService(translator=Mock())
        service.translator.translate_product_name.return_value = ProductNameTranslationResult(
            uk="Свічка запалювання",
            ru="Свеча зажигания",
            en="Spark plug",
            status="translated",
        )
        service._resolve_supplier_raw_name = Mock(return_value="0127 Свічка запалювання SIFR6A11")
        service.build_diagnostics = Mock(
            return_value=_diag(
                source_kind=Product.NAME_SOURCE_SUPPLIER_FALLBACK,
                before="0127 Свічка запалювання SIFR6A11",
                after="Свічка запалювання",
                fallback=True,
                reason="supplier_raw_offer.product_name",
            )
        )

        product = _build_product()
        result = service.enrich_product(product=product, dry_run=False)

        self.assertEqual(result.status, "updated")
        self.assertTrue(result.supplier_fallback_used)
        self.assertEqual(product.name_source, Product.NAME_SOURCE_SUPPLIER_FALLBACK)

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_does_not_call_utr_client(self, utr_cls):
        service = AutoDbProductNameEnrichmentService()
        service._resolve_supplier_raw_name = Mock(return_value="")
        service.build_diagnostics = Mock(
            return_value=_diag(
                source_kind=Product.NAME_SOURCE_AUTODB_PRO,
                before="Свічка запалювання",
                after="Свічка запалювання",
                fallback=False,
                reason="articles.normalized_description",
            )
        )

        service.enrich_product(product=_build_product(), dry_run=True)

        utr_cls.assert_not_called()
