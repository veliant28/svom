from django.test import SimpleTestCase

from apps.autodb.services.product_name_translation import ProductNameTranslationService


class ProductNameTranslationServiceTests(SimpleTestCase):
    def test_static_translation_for_spark_plug(self):
        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Свічка запалювання", source_lang="uk")
        self.assertEqual(result.uk, "Свічка запалювання")
        self.assertEqual(result.ru, "Свеча зажигания")
        self.assertEqual(result.en, "Spark plug")
        self.assertEqual(result.status, "translated")

    def test_amortyzator_translates_to_shock_absorber(self):
        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Амортизатор")
        self.assertEqual(result.uk, "Амортизатор")
        self.assertEqual(result.ru, "Амортизатор")
        self.assertEqual(result.en, "Shock absorber")
        self.assertEqual(result.status, "translated")

    def test_unknown_phrase_is_pending(self):
        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Невідомий товар", source_lang="uk")
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.uk, "Невідомий товар")
        self.assertEqual(result.error, "translation_not_found_in_dictionary")
