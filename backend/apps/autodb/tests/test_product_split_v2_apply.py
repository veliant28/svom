from __future__ import annotations

from django.test import TestCase

from apps.autodb.services.matching.product_split_v2 import AutoDbProductSplitV2Service
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbProductSplitV2ApplyTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.brand_polmo = Brand.objects.create(name="POLMO", slug="polmo-v2-apply", is_active=True)
        self.brand_febi = Brand.objects.create(name="FEBI BILSTEIN", slug="febi-v2-apply", is_active=True)
        self.category = Category.objects.create(name="Exhaust", slug="exhaust-v2-apply", is_active=True)
        self.product = Product.objects.create(
            sku="000000003538910",
            svom_sku="0S3V5O5M9202",
            article="01.111",
            name="POLMO Exhaust",
            slug="polmo-exhaust-v2-apply",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="POLMO",
            normalized_brand="POLMO",
            autodb_supplier_id=101,
            autodb_supplier_name="FEBI BILSTEIN",
            autodb_article_number="01111",
            autodb_article_key="101:01111",
            is_active=True,
        )
        self.gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.offer_keep = SupplierOffer.objects.create(
            supplier=self.gpl,
            product=self.product,
            supplier_sku="000000003538910",
            currency="UAH",
            purchase_price="2619.00",
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
            purchase_price="138.88",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )
        ProductPrice.objects.create(
            product=self.product,
            currency="UAH",
            purchase_price="2619.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="2619.00",
            raw_sale_price="2880.90",
            final_price="2880.90",
        )
        source_gpl = ImportSource.objects.create(code="gpl-v2-apply", name="GPL v2", supplier=self.gpl, parser_type=ImportSource.PARSER_GPL)
        run_gpl = ImportRun.objects.create(source=source_gpl, status=ImportRun.STATUS_SUCCESS)
        source_utr = ImportSource.objects.create(code="utr-v2-apply", name="UTR v2", supplier=self.utr, parser_type=ImportSource.PARSER_UTR)
        run_utr = ImportRun.objects.create(source=source_utr, status=ImportRun.STATUS_SUCCESS)
        SupplierRawOffer.objects.create(
            run=run_gpl,
            source=source_gpl,
            supplier=self.gpl,
            row_number=1,
            external_sku="000000003538910",
            article="851111",
            normalized_article="851111",
            brand_name="POLMO",
            normalized_brand="POLMO",
            product_name="POLMO Exhaust",
            price="2619.00",
            stock_qty=2,
            lead_time_days=0,
            matched_product=self.product,
            is_valid=True,
            raw_payload={"count_warehouse_1": "2"},
        )
        self.raw_move = SupplierRawOffer.objects.create(
            run=run_utr,
            source=source_utr,
            supplier=self.utr,
            row_number=2,
            external_sku="FE01111",
            article="01111",
            normalized_article="01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI top mount bearing",
            price="138.88",
            stock_qty=0,
            lead_time_days=0,
            matched_product=self.product,
            is_valid=True,
            raw_payload={"warehouse": "0"},
        )
        self.service = AutoDbProductSplitV2Service()

    def test_apply_moves_offer_and_raw_offer_and_creates_new_price(self):
        result = self.service.apply(
            sku="0S3V5O5M9202",
            source_product_id=str(self.product.id),
            moved_offer_ids=[str(self.offer_move.id)],
            moved_raw_offer_ids=[str(self.raw_move.id)],
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
        )

        self.offer_move.refresh_from_db()
        self.raw_move.refresh_from_db()
        self.product.refresh_from_db()
        new_product = Product.objects.get(id=result.new_product_id)
        new_price = ProductPrice.objects.get(id=result.new_productprice_id)

        self.assertEqual(str(self.offer_move.product_id), str(new_product.id))
        self.assertEqual(str(self.raw_move.matched_product_id), str(new_product.id))
        self.assertNotIn("SPLIT", str(new_product.sku).upper())
        self.assertTrue(str(new_product.svom_sku or "").strip())
        self.assertEqual(new_product.display_brand_name, "FEBI BILSTEIN")
        self.assertEqual(int(new_product.autodb_supplier_id or 0), 101)
        self.assertEqual(self.product.display_brand_name, "POLMO")
        self.assertEqual(int(self.product.autodb_supplier_id or 0), 0)
        self.assertEqual(str(self.product.autodb_article_key or ""), "")
        self.assertEqual(new_price.purchase_price, self.offer_move.purchase_price)
