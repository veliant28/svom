from django.test import SimpleTestCase

from apps.supplier_imports.gpl_article_resolver import GplArticleResolver


class GplArticleResolverTests(SimpleTestCase):
    def test_prefers_tecdoc_article_field(self):
        resolver = GplArticleResolver()
        result = resolver.resolve(
            raw_payload={
                "tecdoc_article": "214082",
                "Артикул ТД": "WP6873",
                "Артикул": "324966",
                "Код": "0000001",
            },
            article="324966",
            external_sku="0000001",
        )
        self.assertEqual(result.manufacturer_article, "214082")
        self.assertEqual(result.article_confidence, "high")
        self.assertEqual(result.article_resolution_status, "resolved")

    def test_prefers_manufacturer_article_field(self):
        resolver = GplArticleResolver()
        result = resolver.resolve(
            raw_payload={
                "Артикул": "324966",
                "Артикул ТД": "WP6873",
                "Код": "0000001",
            },
            article="324966",
            external_sku="0000001",
        )
        self.assertEqual(result.manufacturer_article, "WP6873")
        self.assertEqual(result.supplier_sku, "0000001")
        self.assertEqual(result.article_confidence, "high")
        self.assertEqual(result.article_resolution_status, "resolved")

    def test_falls_back_to_article_when_explicit_field_missing(self):
        resolver = GplArticleResolver()
        result = resolver.resolve(
            raw_payload={"Артикул": "AB-123", "Код": "0000002"},
            article="AB-123",
            external_sku="0000002",
        )
        self.assertEqual(result.manufacturer_article, "AB-123")
        self.assertEqual(result.article_confidence, "medium")
        self.assertEqual(result.article_resolution_status, "resolved")
