from __future__ import annotations

from django.test import TestCase

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.autodb.services.matching.product_split_rollback import AutoDbProductSplitRollbackService
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbProductSplitRollbackServiceTests(TestCase):
    databases = {"default"}

    def setUp(self):
        brand_polmo = Brand.objects.create(name="POLMO", slug="brand-polmo-rollback", is_active=True)
        brand_febi = Brand.objects.create(name="FEBI BILSTEIN", slug="brand-febi-rollback", is_active=True)
        category = Category.objects.create(name="Exhaust", slug="cat-exhaust-rollback", is_active=True)
        self.source = Product.objects.create(
            sku="SKU-ROLLBACK-1",
            svom_sku="SVOM-ROLLBACK-1",
            article="01111",
            name="POLMO Exhaust",
            slug="polmo-exhaust-rollback",
            brand=brand_polmo,
            category=category,
            display_brand_name="POLMO",
            autodb_supplier_id=101,
            autodb_supplier_name="FEBI BILSTEIN",
            is_active=True,
        )
        self.split = Product.objects.create(
            sku="SKU-ROLLBACK-1-SPLIT",
            article="01111",
            name="FEBI part",
            slug="febi-part-rollback",
            brand=brand_febi,
            category=category,
            display_brand_name="FEBI BILSTEIN",
            autodb_supplier_id=101,
            autodb_supplier_name="FEBI BILSTEIN",
            is_active=True,
        )
        gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.offer_source = SupplierOffer.objects.create(
            supplier=gpl,
            product=self.source,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="2000.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=1,
            lead_time_days=0,
            is_available=True,
        )
        self.offer_moved = SupplierOffer.objects.create(
            supplier=utr,
            product=self.split,
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        self.source_price = ProductPrice.objects.create(
            product=self.source,
            currency="UAH",
            purchase_price="2000.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="2000.00",
            raw_sale_price="2100.00",
            final_price="2200.00",
        )
        self.split_price = ProductPrice.objects.create(
            product=self.split,
            currency="UAH",
            purchase_price="100.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="100.00",
            raw_sale_price="100.00",
            final_price="100.00",
        )
        self.utr_source = ImportSource.objects.create(
            code="utr-rollback-source",
            name="UTR rollback source",
            supplier=utr,
            parser_type=ImportSource.PARSER_UTR,
            is_active=True,
        )
        self.utr_run = ImportRun.objects.create(source=self.utr_source, status=ImportRun.STATUS_SUCCESS, trigger="test")
        self.raw_source = SupplierRawOffer.objects.create(
            run=self.utr_run,
            source=self.utr_source,
            supplier=utr,
            external_sku="POLMO01111",
            article="01111",
            normalized_article="01111",
            brand_name="POLMO",
            normalized_brand="POLMO",
            product_name="POLMO Exhaust",
            currency="UAH",
            price="2000.00",
            stock_qty=1,
            matched_product=self.source,
            is_valid=True,
        )
        self.raw_moved = SupplierRawOffer.objects.create(
            run=self.utr_run,
            source=self.utr_source,
            supplier=utr,
            external_sku="FE01111",
            article="FE01111",
            normalized_article="FE01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI Part",
            currency="UAH",
            price="100.00",
            stock_qty=0,
            matched_product=self.split,
            is_valid=True,
        )
        self.service = AutoDbProductSplitRollbackService()

    def test_plan_and_apply(self):
        plan = self.service.plan(
            source_product_id=str(self.source.id),
            split_product_id=str(self.split.id),
            moved_offer_ids=[str(self.offer_moved.id)],
            moved_raw_offer_ids=[str(self.raw_moved.id)],
            split_productprice_ids=[str(self.split_price.id)],
        )
        self.assertTrue(plan.clean)
        self.assertEqual(plan.moved_offer_ids_on_split, (str(self.offer_moved.id),))
        self.assertEqual(plan.moved_raw_offer_ids_on_split, (str(self.raw_moved.id),))
        self.assertEqual(plan.split_productprice_ids_on_split, (str(self.split_price.id),))
        self.assertEqual(plan.recommended_split_product_action, "delete")

        before_jobs = AutoDbMatchJob.objects.count()
        before_evidence = AutoDbMatchEvidence.objects.count()
        result = self.service.apply(
            source_product_id=str(self.source.id),
            split_product_id=str(self.split.id),
            moved_offer_ids=[str(self.offer_moved.id)],
            moved_raw_offer_ids=[str(self.raw_moved.id)],
            split_productprice_ids=[str(self.split_price.id)],
        )

        self.offer_moved.refresh_from_db()
        self.raw_moved.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(str(self.offer_moved.product_id), str(self.source.id))
        self.assertEqual(str(self.raw_moved.matched_product_id), str(self.source.id))
        self.assertFalse(Product.objects.filter(id=self.split.id).exists())
        self.assertEqual(result.moved_offer_ids_restored, (str(self.offer_moved.id),))
        self.assertEqual(result.moved_raw_offer_ids_restored, (str(self.raw_moved.id),))
        self.assertEqual(result.split_productprice_ids_removed, (str(self.split_price.id),))
        self.assertEqual(self.source.display_brand_name, self.source.brand.name)
        self.assertIsNone(self.source.autodb_supplier_id)
        self.assertFalse(ProductPrice.objects.filter(id=self.split_price.id).exists())
        self.assertTrue(ProductPrice.objects.filter(id=self.source_price.id).exists())
        self.assertEqual(result.split_product_action, "delete")
        self.assertEqual(AutoDbMatchJob.objects.count(), before_jobs + 1)
        self.assertEqual(AutoDbMatchEvidence.objects.count(), before_evidence + 1)
