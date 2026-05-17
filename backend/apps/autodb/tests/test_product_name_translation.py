from django.test import SimpleTestCase
from django.test.utils import override_settings
from unittest.mock import patch

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

    @override_settings(AUTODB_OFFLINE_TRANSLATE_ENABLED=False)
    def test_unknown_phrase_is_pending(self):
        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Невідомий товар", source_lang="uk")
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.uk, "Невідомий товар")
        self.assertEqual(result.error, "translation_not_found_in_dictionary")

    def test_detects_russian_without_specific_letters(self):
        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Свеча зажигания")
        self.assertEqual(result.source_lang, "ru")

    @override_settings(
        AUTODB_OFFLINE_TRANSLATE_ENABLED=True,
        AUTODB_OFFLINE_TRANSLATE_URL="http://libretranslate:5000",
        AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS=1000,
    )
    @patch("apps.autodb.services.product_name_translation.urllib_request.urlopen")
    def test_unknown_phrase_uses_offline_translator_when_enabled(self, mocked_urlopen):
        class _FakeResponse:
            def __init__(self, payload: str):
                self._payload = payload.encode("utf-8")

            def read(self):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        responses = iter(
            [
                _FakeResponse('{"translatedText":"Неизвестный товар"}'),
                _FakeResponse('{"translatedText":"Unknown product"}'),
            ]
        )
        mocked_urlopen.side_effect = lambda request, timeout: next(responses)

        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Невідомий товар", source_lang="uk")
        self.assertEqual(result.status, "translated")
        self.assertEqual(result.uk, "Невідомий товар")
        self.assertEqual(result.ru, "Неизвестный товар")
        self.assertEqual(result.en, "Unknown product")

    @override_settings(
        AUTODB_OFFLINE_TRANSLATE_ENABLED=True,
        AUTODB_OFFLINE_TRANSLATE_URL="http://libretranslate:5000",
        AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS=1000,
    )
    @patch("apps.autodb.services.product_name_translation.urllib_request.urlopen")
    def test_offline_translation_preserves_series_tokens_and_normalizes_wiper_name(self, mocked_urlopen):
        class _FakeResponse:
            def __init__(self, payload: str):
                self._payload = payload.encode("utf-8")

            def read(self):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        responses = iter(
            [
                _FakeResponse('{"translatedText":"Вітровий склоочисник щітка __AUTODB_TOKEN_0__"}'),
                _FakeResponse('{"translatedText":"wiper brush __AUTODB_TOKEN_0__"}'),
            ]
        )
        mocked_urlopen.side_effect = lambda request, timeout: next(responses)

        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Щетка стеклоочистителя HYDROCONNECT", source_lang="ru")
        self.assertEqual(result.status, "translated")
        self.assertEqual(result.uk, "Щітка склоочисника HYDROCONNECT")
        self.assertEqual(result.ru, "Щетка стеклоочистителя HYDROCONNECT")
        self.assertEqual(result.en, "Wiper blade HYDROCONNECT")

    @override_settings(
        AUTODB_OFFLINE_TRANSLATE_ENABLED=True,
        AUTODB_OFFLINE_TRANSLATE_URL="http://libretranslate:5000",
        AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS=1000,
    )
    @patch("apps.autodb.services.product_name_translation.urllib_request.urlopen")
    def test_missing_protected_tokens_are_reinjected(self, mocked_urlopen):
        class _FakeResponse:
            def __init__(self, payload: str):
                self._payload = payload.encode("utf-8")

            def read(self):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        responses = iter(
            [
                _FakeResponse('{"translatedText":"Вітровий склоочисник щітка"}'),
                _FakeResponse('{"translatedText":"wiper brush"}'),
            ]
        )
        mocked_urlopen.side_effect = lambda request, timeout: next(responses)

        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Щетка стеклоочистителя FIRST MULTICONNECTION", source_lang="ru")
        self.assertEqual(result.status, "translated")
        self.assertIn("FIRST MULTICONNECTION", result.uk)
        self.assertIn("FIRST MULTICONNECTION", result.ru)
        self.assertIn("FIRST MULTICONNECTION", result.en)
