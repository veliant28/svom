from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch
from hashlib import sha1

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
    def test_skips_when_name_translation_status_is_manual_locked(self):
        translator = Mock()
        service = AutoDbProductNameEnrichmentService(translator=translator)
        product = _build_product(
            name_manually_locked=False,
            name_translation_status=Product.NAME_TRANSLATION_MANUAL_LOCKED,
        )

        result = service.enrich_product(product=product, dry_run=False)

        self.assertEqual(result.status, "skipped_manual_locked")
        translator.translate_product_name.assert_not_called()
        product.save.assert_not_called()

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

    def test_combine_base_and_description_drops_conflicting_shock_absorber_prefix_for_exhaust(self):
        service = AutoDbProductNameEnrichmentService()
        combined = service._combine_base_and_description(
            base="Амортизатор",
            description="Предглушитель выхлопных газов",
        )
        self.assertEqual(combined, "Предглушитель выхлопных газов")

    def test_combine_base_and_description_deduplicates_repeated_headword_with_qualifier(self):
        service = AutoDbProductNameEnrichmentService()
        combined = service._combine_base_and_description(
            base="Соединительные элементы трубопровода",
            description="Соединительные элементы, система выпуска",
        )
        self.assertEqual(combined, "Соединительные элементы, система выпуска")

    def test_combine_base_and_description_drops_plural_additives_prefix(self):
        service = AutoDbProductNameEnrichmentService()
        combined = service._combine_base_and_description(
            base="Присадки",
            description="Присадка для топлива Pro-Line JetClean Diesel-System-Reiniger",
        )
        self.assertEqual(combined, "Присадка для топлива Pro-Line JetClean Diesel-System-Reiniger")

    def test_combine_base_and_description_drops_sealing_ring_duplicate_family(self):
        service = AutoDbProductNameEnrichmentService()
        combined = service._combine_base_and_description(
            base="Уплотняющее кольцо",
            description="Уплотнительное кольцо, стержень клапана",
        )
        self.assertEqual(combined, "Уплотнительное кольцо, стержень клапана")

    def test_combine_base_and_description_drops_electrical_wiring_prefix_for_ignition_wires(self):
        service = AutoDbProductNameEnrichmentService()
        combined = service._combine_base_and_description(
            base="Комплект электропроводки",
            description="Комплект проводов зажигания",
        )
        self.assertEqual(combined, "Комплект проводов зажигания")

    def test_combine_base_and_description_drops_pipe_prefix_for_brake_hose(self):
        service = AutoDbProductNameEnrichmentService()
        combined = service._combine_base_and_description(
            base="Шлангопровод",
            description="Тормозной шланг",
        )
        self.assertEqual(combined, "Тормозной шланг")

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

    def test_retranslates_when_existing_names_contain_placeholder_artifacts(self):
        translator = Mock()
        translator.translate_product_name.return_value = ProductNameTranslationResult(
            uk="Свічка запалювання A-line 12",
            ru="Свеча зажигания A-line 12",
            en="Spark plug A-line 12",
            status="translated",
        )
        service = AutoDbProductNameEnrichmentService(translator=translator)
        service._resolve_supplier_raw_name = Mock(return_value="")
        service.build_diagnostics = Mock(
            return_value=_diag(
                source_kind=Product.NAME_SOURCE_AUTODB_PRO,
                before="Свеча зажигания",
                after="Свеча зажигания A-line 12",
                fallback=False,
                reason="prd.normalized_plus_description",
            )
        )

        source_hash = sha1(f"{Product.NAME_SOURCE_AUTODB_PRO}:Свеча зажигания A-line 12".encode("utf-8")).hexdigest()
        product = _build_product(
            name_uk="AutoDB TOKEN 0 АВТОДБ TOKEN 1st A-line 12",
            name_ru="Свеча зажигания A-line 12",
            name_en="AUTODB TOKEN 0 AUTODB TOKEN 1st A-line 12",
            name_source_hash=source_hash,
        )
        result = service.enrich_product(product=product, dry_run=False)

        self.assertEqual(result.status, "updated")
        self.assertEqual(product.name_uk, "Свічка запалювання A-line 12")
        self.assertEqual(product.name_en, "Spark plug A-line 12")

    def test_retranslates_when_latin_suffix_quality_is_broken(self):
        translator = Mock()
        translator.translate_product_name.return_value = ProductNameTranslationResult(
            uk="Амортизатор MONROE ORIGINAL (Gas Technology)",
            ru="Амортизатор MONROE ORIGINAL (Gas Technology)",
            en="Shock absorber MONROE ORIGINAL (Gas Technology)",
            status="translated",
        )
        translator._apply_headword_translation_for_latin_suffix = Mock(
            return_value=(
                "Амортизатор MONROE ORIGINAL (Gas Technology)",
                "Амортизатор MONROE ORIGINAL (Gas Technology)",
                "Shock absorber MONROE ORIGINAL (Gas Technology)",
            )
        )
        service = AutoDbProductNameEnrichmentService(translator=translator)
        service._resolve_supplier_raw_name = Mock(return_value="")
        service.build_diagnostics = Mock(
            return_value=_diag(
                source_kind=Product.NAME_SOURCE_AUTODB_PRO,
                before="Амортизатор",
                after="Амортизатор MONROE ORIGINAL (Gas Technology)",
                fallback=False,
                reason="prd.normalized_plus_description",
            )
        )

        source_hash = sha1(
            f"{Product.NAME_SOURCE_AUTODB_PRO}:Амортизатор MONROE ORIGINAL (Gas Technology)".encode("utf-8")
        ).hexdigest()
        product = _build_product(
            name_uk="Шоктейлер MONROE ORIGINAL (Технології га)",
            name_ru="Амортизатор MONROE ORIGINAL (Gas Technology)",
            name_en="Shock absorber MONROE ORIGINAL (Gas Technology)",
            name_source_hash=source_hash,
        )
        result = service.enrich_product(product=product, dry_run=False)

        self.assertEqual(result.status, "updated")
        self.assertEqual(product.name_uk, "Амортизатор MONROE ORIGINAL (Gas Technology)")

    def test_retranslates_when_dictionary_mapping_differs_even_if_hash_unchanged(self):
        translator = Mock()
        translator.translate_product_name.return_value = ProductNameTranslationResult(
            uk="Прокладка, картер рульового механізму",
            ru="Прокладка, картер рулевого механизма",
            en="Gasket, steering gear housing",
            status="translated",
        )
        translator._normalize_key = lambda value: str(value or "").strip().lower()
        translator._load_translation_index = lambda: {
            "прокладка, картер рулевого механизма": (
                "Прокладка, картер рульового механізму",
                "Прокладка, картер рулевого механизма",
                "Gasket, steering gear housing",
            )
        }
        translator._apply_headword_translation_for_latin_suffix = Mock(
            return_value=(
                "Прокладка, картер рулевого механизма",
                "Прокладка, картер рулевого механизма",
                "Прокладка, картер рулевого механизма",
            )
        )
        service = AutoDbProductNameEnrichmentService(translator=translator)
        service._resolve_supplier_raw_name = Mock(return_value="")
        service.build_diagnostics = Mock(
            return_value=_diag(
                source_kind=Product.NAME_SOURCE_AUTODB_PRO,
                before="Прокладка, картер рулевого механизма",
                after="Прокладка, картер рулевого механизма",
                fallback=False,
                reason="articles.normalized_description",
            )
        )

        source_hash = sha1(
            f"{Product.NAME_SOURCE_AUTODB_PRO}:Прокладка, картер рулевого механизма".encode("utf-8")
        ).hexdigest()
        product = _build_product(
            name_uk="Газування, керма",
            name_ru="Прокладка, картер рулевого механизма",
            name_en="Gasting, steering crankcase",
            name_source_hash=source_hash,
        )
        result = service.enrich_product(product=product, dry_run=False)

        self.assertEqual(result.status, "updated")
        self.assertEqual(product.name_uk, "Прокладка, картер рульового механізму")
        self.assertEqual(product.name_en, "Gasket, steering gear housing")
