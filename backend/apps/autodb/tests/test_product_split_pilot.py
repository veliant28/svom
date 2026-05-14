from __future__ import annotations

from django.test import TestCase

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.autodb.services.matching.product_split_pilot import AutoDbProductSplitPilotService
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer


class AutoDbProductSplitPilotServiceTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.brand_polmo = Brand.objects.create(name="POLMO", slug="brand-polmo", is_active=True)
        self.brand_febi = Brand.objects.create(name="FEBI BILSTEIN", slug="brand-febi", is_active=True)
        self.category = Category.objects.create(name="Exhaust", slug="cat-exhaust", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-SPLIT-1",
            svom_sku="SVOM-SPLIT-1",
            article="01111",
            name="POLMO Exhaust 01111",
            slug="polmo-exhaust-01111",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="FEBI BILSTEIN",
            autodb_supplier_id=101,
            autodb_supplier_name="FEBI BILSTEIN",
            autodb_article_key="101:01111",
            autodb_article_number="01111",
            is_active=True,
        )
        self.gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.offer_keep = SupplierOffer.objects.create(
            supplier=self.gpl,
            product=self.product,
            supplier_sku="SKU-SPLIT-1",
            currency="UAH",
            purchase_price="2000.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=2,
            lead_time_days=0,
            is_available=True,
        )
        self.offer_move = SupplierOffer.objects.create(
            supplier=self.utr,
            product=self.product,
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=1,
            lead_time_days=0,
            is_available=True,
        )
        ProductPrice.objects.create(
            product=self.product,
            currency="UAH",
            purchase_price="2000.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="2000.00",
            raw_sale_price="2200.00",
            final_price="2400.00",
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.product,
            autodb_article_key="101:01111",
            autodb_supplier_id=101,
            autodb_article_number="01111",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="test",
            evidence={},
        )
        self.service = AutoDbProductSplitPilotService()

    def test_plan_is_clean_for_single_moved_offer(self):
        plan = self.service.plan(
            sku="SVOM-SPLIT-1",
            moved_offer_ids=[str(self.offer_move.id)],
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
        )
        self.assertTrue(plan.clean)
        self.assertEqual(plan.source_product_id, str(self.product.id))
        self.assertEqual(plan.proposed_new_brand_name, "FEBI BILSTEIN")
        self.assertEqual(plan.proposed_new_autodb_supplier_id, 101)

    def test_apply_moves_offer_and_creates_new_product(self):
        before_products = Product.objects.count()
        before_offers = SupplierOffer.objects.count()
        before_prices = ProductPrice.objects.count()
        before_jobs = AutoDbMatchJob.objects.count()
        before_evidence = AutoDbMatchEvidence.objects.count()

        result = self.service.apply(
            sku="SVOM-SPLIT-1",
            moved_offer_ids=[str(self.offer_move.id)],
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
        )

        self.assertEqual(Product.objects.count(), before_products + 1)
        self.assertEqual(SupplierOffer.objects.count(), before_offers)
        self.assertEqual(ProductPrice.objects.count(), before_prices)
        self.assertEqual(AutoDbMatchJob.objects.count(), before_jobs + 2)
        self.assertEqual(AutoDbMatchEvidence.objects.count(), before_evidence + 2)

        self.offer_move.refresh_from_db()
        self.offer_keep.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(str(self.offer_keep.product_id), str(self.product.id))
        self.assertEqual(str(self.offer_move.product_id), result.new_product_id)
        self.assertEqual(self.product.display_brand_name, "POLMO")

        new_product = Product.objects.get(id=result.new_product_id)
        self.assertEqual(new_product.display_brand_name, "FEBI BILSTEIN")
        self.assertEqual(int(new_product.autodb_supplier_id or 0), 101)
        self.assertEqual(result.productprice_action, "no_reassign_no_recreate")

