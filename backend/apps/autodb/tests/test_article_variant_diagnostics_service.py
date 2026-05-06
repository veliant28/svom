from django.test import SimpleTestCase

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.article_variant_diagnostics import AutoDbArticleVariantDiagnosticsService


class AutoDbArticleVariantDiagnosticsServiceTests(SimpleTestCase):
    def setUp(self):
        self.service = AutoDbArticleVariantDiagnosticsService.__new__(AutoDbArticleVariantDiagnosticsService)
        self.service.article_normalizer = ArticleNumberNormalizer()

    def test_generates_brand_specific_variants(self):
        wix = self.service.generate_lookup_variants(brand="WIX FILTERS", article="WL7042")
        mann = self.service.generate_lookup_variants(brand="MANN-FILTER", article="C 3483/1")
        ngk = self.service.generate_lookup_variants(brand="NGK", article="TR5A-10")
        fram = self.service.generate_lookup_variants(brand="FRAM", article="CA5400")
        ert = self.service.generate_lookup_variants(brand="ERT", article="150675-C")
        woking = self.service.generate_lookup_variants(brand="WOKING", article="P4023.22")

        self.assertIn("WL 7042", wix)
        self.assertIn("WL-7042", wix)

        self.assertIn("C3483-1", mann)
        self.assertIn("C34831", mann)

        self.assertIn("TR5A10", ngk)
        self.assertIn("TR5A 10", ngk)

        self.assertIn("CA 5400", fram)

        self.assertIn("150675C", ert)

        self.assertIn("P402322", woking)
        self.assertIn("P4023-22", woking)

    def test_extract_article_like_tokens_detects_raw_name_evidence(self):
        tokens = self.service.extract_article_like_tokens("Фільтр оливи WIX FILTERS BMW (WL7042) and MANN C 3483/1")

        self.assertIn("WL7042", tokens)

    def test_external_sku_not_blindly_used_for_gpl(self):
        recommendation, reason, confidence = self.service.recommend_from_signals(
            supplier_code="gpl",
            raw_brand="WIX FILTERS",
            core_hit_raw_name=False,
            core_hit_external=True,
            core_hit_variant=False,
            old_new_hit=False,
            any_reference_hit=False,
            external_sku_looks_like_article=True,
            raw_name_confirms_external=False,
            candidate_count=1,
        )

        self.assertEqual(recommendation, "needs_manual_mapping")
        self.assertEqual(reason, "external_sku_unverified_for_gpl")
        self.assertLess(confidence, 0.9)

    def test_old_new_candidate_classified(self):
        recommendation, reason, confidence = self.service.recommend_from_signals(
            supplier_code="gpl",
            raw_brand="SPIDAN",
            core_hit_raw_name=False,
            core_hit_external=False,
            core_hit_variant=False,
            old_new_hit=True,
            any_reference_hit=False,
            external_sku_looks_like_article=False,
            raw_name_confirms_external=False,
            candidate_count=1,
        )

        self.assertEqual(recommendation, "old_new_number_candidate")
        self.assertEqual(reason, "article_m_or_article_nn_candidate")
        self.assertGreaterEqual(confidence, 0.8)
