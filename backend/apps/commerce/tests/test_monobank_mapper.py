from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Order, OrderItem
from apps.commerce.services.monobank.mapper import build_invoice_create_payload
from apps.users.models import User


class MonobankMapperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="mono-mapper@test.local", first_name="mono", password="pass12345")
        self.brand = Brand.objects.create(name="Mono Brand", slug="mono-brand", is_active=True)
        self.category = Category.objects.create(name="Mono Category", slug="mono-category", is_active=True)
        self.product = Product.objects.create(
            sku="MONO-001",
            article="MONO-001",
            name="Mono Product",
            slug="mono-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

    def test_build_invoice_payload_includes_basket_order_items(self):
        order = Order.objects.create(
            user=self.user,
            order_number="ORD-MONO-1",
            status=Order.STATUS_NEW,
            contact_full_name="Mono User",
            contact_phone="+380001112233",
            contact_email="mono-mapper@test.local",
            delivery_method=Order.DELIVERY_PICKUP,
            delivery_address="",
            payment_method=Order.PAYMENT_MONOBANK,
            subtotal=Decimal("400.00"),
            delivery_fee=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("400.00"),
            currency="UAH",
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name="Service Product",
            product_sku="MONO-001",
            quantity=2,
            unit_price=Decimal("200.00"),
            line_total=Decimal("400.00"),
        )

        payload = build_invoice_create_payload(order=order, webhook_url="https://example.test/webhook")
        basket = payload.get("merchantPaymInfo", {}).get("basketOrder")

        self.assertIsInstance(basket, list)
        self.assertEqual(len(basket), 1)
        self.assertEqual(basket[0]["name"], "Service Product")
        self.assertEqual(basket[0]["qty"], 2)
        self.assertEqual(basket[0]["sum"], 20000)
        self.assertEqual(basket[0]["code"], "MONO-001")
        self.assertEqual(basket[0]["tax"], [0])

    def test_build_invoice_payload_adds_fallback_basket_order_when_order_items_absent(self):
        order = Order.objects.create(
            user=self.user,
            order_number="ORD-MONO-2",
            status=Order.STATUS_NEW,
            contact_full_name="Mono User",
            contact_phone="+380001112233",
            contact_email="mono-mapper@test.local",
            delivery_method=Order.DELIVERY_PICKUP,
            delivery_address="",
            payment_method=Order.PAYMENT_MONOBANK,
            subtotal=Decimal("500.00"),
            delivery_fee=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("500.00"),
            currency="UAH",
        )

        payload = build_invoice_create_payload(order=order, webhook_url="https://example.test/webhook")
        basket = payload.get("merchantPaymInfo", {}).get("basketOrder")

        self.assertEqual(
            basket,
            [
                {
                    "name": "Order ORD-MONO-2",
                    "qty": 1,
                    "sum": 50000,
                    "code": "ORD-MONO-2",
                    "tax": [0],
                }
            ],
        )
