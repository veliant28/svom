from django.test import TestCase

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ArticleNormalizationRule, ImportSource
from apps.supplier_imports.services import ArticleNormalizerService


class ArticleNormalizerServiceTests(TestCase):
    def setUp(self):
        supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.source = ImportSource.objects.create(
            code="utr",
            name="UTR",
            supplier=supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
        )

    def test_source_rules_are_applied_with_trace(self):
        ArticleNormalizationRule.objects.create(
            source=self.source,
            name="Strip OEM prefix",
            rule_type=ArticleNormalizationRule.RULE_STRIP_PREFIX,
            pattern="OEM-",
            priority=200,
            is_active=True,
        )
        ArticleNormalizationRule.objects.create(
            source=self.source,
            name="Remove separators",
            rule_type=ArticleNormalizationRule.RULE_REMOVE_SEPARATORS,
            priority=100,
            is_active=True,
        )

        result = ArticleNormalizerService().normalize(article="oem- ab-123", source=self.source)

        self.assertEqual(result.normalized_article, "AB123")
        self.assertGreaterEqual(len(result.trace), 2)
        self.assertTrue(any(item.get("step") == "rule" for item in result.trace))
