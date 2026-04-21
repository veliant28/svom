from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import CartItem, Order
from apps.commerce.services import add_product_to_cart, get_or_create_user_cart, submit_checkout
from apps.commerce.services.checkout_service import resolve_delivery_fee
from apps.commerce.services.loyalty_service import (
    LoyaltyPromoValidationError,
    compute_loyalty_discount_for_checkout,
    issue_loyalty_promo,
)
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.users.models import User


class LoyaltyServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="loyalty@test.local", first_name="Loyal", password="pass12345")
        self.other_user = User.objects.create_user(email="loyalty-other@test.local", first_name="Other", password="pass12345")
        self.staff = User.objects.create_user(email="staff@test.local", first_name="Staff", password="pass12345", is_staff=True)

        brand = Brand.objects.create(name="Loyalty Brand", slug="loyalty-brand", is_active=True)
        category = Category.objects.create(name="Loyalty Category", slug="loyalty-category", is_active=True)
        self.product = Product.objects.create(
            sku="LOYALTY-001",
            article="LOYALTY-001",
            name="Loyalty Product",
            slug="loyalty-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductPrice.objects.create(
            product=self.product,
            final_price="200.00",
            landed_cost="150.00",
            currency="UAH",
        )
        supplier = Supplier.objects.create(name="Loyalty Supplier", code="loyalty-supplier", is_active=True, is_preferred=True, priority=1)
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="LOYALTY-SUP-001",
            purchase_price="150.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=20,
            lead_time_days=0,
            is_available=True,
        )

    def _cart_items(self):
        cart = get_or_create_user_cart(self.user)
        return list(
            cart.items.select_related("product", "product__product_price").prefetch_related("product__supplier_offers")
        )

    def test_issue_generates_unique_codes(self):
        first = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="Compensation",
            discount_type="delivery_fee",
            discount_percent=Decimal("10.00"),
            expires_at=None,
            usage_limit=1,
        )
        second = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="Retention",
            discount_type="delivery_fee",
            discount_percent=Decimal("10.00"),
            expires_at=None,
            usage_limit=1,
        )
        self.assertNotEqual(first.code, second.code)

    def test_delivery_discount_applies_only_to_delivery_fee(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=2)
        promo = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="Delivery promo",
            discount_type="delivery_fee",
            discount_percent=Decimal("50.00"),
            expires_at=None,
            usage_limit=1,
        )

        computation = compute_loyalty_discount_for_checkout(
            user=self.user,
            promo_code_value=promo.code,
            items=self._cart_items(),
            delivery_fee=resolve_delivery_fee(Order.DELIVERY_COURIER),
            currency="UAH",
        )

        self.assertEqual(computation.delivery_discount, Decimal("75.00"))
        self.assertEqual(computation.product_discount, Decimal("0.00"))
        self.assertEqual(computation.total_discount, Decimal("75.00"))

    def test_delivery_discount_rejected_when_delivery_is_zero(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        promo = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="Delivery promo",
            discount_type="delivery_fee",
            discount_percent=Decimal("100.00"),
            expires_at=None,
            usage_limit=1,
        )

        with self.assertRaises(LoyaltyPromoValidationError) as exc:
            compute_loyalty_discount_for_checkout(
                user=self.user,
                promo_code_value=promo.code,
                items=self._cart_items(),
                delivery_fee=Decimal("0.00"),
                currency="UAH",
            )

        self.assertEqual(exc.exception.code, "delivery_zero")

    def test_product_discount_respects_markup_cap(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=2)
        promo = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="Product promo",
            discount_type="product_markup",
            discount_percent=Decimal("100.00"),
            expires_at=None,
            usage_limit=1,
        )

        computation = compute_loyalty_discount_for_checkout(
            user=self.user,
            promo_code_value=promo.code,
            items=self._cart_items(),
            delivery_fee=Decimal("0.00"),
            currency="UAH",
        )

        self.assertEqual(computation.product_markup_total, Decimal("100.00"))
        self.assertEqual(computation.product_discount, Decimal("100.00"))
        self.assertEqual(computation.total_after_discount, Decimal("300.00"))

    def test_one_time_promo_cannot_be_reused_after_checkout(self):
        promo = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="One-time product promo",
            discount_type="product_markup",
            discount_percent=Decimal("50.00"),
            expires_at=None,
            usage_limit=1,
        )

        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        order = submit_checkout(
            user=self.user,
            payload={
                "contact_full_name": "Loyal User",
                "contact_phone": "380001112233",
                "contact_email": self.user.email,
                "delivery_method": Order.DELIVERY_PICKUP,
                "delivery_address": "",
                "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
                "customer_comment": "",
                "promo_code": promo.code,
            },
        )
        self.assertEqual(order.applied_promo_code, promo.code)
        self.assertGreater(order.discount_total, Decimal("0.00"))
        self.assertTrue(order.discount_breakdown)

        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        with self.assertRaises(ValidationError) as exc:
            submit_checkout(
                user=self.user,
                payload={
                    "contact_full_name": "Loyal User",
                    "contact_phone": "380001112233",
                    "contact_email": self.user.email,
                    "delivery_method": Order.DELIVERY_PICKUP,
                    "delivery_address": "",
                    "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
                    "customer_comment": "",
                    "promo_code": promo.code,
                },
            )

        self.assertIn("promo_code", exc.exception.message_dict)

    def test_foreign_promo_code_cannot_be_applied(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        foreign_promo = issue_loyalty_promo(
            customer=self.other_user,
            issued_by=self.staff,
            reason="Other user promo",
            discount_type="delivery_fee",
            discount_percent=Decimal("10.00"),
            expires_at=None,
            usage_limit=1,
        )

        with self.assertRaises(LoyaltyPromoValidationError) as exc:
            compute_loyalty_discount_for_checkout(
                user=self.user,
                promo_code_value=foreign_promo.code,
                items=self._cart_items(),
                delivery_fee=Decimal("100.00"),
                currency="UAH",
            )

        self.assertEqual(exc.exception.code, "not_owned")
