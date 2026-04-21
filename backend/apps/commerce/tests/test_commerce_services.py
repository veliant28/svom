from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import CartItem, Order
from apps.commerce.services import add_product_to_cart, calculate_cart_totals, get_or_create_user_cart, submit_checkout
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.users.models import User


class CommerceServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="service@test.local", first_name="service", password="pass12345")
        self.brand = Brand.objects.create(name="Service Brand", slug="service-brand", is_active=True)
        self.category = Category.objects.create(name="Service Category", slug="service-category", is_active=True)

        self.product = Product.objects.create(
            sku="SERVICE-001",
            article="SERVICE-001",
            name="Service Product",
            slug="service-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="200.00", currency="UAH")
        self.supplier = Supplier.objects.create(
            name="Service Supplier",
            code="service-supplier",
            is_active=True,
            is_preferred=True,
            priority=1,
        )
        self.offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="SERVICE-SUP-001",
            purchase_price="150.00",
            logistics_cost="10.00",
            extra_cost="0.00",
            stock_qty=10,
            lead_time_days=0,
            is_available=True,
        )

    def test_cart_totals_calculation(self):
        cart = get_or_create_user_cart(self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=3)

        totals = calculate_cart_totals([item])
        self.assertEqual(totals.items_count, 3)
        self.assertEqual(totals.subtotal, Decimal("600.00"))

    def test_submit_checkout_creates_order_and_clears_cart(self):
        cart = get_or_create_user_cart(self.user)
        add_product_to_cart(user=self.user, product=self.product, quantity=2)

        order = submit_checkout(
            user=self.user,
            payload={
                "contact_full_name": "Service Demo",
                "contact_phone": "+380001112233",
                "contact_email": "service@test.local",
                "delivery_method": Order.DELIVERY_PICKUP,
                "delivery_address": "",
                "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
                "customer_comment": "",
            },
        )

        self.assertEqual(order.total, Decimal("400.00"))
        self.assertEqual(order.status, Order.STATUS_NEW)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(cart.items.count(), 0)

    def test_checkout_validation_rejects_stale_price(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        ProductPrice.objects.filter(product=self.product).update(final_price=Decimal("250.00"))

        with self.assertRaises(ValidationError) as exc:
            submit_checkout(
                user=self.user,
                payload={
                    "contact_full_name": "Service Demo",
                    "contact_phone": "+380001112233",
                    "contact_email": "service@test.local",
                    "delivery_method": Order.DELIVERY_PICKUP,
                    "delivery_address": "",
                    "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
                    "customer_comment": "",
                },
            )

        self.assertIn("cart", exc.exception.message_dict)
        self.assertIn("items", exc.exception.message_dict)

    def test_checkout_validation_rejects_unavailable_item(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        ProductPrice.objects.filter(product=self.product).update(final_price=Decimal("0.00"))
        SupplierOffer.objects.filter(id=self.offer.id).update(is_available=False, stock_qty=0)

        with self.assertRaises(ValidationError) as exc:
            submit_checkout(
                user=self.user,
                payload={
                    "contact_full_name": "Service Demo",
                    "contact_phone": "+380001112233",
                    "contact_email": "service@test.local",
                    "delivery_method": Order.DELIVERY_PICKUP,
                    "delivery_address": "",
                    "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
                    "customer_comment": "",
                },
            )

        self.assertIn("cart", exc.exception.message_dict)
        self.assertIn("items", exc.exception.message_dict)
        self.assertGreater(len(exc.exception.message_dict["items"]), 0)

    def test_order_item_snapshot_is_persisted(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=2)
        order = submit_checkout(
            user=self.user,
            payload={
                "contact_full_name": "Service Demo",
                "contact_phone": "+380001112233",
                "contact_email": "service@test.local",
                "delivery_method": Order.DELIVERY_PICKUP,
                "delivery_address": "",
                "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
                "customer_comment": "",
            },
        )
        item = order.items.first()
        assert item is not None

        self.assertEqual(item.snapshot_sell_price, item.unit_price)
        self.assertTrue(item.snapshot_availability_status)
        self.assertTrue(item.snapshot_availability_label)
        self.assertTrue(item.snapshot_procurement_source)
        self.assertIsNotNone(item.recommended_supplier_offer_id)
