from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services.matching import OfferMatcher


class OfferMatcherServiceTests(TestCase):
    def setUp(self):
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
