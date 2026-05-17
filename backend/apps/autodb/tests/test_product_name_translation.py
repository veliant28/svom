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

    @override_settings(
        AUTODB_OFFLINE_TRANSLATE_ENABLED=True,
        AUTODB_OFFLINE_TRANSLATE_URL="http://libretranslate:5000",
        AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS=1000,
    )
    @patch("apps.autodb.services.product_name_translation.urllib_request.urlopen")
    def test_translated_placeholder_artifacts_are_restored(self, mocked_urlopen):
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
                _FakeResponse('{"translatedText":"AutoDB TOKEN 0 АВТОДБ TOKEN 1st X-line 99"}'),
                _FakeResponse('{"translatedText":"AUTODB TOKEN 0 AUTODB TOKEN 1st X-line 99"}'),
            ]
        )
        mocked_urlopen.side_effect = lambda request, timeout: next(responses)

        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Тестовая свеча X-line 99", source_lang="ru")
        self.assertEqual(result.status, "translated")
        self.assertEqual(result.ru, "Тестовая свеча X-line 99")
        self.assertEqual(result.uk, "X-line 99")
        self.assertEqual(result.en, "X-line 99")
        self.assertNotIn("AUTODB TOKEN", result.uk.upper())
        self.assertNotIn("AUTODB TOKEN", result.en.upper())

    @override_settings(
        AUTODB_OFFLINE_TRANSLATE_ENABLED=True,
        AUTODB_OFFLINE_TRANSLATE_URL="http://libretranslate:5000",
        AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS=1000,
    )
    @patch("apps.autodb.services.product_name_translation.urllib_request.urlopen")
    def test_compact_placeholder_artifacts_are_restored(self, mocked_urlopen):
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
                _FakeResponse('{"translatedText":"Свічка запалювання @AUTODB0@@AUTODB1@ A-line 14"}'),
                _FakeResponse('{"translatedText":"Ignition candle @AUTODB0@@@14@ A-line"}'),
            ]
        )
        mocked_urlopen.side_effect = lambda request, timeout: next(responses)

        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Свеча зажигания A-line 14", source_lang="ru")
        self.assertEqual(result.status, "translated")
        self.assertNotIn("AUTODB", result.uk.upper())
        self.assertNotIn("AUTODB", result.en.upper())

    @override_settings(
        AUTODB_OFFLINE_TRANSLATE_ENABLED=True,
        AUTODB_OFFLINE_TRANSLATE_URL="http://libretranslate:5000",
        AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS=1000,
    )
    @patch("apps.autodb.services.product_name_translation.urllib_request.urlopen")
    def test_glued_placeholder_artifacts_are_restored(self, mocked_urlopen):
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
                _FakeResponse('{"translatedText":"Свічка запалювання A-lineAUTODB1@ 12"}'),
                _FakeResponse('{"translatedText":"Ignition candle A-line12@"}'),
            ]
        )
        mocked_urlopen.side_effect = lambda request, timeout: next(responses)

        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Свеча зажигания A-line 12", source_lang="ru")
        self.assertEqual(result.status, "translated")
        self.assertIn("A-line 12", result.uk)
        self.assertIn("A-line 12", result.en)
        self.assertNotIn("AUTODB", result.uk.upper())
        self.assertNotIn("AUTODB", result.en.upper())

    @override_settings(
        AUTODB_OFFLINE_TRANSLATE_ENABLED=True,
        AUTODB_OFFLINE_TRANSLATE_URL="http://libretranslate:5000",
        AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS=1000,
    )
    @patch("apps.autodb.services.product_name_translation.urllib_request.urlopen")
    def test_latin_suffix_is_preserved_when_headword_is_known(self, mocked_urlopen):
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
                _FakeResponse('{"translatedText":"Шоктейлер MONROE ORIGINAL (Технології га)"}'),
                _FakeResponse('{"translatedText":"Shock absorber MONROE ORIGINAL (Gas Technology)"}'),
            ]
        )
        mocked_urlopen.side_effect = lambda request, timeout: next(responses)

        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="Амортизатор MONROE ORIGINAL (Gas Technology)", source_lang="ru")
        self.assertEqual(result.status, "translated")
        self.assertEqual(result.uk, "Амортизатор MONROE ORIGINAL (Gas Technology)")
        self.assertEqual(result.ru, "Амортизатор MONROE ORIGINAL (Gas Technology)")
        self.assertEqual(result.en, "Shock absorber MONROE ORIGINAL (Gas Technology)")

    @override_settings(AUTODB_OFFLINE_TRANSLATE_ENABLED=False)
    def test_dictionary_overrides_batch_problematic_phrases(self):
        service = ProductNameTranslationService()
        cases = [
            (
                "Прокладка, труба выхлопного газа",
                "Прокладка, труба вихлопного газу",
                "Прокладка, труба выхлопного газа",
                "Exhaust pipe gasket",
            ),
            (
                "Трубка Труба выхлопного газа",
                "Труба вихлопного газу",
                "Труба выхлопного газа",
                "Exhaust pipe",
            ),
            (
                "Ремонтний комплект зчеплення",
                "Ремкомплект зчеплення",
                "Ремкомплект сцепления",
                "Clutch repair kit",
            ),
            (
                "Поликлиновой ремень",
                "Поліклиновий ремінь",
                "Поликлиновой ремень",
                "Poly-V belt",
            ),
            (
                "Несущий / направляющий шарнир",
                "Несучий / напрямний шарнір",
                "Несущий / направляющий шарнир",
                "Support / guide joint",
            ),
            (
                "Уплотняющее кольцо, коленчатый вал",
                "Ущільнювальне кільце, колінчастий вал",
                "Уплотняющее кольцо, коленчатый вал",
                "Sealing ring, crankshaft",
            ),
            (
                "Подшипник Опора стойки амортизатора",
                "Підшипник, опора стійки амортизатора",
                "Подшипник, опора стойки амортизатора",
                "Strut mount bearing",
            ),
            (
                "Датчик Лямбда-зонд",
                "Датчик лямбда-зонд",
                "Датчик лямбда-зонд",
                "Lambda sensor",
            ),
            (
                "Поликлиновой ремень Micro-V®",
                "Поліклиновий ремінь Micro-V®",
                "Поликлиновой ремень Micro-V®",
                "Poly-V belt Micro-V®",
            ),
            (
                "Патрубок радіатора",
                "Патрубок радіатора",
                "Патрубок радиатора",
                "Radiator hose",
            ),
            (
                "Комплект тормозных колодок, дисковый тормоз",
                "Комплект гальмівних колодок, дискове гальмо",
                "Комплект тормозных колодок, дисковый тормоз",
                "Set of brake pads, disc brake",
            ),
            (
                "Датчик Лямбда-зонд Direct Fit",
                "Датчик лямбда-зонд Direct Fit",
                "Датчик лямбда-зонд Direct Fit",
                "Lambda sensor Direct Fit",
            ),
        ]
        for source_text, expected_uk, expected_ru, expected_en in cases:
            result = service.translate_product_name(source_text=source_text)
            self.assertEqual(result.status, "translated")
            self.assertEqual(result.uk, expected_uk)
            self.assertEqual(result.ru, expected_ru)
            self.assertEqual(result.en, expected_en)

    @override_settings(AUTODB_OFFLINE_TRANSLATE_ENABLED=False)
    def test_english_cyrillic_terms_are_normalized(self):
        service = ProductNameTranslationService()
        result = service.translate_product_name(source_text="ШРКШ внутрішній правий ВАЗ довгий ЗІЛ CV 16023")
        self.assertEqual(result.status, "pending")
        self.assertIn("VAZ", result.en)
        self.assertIn("ZIL", result.en)
        self.assertIn("long", result.en.lower())
