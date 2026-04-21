from django.test import TestCase

from apps.backoffice.services import ProcurementService
from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Order, OrderItem
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.users.models import User


class ProcurementServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="procurement@test.local", first_name="procurement", password="pass12345")
        self.brand = Brand.objects.create(name="Procurement Brand", slug="procurement-brand", is_active=True)
        self.category = Category.objects.create(name="Procurement Category", slug="procurement-category", is_active=True)
        self.product = Product.objects.create(
            sku="PROC-001",
            article="PROC-001",
            name="Procurement Product",
            slug="procurement-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="180.00", currency="UAH")

        self.supplier = Supplier.objects.create(name="Procurement Supplier", code="proc-supplier", is_active=True, is_preferred=True, priority=1)
        self.offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="PROC-SUP-001",
            purchase_price="120.00",
            stock_qty=5,
            lead_time_days=1,
            is_available=True,
        )

        self.order = Order.objects.create(
            user=self.user,
            order_number="ORD-PROC-1",
            status=Order.STATUS_AWAITING_PROCUREMENT,
            contact_full_name="Procurement User",
            contact_phone="+380000000001",
            contact_email="procurement@test.local",
            delivery_method=Order.DELIVERY_PICKUP,
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="180.00",
            delivery_fee="0.00",
            total="180.00",
            currency="UAH",
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=2,
            unit_price="180.00",
            line_total="360.00",
            procurement_status=OrderItem.PROCUREMENT_AWAITING,
            recommended_supplier_offer=self.offer,
            snapshot_availability_status="supplier_stock",
            snapshot_availability_label="Supplier stock",
            snapshot_procurement_source="Available from supplier stock",
            snapshot_currency="UAH",
            snapshot_sell_price="180.00",
        )

    def test_grouped_procurement_suggestions(self):
        payload = ProcurementService().build_grouped_suggestions([self.order])

        self.assertEqual(payload["groups_count"], 1)
        self.assertEqual(payload["items_count"], 1)
        group = payload["groups"][0]
        self.assertEqual(group["supplier_name"], self.supplier.name)
        self.assertEqual(group["items_count"], 1)
        recommendation = group["items"][0]
        self.assertEqual(recommendation["order_item_id"], str(self.item.id))
        self.assertTrue(recommendation["can_fulfill"])
