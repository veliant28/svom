from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Product
from apps.pricing.models import Supplier, SupplierOffer


class RecalculateProductOfferCacheCommandTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.supplier = Supplier.objects.create(name="Supplier", code="supplier", is_active=True)
        self.product_a = Product.objects.create(
            sku="SKU-A",
            article="ART-A",
            name="Product A",
            slug="product-a",
            brand=self.brand,
            is_active=True,
            available_stock_qty_cached=0,
        )
        self.product_b = Product.objects.create(
            sku="SKU-B",
            article="ART-B",
            name="Product B",
            slug="product-b",
            brand=self.brand,
            is_active=True,
            available_stock_qty_cached=3,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product_a,
            supplier_sku="A-1",
            purchase_price="100.00",
            stock_qty=4,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product_b,
            supplier_sku="B-1",
            purchase_price="100.00",
            stock_qty=6,
            is_available=True,
        )

    def test_dry_run_does_not_persist_cache(self):
        out = StringIO()
        call_command("recalculate_product_offer_cache", "--dry-run", stdout=out)
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()

        self.assertEqual(self.product_a.available_stock_qty_cached, 0)
        self.assertEqual(self.product_b.available_stock_qty_cached, 3)
        output = out.getvalue()
        self.assertIn("- processed: 2", output)
        self.assertIn("- updated: 2", output)
        self.assertIn("- total_stock_before: 3", output)
        self.assertIn("- total_stock_after: 10", output)

    def test_real_run_updates_cache_and_repeat_is_idempotent(self):
        first_out = StringIO()
        call_command("recalculate_product_offer_cache", stdout=first_out)

        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.available_stock_qty_cached, 4)
        self.assertEqual(self.product_b.available_stock_qty_cached, 6)

        second_out = StringIO()
        call_command("recalculate_product_offer_cache", "--dry-run", stdout=second_out)
        output = second_out.getvalue()
        self.assertIn("- updated: 0", output)
        self.assertIn("- skipped_unchanged: 2", output)
