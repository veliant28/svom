from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer


class RepairGplProductPublicVisibilityCommandTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="TEST", slug="test", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True, is_assignable=True)
        self.gpl_supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.other_supplier = Supplier.objects.create(name="OTHER", code="other", is_active=True)

    def test_dry_run_does_not_write(self):
        product = Product.objects.create(
            sku="GPL-001",
            article="A-001",
            name="GPL Product",
            slug="gpl-product",
            brand=self.brand,
            category=self.category,
            is_active=False,
            published_at=None,
            available_stock_qty_cached=0,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl_supplier,
            product=product,
            supplier_sku="A-001",
            currency="UAH",
            purchase_price="100.00",
            stock_qty=7,
            is_available=True,
        )
        out = StringIO()
        call_command("repair_gpl_product_public_visibility", "--dry-run", stdout=out)

        product.refresh_from_db()
        self.assertFalse(product.is_active)
        self.assertIsNone(product.published_at)
        self.assertEqual(product.available_stock_qty_cached, 0)
        self.assertIn("skipped_price_guard_publish: 1", out.getvalue())

    def test_apply_updates_stock_cache_without_forcing_active_or_published(self):
        gpl_product = Product.objects.create(
            sku="GPL-002",
            article="A-002",
            name="GPL Product 2",
            slug="gpl-product-2",
            brand=self.brand,
            category=self.category,
            is_active=False,
            published_at=None,
            available_stock_qty_cached=0,
        )
        other_product = Product.objects.create(
            sku="OTH-001",
            article="B-001",
            name="Other Product",
            slug="other-product",
            brand=self.brand,
            category=self.category,
            is_active=False,
            published_at=None,
            available_stock_qty_cached=0,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl_supplier,
            product=gpl_product,
            supplier_sku="A-002",
            currency="UAH",
            purchase_price="110.00",
            stock_qty=9,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=self.other_supplier,
            product=other_product,
            supplier_sku="B-001",
            currency="UAH",
            purchase_price="120.00",
            stock_qty=12,
            is_available=True,
        )

        before_name = gpl_product.name
        before_category_id = gpl_product.category_id
        call_command("repair_gpl_product_public_visibility")

        gpl_product.refresh_from_db()
        other_product.refresh_from_db()

        self.assertFalse(gpl_product.is_active)
        self.assertIsNone(gpl_product.published_at)
        self.assertEqual(gpl_product.available_stock_qty_cached, 9)
        self.assertEqual(gpl_product.name, before_name)
        self.assertEqual(gpl_product.category_id, before_category_id)

        self.assertFalse(other_product.is_active)
        self.assertIsNone(other_product.published_at)
        self.assertEqual(other_product.available_stock_qty_cached, 0)
