from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import PriceOverride, PricingPolicy, ProductPrice, Supplier, SupplierOffer
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
        self.policy = PricingPolicy.objects.create(
            name="Activity Global Policy",
            scope=PricingPolicy.SCOPE_GLOBAL,
            percent_markup="20.00",
            min_margin_percent="10.00",
            is_active=True,
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

    def _create_safe_price(self, *, product: Product, purchase_price: str = "100.00", final_price: str = "130.00"):
        return ProductPrice.objects.create(
            product=product,
            purchase_price=purchase_price,
            final_price=final_price,
            currency="UAH",
            policy=self.policy,
        )

    def _create_offer(
        self,
        *,
        product: Product,
        stock_qty: int = 5,
        is_available: bool = True,
        last_seen_at=None,
        purchase_price: str = "100.00",
    ) -> SupplierOffer:
        return SupplierOffer.objects.create(
            supplier=self.supplier,
            product=product,
            supplier_sku=f"SUP-{product.sku}",
            purchase_price=purchase_price,
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=stock_qty,
            lead_time_days=1,
            is_available=is_available,
            last_seen_at=last_seen_at or timezone.now(),
        )

    def test_sync_deactivates_products_with_stale_or_missing_price(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        stale_product = self._create_product(is_active=True, prefix="STALE")
        self._create_safe_price(product=stale_product)
        stale_offer = self._create_offer(product=stale_product)
        SupplierOffer.objects.filter(id=stale_offer.id).update(last_seen_at=now - timedelta(hours=26))

        missing_price_product = self._create_product(is_active=True, prefix="MISSING")
        self._create_offer(product=missing_price_product, last_seen_at=now)

        fresh_product = self._create_product(is_active=True, prefix="FRESH")
        self._create_safe_price(product=fresh_product, purchase_price="150.00", final_price="199.00")
        self._create_offer(product=fresh_product, last_seen_at=now)

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
            purchase_price="160.00",
            final_price="210.00",
            currency="UAH",
            policy=self.policy,
        )
        ProductPrice.objects.filter(id=fresh_price.id).update(updated_at=now - timedelta(hours=30))
        self._create_offer(product=inactive_with_fresh_price, last_seen_at=now)

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        inactive_with_fresh_price.refresh_from_db()
        self.assertEqual(result.activated, 1)
        self.assertTrue(inactive_with_fresh_price.is_active)

    def test_sync_zeroes_stale_offers_for_deactivated_products(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        stale_product = self._create_product(is_active=True, prefix="STALE-STOCK")
        self._create_safe_price(product=stale_product, final_price="140.00")

        stale_offer = self._create_offer(product=stale_product, stock_qty=9)
        SupplierOffer.objects.filter(id=stale_offer.id).update(
            last_seen_at=now - timedelta(hours=30),
            updated_at=now - timedelta(hours=30),
        )

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
        ProductPrice.objects.create(product=product, final_price="140.00", currency="UAH")
        fresh_offer = self._create_offer(product=product, stock_qty=9, last_seen_at=now)

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
            purchase_price="90.00",
            final_price="120.00",
            currency="UAH",
            policy=self.policy,
        )
        ProductPrice.objects.filter(id=fresh_price.id).update(updated_at=now - timedelta(hours=30))
        fresh_offer = self._create_offer(product=inactive_product, stock_qty=4, last_seen_at=now, purchase_price="90.00")

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        inactive_product.refresh_from_db()
        fresh_offer.refresh_from_db()

        self.assertTrue(inactive_product.is_active)
        self.assertEqual(fresh_offer.stock_qty, 4)
        self.assertTrue(fresh_offer.is_available)
        self.assertEqual(result.supplier_offers_zeroed, 0)

    def test_sync_deactivates_product_with_fresh_offer_but_no_actual_markup(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        product = self._create_product(is_active=True, prefix="NO-POLICY")
        ProductPrice.objects.create(
            product=product,
            purchase_price="100.00",
            final_price="100.00",
            currency="UAH",
        )
        self._create_offer(product=product, last_seen_at=now)

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        product.refresh_from_db()
        self.assertFalse(product.is_active)
        self.assertEqual(result.deactivated, 1)
        self.assertEqual(result.deactivated_unsafe_markup, 1)

    def test_sync_keeps_product_active_when_positive_markup_is_below_policy_margin(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        product = self._create_product(is_active=True, prefix="LOW-MARGIN")
        ProductPrice.objects.create(
            product=product,
            purchase_price="100.00",
            final_price="105.00",
            currency="UAH",
            policy=self.policy,
        )
        self._create_offer(product=product, last_seen_at=now)

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        product.refresh_from_db()
        self.assertTrue(product.is_active)
        self.assertEqual(result.deactivated, 0)
        self.assertEqual(result.deactivated_unsafe_markup, 0)

    def test_sync_allows_active_override_to_bypass_markup_policy_guard(self):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)

        product = self._create_product(is_active=False, prefix="OVERRIDE")
        ProductPrice.objects.create(
            product=product,
            purchase_price="100.00",
            final_price="101.00",
            currency="UAH",
        )
        PriceOverride.objects.create(product=product, override_price="101.00", currency="UAH", is_active=True)
        self._create_offer(product=product, last_seen_at=now)

        result = sync_products_activity_by_price_freshness(freshness_hours=24, cutoff_at=cutoff)

        product.refresh_from_db()
        self.assertTrue(product.is_active)
        self.assertEqual(result.activated, 1)

    def test_reprice_immediately_reactivates_product(self):
        product = self._create_product(is_active=False, prefix="REPRICE")
        self._create_offer(product=product, purchase_price="120.00")

        result = ProductRepricer().recalculate_product(product=product)

        product.refresh_from_db()
        product_price = ProductPrice.objects.get(product=product)
        self.assertEqual(result.status, "repriced")
        self.assertTrue(product.is_active)
        self.assertGreater(product_price.final_price, 0)

    def test_task_wrapper_returns_expected_stats(self):
        now = timezone.now()
        stale_product = self._create_product(is_active=True, prefix="TASK")
        self._create_safe_price(product=stale_product)
        stale_offer = self._create_offer(product=stale_product)
        SupplierOffer.objects.filter(id=stale_offer.id).update(last_seen_at=now - timedelta(hours=30))

        payload = sync_products_activity_by_price_freshness_task(freshness_hours=24)

        stale_product.refresh_from_db()
        self.assertFalse(stale_product.is_active)
        self.assertEqual(payload["deactivated"], 1)
        self.assertEqual(payload["activated"], 0)
        self.assertIn("deactivated_no_fresh_offer", payload)
        self.assertIn("deactivated_invalid_price", payload)
        self.assertIn("deactivated_unsafe_markup", payload)
        self.assertIn("supplier_offers_zeroed", payload)
        self.assertEqual(payload["freshness_hours"], 24)
        self.assertIsInstance(payload["cutoff_at"], str)
