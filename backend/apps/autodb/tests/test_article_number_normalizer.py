from django.test import SimpleTestCase

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer


class ArticleNumberNormalizerTests(SimpleTestCase):
    def test_generates_search_variants(self):
        result = ArticleNumberNormalizer().normalize("W 712/95")

        self.assertEqual(result.normalized, "W71295")
        self.assertIn("W712/95", result.search_variants)
        self.assertIn("W71295", result.search_variants)
        self.assertIn("W712-95", result.search_variants)

    def test_generates_ngk_like_variants(self):
        result = ArticleNumberNormalizer().normalize("SIFR6A11")

        self.assertIn("SIFR6A11", result.search_variants)
        self.assertIn("SIFR6A-11", result.search_variants)
        self.assertIn("SIFR 6A11", result.search_variants)
        self.assertIn("SIFR 6A-11", result.search_variants)
        self.assertIn("SIFR6A 11", result.search_variants)
