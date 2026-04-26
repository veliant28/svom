from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.pricing.services import ProductRepricer, sync_products_activity_by_price_freshness
from apps.pricing.tasks.sync_product_activity import sync_products_activity_by_price_freshness_task


class ProductActivitySyncTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Activity Brand", slug="activity-brand", is_active=True)
        self.category = Category.objects.create(name="Activity Category", slug="activity-category", is_active=True)
        self.supplier = Supplier.objects.create(
            name="Activity Supplier",
            code="activity-supplier",
            is_active=True,
            is_preferred=True,
            priority=1,
            quality_score="9.00",
        )
        self._counter = 0

    def _create_product(self, *, is_active: bool, prefix: str) -> Product:
        self._counter += 1
        suffix = f"{self._counter:03d}"
        return Product.objects.create(
            sku=f"{prefix}-{suffix}",
            article=f"{prefix}-{suffix}",
            name=f"{prefix} Product {suffix}",
            slug=f"{prefix.lower()}-product-{suffix}",
            brand=self.brand,
            category=self.category,
            is_active=is_active,
        )

    def test_sync_deactivates_products_with_stale_or_missing_price(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        stale_product = self._create_product(is_active=True, prefix="STALE")
        stale_price = ProductPrice.objects.create(product=stale_product, final_price="150.00", currency="UAH")
        ProductPrice.objects.filter(id=stale_price.id).update(updated_at=now - timedelta(hours=26))

        missing_price_product = self._create_product(is_active=True, prefix="MISSING")

        fresh_product = self._create_product(is_active=True, prefix="FRESH")
        fresh_price = ProductPrice.objects.create(product=fresh_product, final_price="199.00", currency="UAH")
        ProductPrice.objects.filter(id=fresh_price.id).update(updated_at=now - timedelta(hours=1))

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        stale_product.refresh_from_db()
        missing_price_product.refresh_from_db()
        fresh_product.refresh_from_db()

        self.assertEqual(result.deactivated, 2)
        self.assertFalse(stale_product.is_active)
        self.assertFalse(missing_price_product.is_active)
        self.assertTrue(fresh_product.is_active)

    def test_sync_activates_inactive_products_with_fresh_price(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        inactive_with_fresh_price = self._create_product(is_active=False, prefix="REACTIVATE")
        fresh_price = ProductPrice.objects.create(
            product=inactive_with_fresh_price,
            final_price="210.00",
            currency="UAH",
        )
        ProductPrice.objects.filter(id=fresh_price.id).update(updated_at=now - timedelta(hours=2))

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        inactive_with_fresh_price.refresh_from_db()
        self.assertEqual(result.activated, 1)
        self.assertTrue(inactive_with_fresh_price.is_active)

    def test_sync_zeroes_stale_offers_for_deactivated_products(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        stale_product = self._create_product(is_active=True, prefix="STALE-STOCK")
        stale_price = ProductPrice.objects.create(product=stale_product, final_price="140.00", currency="UAH")
        ProductPrice.objects.filter(id=stale_price.id).update(updated_at=now - timedelta(hours=30))

        stale_offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=stale_product,
            supplier_sku=f"SUP-{stale_product.sku}",
            purchase_price="100.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=9,
            lead_time_days=2,
            is_available=True,
        )
        SupplierOffer.objects.filter(id=stale_offer.id).update(updated_at=now - timedelta(hours=30))

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        stale_product.refresh_from_db()
        stale_offer.refresh_from_db()

        self.assertFalse(stale_product.is_active)
        self.assertEqual(stale_offer.stock_qty, 0)
        self.assertFalse(stale_offer.is_available)
        self.assertEqual(result.supplier_offers_zeroed, 1)

    def test_sync_does_not_zero_recently_refreshed_offer_with_stale_product_price(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        product = self._create_product(is_active=True, prefix="REFRESHED-STOCK")
        stale_price = ProductPrice.objects.create(product=product, final_price="140.00", currency="UAH")
        ProductPrice.objects.filter(id=stale_price.id).update(updated_at=now - timedelta(hours=30))
        fresh_offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=product,
            supplier_sku=f"SUP-{product.sku}",
            purchase_price="100.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=9,
            lead_time_days=2,
            is_available=True,
        )
        SupplierOffer.objects.filter(id=fresh_offer.id).update(updated_at=now - timedelta(minutes=5))

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        product.refresh_from_db()
        fresh_offer.refresh_from_db()

        self.assertFalse(product.is_active)
        self.assertEqual(fresh_offer.stock_qty, 9)
        self.assertTrue(fresh_offer.is_available)
        self.assertEqual(result.supplier_offers_zeroed, 0)

    def test_sync_does_not_zero_offers_for_products_reactivated_by_fresh_price(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        inactive_product = self._create_product(is_active=False, prefix="INACTIVE-FRESH-OFFER")
        fresh_price = ProductPrice.objects.create(
            product=inactive_product,
            final_price="120.00",
            currency="UAH",
        )
        ProductPrice.objects.filter(id=fresh_price.id).update(updated_at=now - timedelta(hours=1))
        fresh_offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=inactive_product,
            supplier_sku=f"SUP-{inactive_product.sku}",
            purchase_price="90.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=4,
            lead_time_days=1,
            is_available=True,
        )
        SupplierOffer.objects.filter(id=fresh_offer.id).update(updated_at=now - timedelta(hours=1))

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        inactive_product.refresh_from_db()
        fresh_offer.refresh_from_db()

        self.assertTrue(inactive_product.is_active)
        self.assertEqual(fresh_offer.stock_qty, 4)
        self.assertTrue(fresh_offer.is_available)
        self.assertEqual(result.supplier_offers_zeroed, 0)

    def test_reprice_immediately_reactivates_product(self):
        product = self._create_product(is_active=False, prefix="REPRICE")
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=product,
            supplier_sku=f"SUP-{product.sku}",
            purchase_price="120.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=5,
            lead_time_days=1,
            is_available=True,
        )

        result = ProductRepricer().recalculate_product(product=product)

        product.refresh_from_db()
        product_price = ProductPrice.objects.get(product=product)
        self.assertEqual(result.status, "repriced")
        self.assertTrue(product.is_active)
        self.assertGreater(product_price.final_price, 0)

    def test_task_wrapper_returns_expected_stats(self):
        now = timezone.now()
        stale_product = self._create_product(is_active=True, prefix="TASK")
        stale_price = ProductPrice.objects.create(product=stale_product, final_price="130.00", currency="UAH")
        ProductPrice.objects.filter(id=stale_price.id).update(updated_at=now - timedelta(hours=30))

        payload = sync_products_activity_by_price_freshness_task(freshness_hours=24)

        stale_product.refresh_from_db()
        self.assertFalse(stale_product.is_active)
        self.assertEqual(payload["deactivated"], 1)
        self.assertEqual(payload["activated"], 0)
        self.assertIn("supplier_offers_zeroed", payload)
        self.assertEqual(payload["freshness_hours"], 24)
        self.assertIsInstance(payload["cutoff_at"], str)
