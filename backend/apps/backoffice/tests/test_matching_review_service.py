from decimal import Decimal

from django.test import TestCase

from apps.backoffice.services import MatchingReviewService
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User


class MatchingReviewServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="matcher@test.local",
            username="matcher",
            password="demo12345",
            is_staff=True,
        )
        self.brand = Brand.objects.create(name="ARAL", slug="aral", is_active=True)
        self.category = Category.objects.create(name="Oils", slug="oils", is_active=True)
        self.product = Product.objects.create(
            sku="AR-20488",
            article="AR-20488",
            name="Aral BlueTronic 10W-40 1Lx12",
            slug="aral-bluetronic-10w40-1l",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test")

    def test_manual_confirm_match_sets_manually_matched_and_syncs_supplier_offer(self):
        raw_offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="0001",
            article="AR-20488",
            normalized_article="AR20488",
            brand_name="ARAL",
            normalized_brand="ARAL",
            product_name="Aral",
            currency="UAH",
            price=Decimal("120.00"),
            stock_qty=5,
            match_status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED,
            match_reason=SupplierRawOffer.MATCH_REASON_AMBIGUOUS,
            is_valid=False,
            skip_reason="ambiguous_match",
        )

        result = MatchingReviewService().confirm_match(raw_offer=raw_offer, product=self.product, actor=self.user)

        raw_offer.refresh_from_db()
        self.assertEqual(raw_offer.match_status, SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED)
        self.assertEqual(raw_offer.matched_product_id, self.product.id)
        self.assertEqual(raw_offer.matched_manually_by_id, self.user.id)
        self.assertEqual(raw_offer.is_valid, True)
        self.assertEqual(raw_offer.skip_reason, "")
        self.assertEqual(result["synced_supplier_offer"], True)
        self.assertTrue(SupplierOffer.objects.filter(supplier=self.supplier, product=self.product, supplier_sku="0001").exists())

    def test_ignore_flow_marks_offer_as_ignored(self):
        raw_offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="no-match",
            article="UNKNOWN",
            normalized_article="UNKNOWN",
            brand_name="X",
            normalized_brand="X",
            product_name="Unknown",
            currency="UAH",
            price=Decimal("100.00"),
            stock_qty=1,
            match_status=SupplierRawOffer.MATCH_STATUS_UNMATCHED,
            match_reason=SupplierRawOffer.MATCH_REASON_ARTICLE_CONFLICT,
            is_valid=False,
            skip_reason="article_conflict",
        )

        result = MatchingReviewService().ignore_offer(raw_offer=raw_offer, actor=self.user)

        raw_offer.refresh_from_db()
        self.assertEqual(result["status"], SupplierRawOffer.MATCH_STATUS_IGNORED)
        self.assertEqual(raw_offer.match_status, SupplierRawOffer.MATCH_STATUS_IGNORED)
        self.assertEqual(raw_offer.is_valid, False)
        self.assertEqual(raw_offer.skip_reason, "ignored")
        self.assertIsNotNone(raw_offer.ignored_at)
