from django.test import TestCase

from apps.pricing.models import Supplier
from apps.catalog.models import Brand, Category, Product
from apps.supplier_imports.models import ImportSource, SupplierRawOffer
from apps.supplier_imports.services.normalization import ArticleNormalizerService, BrandAliasResolverService
from apps.supplier_imports.services.matching import OfferMatcher
from apps.supplier_imports.services.matching.product_index import ProductMatchIndex


class OfferMatcherServiceTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.source = ImportSource.objects.create(
            code="utr",
            name="UTR",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
        )
        brand = Brand.objects.create(name="ARAL", slug="aral", is_active=True)
        category = Category.objects.create(name="Oils", slug="oils", is_active=True)
        self.product = Product.objects.create(
            sku="AR-20488",
            article="AR-20488",
            name="Aral BlueTronic 10W-40 1Lx12",
            slug="aral-bluetronic-10w40-1l",
            brand=brand,
            category=category,
            is_active=True,
        )

    def test_exact_match_returns_auto_matched(self):
        decision = OfferMatcher().evaluate(article="AR-20488", external_sku="0007523", brand_name="ARAL")

        self.assertEqual(decision.status, SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)
        self.assertEqual(decision.reason, "")
        self.assertIsNotNone(decision.matched_product)
        self.assertEqual(decision.matched_product.id, self.product.id)

    def test_ambiguous_match_detected_as_manual_required(self):
        duplicate = Product.objects.create(
            sku="AR-20488-X",
            article="AR-20488",
            name="Another ARAL",
            slug="another-aral",
            brand=self.product.brand,
            category=self.product.category,
            is_active=True,
        )
        _ = duplicate

        decision = OfferMatcher().evaluate(article="AR-20488", external_sku="", brand_name="ARAL")

        self.assertEqual(decision.status, SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED)
        self.assertEqual(decision.reason, SupplierRawOffer.MATCH_REASON_AMBIGUOUS)
        self.assertIsNone(decision.matched_product)
        self.assertGreaterEqual(len(decision.candidate_products), 2)

    def test_specific_external_sku_resolves_duplicate_article(self):
        duplicate = Product.objects.create(
            sku="AR-20488-X",
            article="AR-20488",
            name="Another ARAL",
            slug="another-aral",
            brand=self.product.brand,
            category=self.product.category,
            is_active=True,
        )

        decision = OfferMatcher().evaluate(article="AR-20488", external_sku="AR-20488-X", brand_name="ARAL")

        self.assertEqual(decision.status, SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)
        self.assertEqual(decision.reason, "")
        self.assertIsNotNone(decision.matched_product)
        self.assertEqual(decision.matched_product.id, duplicate.id)

    def test_equivalent_duplicate_article_formatting_auto_matches_canonical(self):
        brand = Brand.objects.create(name="CONTINENTAL", slug="continental", is_active=True)
        category = Category.objects.create(name="Belts", slug="belts", is_active=True)
        Product.objects.create(
            sku="6PK1502 EXTRA",
            article="6PK1502 EXTRA",
            name="Drive belt spaced",
            slug="drive-belt-spaced",
            brand=brand,
            category=category,
            is_active=False,
        )
        compact = Product.objects.create(
            sku="6PK1502EXTRA",
            article="6PK1502EXTRA",
            name="Drive belt compact",
            slug="drive-belt-compact",
            brand=brand,
            category=category,
            is_active=False,
        )

        for article, external_sku in (
            ("6PK1502 EXTRA", "6PK1502 EXTRA"),
            ("6PK1502EXTRA", "6PK1502EXTRA"),
        ):
            decision = OfferMatcher().evaluate(
                article=article,
                external_sku=external_sku,
                brand_name="CONTINENTAL",
            )

            self.assertEqual(decision.status, SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)
            self.assertEqual(decision.reason, "")
            self.assertIsNotNone(decision.matched_product)
            self.assertEqual(decision.matched_product.id, compact.id)

    def test_injected_normalizers_keep_cache_across_evaluations(self):
        article_normalizer = ArticleNormalizerService()
        brand_resolver = BrandAliasResolverService()
        matcher = OfferMatcher(article_normalizer=article_normalizer, brand_resolver=brand_resolver)

        for _ in range(2):
            decision = matcher.evaluate(
                article="AR-20488",
                external_sku="",
                brand_name="ARAL",
                source=self.source,
                supplier=self.supplier,
            )
            self.assertEqual(decision.status, SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)

        stats = matcher.cache_stats()
        self.assertGreaterEqual(stats["article_normalizer"].get("rules_cache_hits", 0), 1)
        self.assertGreaterEqual(stats["article_normalizer"].get("result_cache_hits", 0), 1)
        self.assertGreaterEqual(stats["brand_resolver"].get("alias_cache_hits", 0), 1)

    def test_lightweight_product_index_matches_with_fk_ids(self):
        matcher = OfferMatcher(index=ProductMatchIndex(lightweight_products=True))

        decision = matcher.evaluate(article="AR-20488", external_sku="", brand_name="ARAL")

        self.assertEqual(decision.status, SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)
        self.assertIsNotNone(decision.matched_product)
        self.assertEqual(decision.matched_product.id, self.product.id)
        self.assertEqual(decision.matched_product.brand_id, self.product.brand_id)
        self.assertEqual(decision.matched_product.category_id, self.product.category_id)

    def test_lightweight_product_instance_save_update_fields_does_not_insert(self):
        matcher = OfferMatcher(index=ProductMatchIndex(lightweight_products=True))
        decision = matcher.evaluate(article="AR-20488", external_sku="", brand_name="ARAL")

        self.assertIsNotNone(decision.matched_product)
        matched = decision.matched_product
        matched.category = self.product.category
        matched.save(update_fields=("category", "updated_at"))

        self.assertEqual(Product.objects.filter(id=self.product.id).count(), 1)
