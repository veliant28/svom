from __future__ import annotations

from django.test import TestCase

from apps.autodb.services.matching.product_split_v2_planner import AutoDbProductSplitV2Planner
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbProductSplitV2PlannerTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.brand_polmo = Brand.objects.create(name="POLMO", slug="polmo-v2", is_active=True)
        self.brand_febi = Brand.objects.create(name="FEBI BILSTEIN", slug="febi-v2", is_active=True)
        self.category = Category.objects.create(name="Exhaust", slug="exhaust-v2", is_active=True)
        self.source_product = Product.objects.create(
            sku="000000003538910",
            svom_sku="0S3V5O5M9202",
            article="01.111",
            name="POLMO Exhaust",
            slug="polmo-exhaust-v2",
            brand=self.brand_polmo,
            category=self.category,
            display_brand_name="POLMO",
            normalized_brand="POLMO",
            autodb_supplier_id=101,
            autodb_supplier_name="FEBI BILSTEIN",
            is_active=True,
        )
        self.gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.offer_keep = SupplierOffer.objects.create(
            supplier=self.gpl,
            product=self.source_product,
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
            product=self.source_product,
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
            product=self.source_product,
            currency="UAH",
            purchase_price="2619.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="2619.00",
            raw_sale_price="2880.90",
            final_price="2880.90",
        )

        self.utr_source = ImportSource.objects.create(
            code="utr-v2",
            name="UTR v2",
            supplier=self.utr,
            parser_type=ImportSource.PARSER_UTR,
        )
        self.utr_run = ImportRun.objects.create(source=self.utr_source, status=ImportRun.STATUS_SUCCESS)
        SupplierRawOffer.objects.create(
            run=self.utr_run,
            source=self.utr_source,
            supplier=self.utr,
            row_number=1,
            external_sku="FE01111",
            article="01111",
            normalized_article="01111",
            brand_name="FEBI BILSTEIN",
            normalized_brand="FEBIBILSTEIN",
            product_name="FEBI top mount bearing",
            price="138.88",
            stock_qty=0,
            lead_time_days=0,
            matched_product=self.source_product,
            is_valid=True,
            raw_payload={"warehouse": "0"},
        )
        self.planner = AutoDbProductSplitV2Planner()

    def test_plan_contains_raw_offer_and_productprice_strategy_without_split_suffix(self):
        before_counts = {
            "product": Product.objects.count(),
            "offer": SupplierOffer.objects.count(),
            "raw": SupplierRawOffer.objects.count(),
            "price": ProductPrice.objects.count(),
        }
        plan = self.planner.plan(
            sku="0S3V5O5M9202",
            source_product_id=str(self.source_product.id),
            moved_offer_ids=[str(self.offer_move.id)],
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
        )
        after_counts = {
            "product": Product.objects.count(),
            "offer": SupplierOffer.objects.count(),
            "raw": SupplierRawOffer.objects.count(),
            "price": ProductPrice.objects.count(),
        }

        self.assertTrue(plan.sku_strategy_known)
        self.assertNotIn("SPLIT", plan.proposed_internal_sku.upper())
        self.assertIn(str(self.offer_move.id), plan.offers_to_move)
        self.assertTrue(plan.raw_offers_to_move)
        self.assertEqual(plan.source_productprice_ids and len(plan.source_productprice_ids), 1)
        self.assertTrue(plan.productprice_actions)
        self.assertEqual(plan.source_display_brand_after, "POLMO")
        self.assertEqual(plan.new_display_brand_after, "FEBI BILSTEIN")
        self.assertEqual(before_counts, after_counts)

    def test_existing_inactive_split_with_price_blocks_dry_run(self):
        split_product = Product.objects.create(
            sku="000000003538910-SPLIT-OLD",
            article="01111",
            name="Old split",
            slug="old-split-v2",
            brand=self.brand_febi,
            category=self.category,
            is_active=False,
        )
        ProductPrice.objects.create(
            product=split_product,
            currency="UAH",
            purchase_price="100.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="100.00",
            raw_sale_price="110.00",
            final_price="120.00",
        )

        plan = self.planner.plan(
            sku="0S3V5O5M9202",
            source_product_id=str(self.source_product.id),
            moved_offer_ids=[str(self.offer_move.id)],
            keep_group="POLMO|01111",
            move_group="FEBIBILSTEIN|01111",
        )

        self.assertFalse(plan.clean)
        self.assertIn("existing_inactive_split_product_cleanup_needed", plan.blockers)
        self.assertIn("productprice_relation_ambiguous_existing_split_product", plan.blockers)
