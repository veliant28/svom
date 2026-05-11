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

    def test_canonical_compacts_spacing_and_homoglyphs(self):
        normalizer = ArticleNumberNormalizer()

        a = normalizer.normalize("4PK813")
        b = normalizer.normalize("4 PK 813")
        c = normalizer.normalize("4 РК 813")
        d = normalizer.normalize("4PK 813")

        self.assertEqual(a.normalized, "4PK813")
        self.assertEqual(a.normalized, b.normalized)
        self.assertEqual(a.normalized, c.normalized)
        self.assertEqual(a.normalized, d.normalized)
        self.assertIn("4 PK 813", a.search_variants)
        self.assertIn("4 РК 813", a.search_variants)

    def test_no_empty_normalized_for_regular_article(self):
        result = ArticleNumberNormalizer().normalize("BOSCH-0 986 452 500")

        self.assertEqual(result.normalized, "BOSCH0986452500")
