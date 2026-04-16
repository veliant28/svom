from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.pricing.services import OfferStrategy, ProductSellableSnapshotService, SupplierOfferSelector
from apps.pricing.services.availability_calculator import AvailabilityCalculator, AvailabilityStatus
from apps.pricing.services.selector.types import OfferSelectionResult


class OfferIntelligenceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Selector Brand", slug="selector-brand", is_active=True)
        self.category = Category.objects.create(name="Selector Category", slug="selector-category", is_active=True)
        self.product = Product.objects.create(
            sku="SEL-001",
            article="SEL-001",
            name="Selector Product",
            slug="selector-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="150.00", currency="UAH")

        self.preferred_supplier = Supplier.objects.create(
            name="Preferred Supplier",
            code="preferred",
            is_active=True,
            is_preferred=True,
            priority=1,
            quality_score="9.50",
        )
        self.fast_supplier = Supplier.objects.create(
            name="Fast Supplier",
            code="fast",
            is_active=True,
            is_preferred=False,
            priority=10,
            quality_score="8.50",
        )
        self.cheap_supplier = Supplier.objects.create(
            name="Cheap Supplier",
            code="cheap",
            is_active=True,
            is_preferred=False,
            priority=20,
            quality_score="7.00",
        )

        self.offer_preferred = SupplierOffer.objects.create(
            supplier=self.preferred_supplier,
            product=self.product,
            supplier_sku="P-1",
            purchase_price="120.00",
            logistics_cost="5.00",
            extra_cost="0.00",
            stock_qty=3,
            lead_time_days=2,
            is_available=True,
        )
        self.offer_fast = SupplierOffer.objects.create(
            supplier=self.fast_supplier,
            product=self.product,
            supplier_sku="F-1",
            purchase_price="118.00",
            logistics_cost="4.00",
            extra_cost="0.00",
            stock_qty=2,
            lead_time_days=0,
            is_available=True,
        )
        self.offer_cheap = SupplierOffer.objects.create(
            supplier=self.cheap_supplier,
            product=self.product,
            supplier_sku="C-1",
            purchase_price="100.00",
            logistics_cost="3.00",
            extra_cost="1.00",
            stock_qty=1,
            lead_time_days=4,
            is_available=True,
        )

    def test_best_offer_selector_strategies(self):
        selector = SupplierOfferSelector()

        cheapest = selector.select_for_product(product=self.product, strategy=OfferStrategy.CHEAPEST)
        self.assertEqual(cheapest.selected_offer.id, self.offer_cheap.id)

        fastest = selector.select_for_product(product=self.product, strategy=OfferStrategy.FASTEST_DELIVERY)
        self.assertEqual(fastest.selected_offer.id, self.offer_fast.id)

        preferred = selector.select_for_product(product=self.product, strategy=OfferStrategy.PREFERRED_SUPPLIER)
        self.assertEqual(preferred.selected_offer.id, self.offer_preferred.id)

        in_stock_first = selector.select_for_product(product=self.product, strategy=OfferStrategy.IN_STOCK_FIRST, quantity=2)
        self.assertEqual(in_stock_first.selected_offer.id, self.offer_fast.id)

    def test_selector_fallback_and_explainability(self):
        self.preferred_supplier.is_preferred = False
        self.preferred_supplier.save(update_fields=("is_preferred", "updated_at"))

        selector = SupplierOfferSelector()
        result = selector.select_for_product(product=self.product, strategy=OfferStrategy.PREFERRED_SUPPLIER)

        self.assertIsNotNone(result.selected_offer)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.requested_strategy, OfferStrategy.PREFERRED_SUPPLIER)
        self.assertIn("ordered_candidates", result.explainability)
        self.assertGreaterEqual(len(result.explainability["ordered_candidates"]), 1)

    def test_availability_calculation_statuses(self):
        calculator = AvailabilityCalculator()

        in_stock_selection = OfferSelectionResult(
            selected_offer=self.offer_fast,
            requested_strategy=OfferStrategy.BEST_OFFER,
            strategy_applied=OfferStrategy.BEST_OFFER,
            fallback_used=False,
            reason="",
            explainability={},
        )
        in_stock = calculator.calculate(product=self.product, selection=in_stock_selection, requested_quantity=1)
        self.assertEqual(in_stock.status, AvailabilityStatus.LOW_STOCK)
        self.assertTrue(in_stock.is_sellable)

        self.offer_fast.stock_qty = 0
        self.offer_fast.lead_time_days = 12
        self.offer_fast.save(update_fields=("stock_qty", "lead_time_days", "updated_at"))

        preorder_selection = OfferSelectionResult(
            selected_offer=self.offer_fast,
            requested_strategy=OfferStrategy.BEST_OFFER,
            strategy_applied=OfferStrategy.BEST_OFFER,
            fallback_used=False,
            reason="",
            explainability={},
        )
        preorder = calculator.calculate(product=self.product, selection=preorder_selection, requested_quantity=1)
        self.assertEqual(preorder.status, AvailabilityStatus.PREORDER)
        self.assertTrue(preorder.is_sellable)

    def test_sellable_snapshot_fallback_without_offer(self):
        SupplierOffer.objects.filter(product=self.product).delete()
        ProductPrice.objects.filter(product=self.product).update(final_price=Decimal("99.99"))

        snapshot = ProductSellableSnapshotService().build(product=self.product)
        self.assertEqual(snapshot.availability_status, AvailabilityStatus.ON_REQUEST)
        self.assertTrue(snapshot.is_sellable)
        self.assertIn("no_matched_supplier_offer", snapshot.quality_hints)
