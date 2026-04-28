from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import CheckoutMethodSettings, Order
from apps.pricing.models import ProductPrice
from apps.users.models import User


class CheckoutMethodSettingsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="checkout-methods@test.local", first_name="Checkout", password="pass12345")
        self.token = Token.objects.create(user=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}
        brand = Brand.objects.create(name="Checkout Methods Brand", slug="checkout-methods-brand", is_active=True)
        category = Category.objects.create(name="Checkout Methods Category", slug="checkout-methods-category", is_active=True)
        self.product = Product.objects.create(
            sku="CHECKOUT-METHODS-001",
            article="CHECKOUT-METHODS-001",
            name="Checkout Methods Product",
            slug="checkout-methods-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="100.00", currency="UAH")

    def test_checkout_methods_endpoint_returns_enabled_methods(self):
        settings, _ = CheckoutMethodSettings.objects.get_or_create(code=CheckoutMethodSettings.DEFAULT_CODE)
        settings.pickup_enabled = False
        settings.monobank_enabled = False
        settings.save(update_fields=("pickup_enabled", "monobank_enabled", "updated_at"))

        response = self.client.get(reverse("commerce_api:checkout-methods"), **self.auth)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(Order.DELIVERY_PICKUP, response.data["delivery_methods"])
        self.assertIn(Order.DELIVERY_NOVA_POSHTA, response.data["delivery_methods"])
        self.assertNotIn(Order.PAYMENT_MONOBANK, response.data["payment_methods"])
        self.assertIn(Order.PAYMENT_NOVAPAY, response.data["payment_methods"])
        self.assertIn(Order.PAYMENT_CASH_ON_DELIVERY, response.data["payment_methods"])

    def test_checkout_preview_rejects_disabled_delivery_method(self):
        settings, _ = CheckoutMethodSettings.objects.get_or_create(code=CheckoutMethodSettings.DEFAULT_CODE)
        settings.courier_enabled = False
        settings.save(update_fields=("courier_enabled", "updated_at"))

        response = self.client.get(
            reverse("commerce_api:checkout-preview"),
            {"delivery_method": Order.DELIVERY_COURIER},
            **self.auth,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delivery_method", response.data)

    def test_checkout_submit_rejects_disabled_methods(self):
        settings, _ = CheckoutMethodSettings.objects.get_or_create(code=CheckoutMethodSettings.DEFAULT_CODE)
        settings.courier_enabled = False
        settings.cash_on_delivery_enabled = False
        settings.novapay_enabled = False
        settings.monobank_enabled = False
        settings.liqpay_enabled = False
        settings.save(
            update_fields=(
                "courier_enabled",
                "cash_on_delivery_enabled",
                "novapay_enabled",
                "monobank_enabled",
                "liqpay_enabled",
                "updated_at",
            )
        )
        self.client.post(
            reverse("commerce_api:cart-item-create"),
            {"product_id": str(self.product.id), "quantity": 1},
            format="json",
            **self.auth,
        )

        response = self.client.post(
            reverse("commerce_api:checkout-submit"),
            {
                "contact_full_name": "Checkout Demo",
                "contact_phone": "38(000)111-22-33",
                "contact_email": "checkout-methods@test.local",
                "delivery_method": Order.DELIVERY_COURIER,
                "delivery_address": "Kyiv, Demo street 1",
                "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
            },
            format="json",
            **self.auth,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delivery_method", response.data)
        self.assertIn("payment_method", response.data)
