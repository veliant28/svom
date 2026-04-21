from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.services import add_product_to_cart, issue_loyalty_promo
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.users.models import User


class LoyaltyCommerceAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="promo-user@test.local", first_name="Promo", password="pass12345")
        self.other_user = User.objects.create_user(email="promo-other@test.local", first_name="Other", password="pass12345")
        self.staff = User.objects.create_user(email="promo-staff@test.local", first_name="Staff", password="pass12345", is_staff=True)

        self.token = Token.objects.create(user=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

        brand = Brand.objects.create(name="Promo Brand", slug="promo-brand", is_active=True)
        category = Category.objects.create(name="Promo Category", slug="promo-category", is_active=True)
        self.product = Product.objects.create(
            sku="PROMO-001",
            article="PROMO-001",
            name="Promo Product",
            slug="promo-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="210.00", landed_cost="160.00", currency="UAH")
        supplier = Supplier.objects.create(name="Promo Supplier", code="promo-supplier", is_active=True, is_preferred=True, priority=1)
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="PROMO-SUP-001",
            purchase_price="160.00",
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=30,
            lead_time_days=0,
            is_available=True,
        )

    def test_my_loyalty_codes_returns_only_current_user_codes(self):
        own = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="Own code",
            discount_type="delivery_fee",
            discount_percent=Decimal("10.00"),
            expires_at=None,
            usage_limit=1,
        )
        issue_loyalty_promo(
            customer=self.other_user,
            issued_by=self.staff,
            reason="Foreign code",
            discount_type="delivery_fee",
            discount_percent=Decimal("10.00"),
            expires_at=None,
            usage_limit=1,
        )

        response = self.client.get(reverse("commerce_api:loyalty-my-codes"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], own.code)

    def test_apply_checkout_promo_blocks_foreign_code(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        foreign = issue_loyalty_promo(
            customer=self.other_user,
            issued_by=self.staff,
            reason="Foreign code",
            discount_type="delivery_fee",
            discount_percent=Decimal("10.00"),
            expires_at=None,
            usage_limit=1,
        )

        response = self.client.post(
            reverse("commerce_api:checkout-promo-apply"),
            {"promo_code": foreign.code, "delivery_method": "courier"},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("promo_code_error"), "not_owned")

    def test_apply_checkout_promo_returns_breakdown(self):
        add_product_to_cart(user=self.user, product=self.product, quantity=1)
        promo = issue_loyalty_promo(
            customer=self.user,
            issued_by=self.staff,
            reason="Delivery promo",
            discount_type="delivery_fee",
            discount_percent=Decimal("50.00"),
            expires_at=None,
            usage_limit=1,
        )

        response = self.client.post(
            reverse("commerce_api:checkout-promo-apply"),
            {"promo_code": promo.code, "delivery_method": "courier"},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        preview = response.data["checkout_preview"]
        self.assertEqual(preview["promo"]["code"], promo.code)
        self.assertEqual(preview["promo"]["discount_type"], "delivery_fee")
        self.assertEqual(str(preview["discount_total"]), "75.00")
