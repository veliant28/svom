from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Order, OrderReceipt
from apps.pricing.models import ProductPrice
from apps.users.models import User


class VchasnoKasaAccountAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner-vch@test.local", first_name="owner", password="demo12345")
        self.owner_token = Token.objects.create(user=self.owner)
        self.owner_auth = {"HTTP_AUTHORIZATION": f"Token {self.owner_token.key}"}

        self.other = User.objects.create_user(email="other-vch@test.local", first_name="other", password="demo12345")
        self.other_token = Token.objects.create(user=self.other)
        self.other_auth = {"HTTP_AUTHORIZATION": f"Token {self.other_token.key}"}

        brand = Brand.objects.create(name="Account Vchasno Brand", slug="account-vch-brand", is_active=True)
        category = Category.objects.create(name="Account Vchasno Category", slug="account-vch-category", is_active=True)
        product = Product.objects.create(
            sku="ACC-VCH-001",
            article="ACC-VCH-001",
            name="Account Receipt Product",
            slug="account-vchasno-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductPrice.objects.create(product=product, final_price="199.00", currency="UAH")

        self.order = Order.objects.create(
            user=self.owner,
            order_number="ORD-VCH-ACC-1",
            status=Order.STATUS_COMPLETED,
            contact_full_name="Owner Customer",
            contact_phone="+380000000002",
            contact_email="owner-vch@test.local",
            delivery_method=Order.DELIVERY_PICKUP,
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="199.00",
            delivery_fee="0.00",
            total="199.00",
            currency="UAH",
        )
        OrderReceipt.objects.create(
            order=self.order,
            vchasno_order_number=self.order.order_number,
            fiscal_status_code=11,
            fiscal_status_key="fiscalized",
            fiscal_status_label="Fiscalized",
            receipt_url="https://kasa.vchasno.ua/check/account-1",
        )

    def test_owner_can_open_receipt_and_other_user_cannot(self):
        owner_response = self.client.get(
            reverse("commerce_api:account-order-receipt-open", kwargs={"order_id": str(self.order.id)}),
            {"mode": "json"},
            **self.owner_auth,
        )
        self.assertEqual(owner_response.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_response.data["url"], "https://kasa.vchasno.ua/check/account-1")

        other_response = self.client.get(
            reverse("commerce_api:account-order-receipt-open", kwargs={"order_id": str(self.order.id)}),
            {"mode": "json"},
            **self.other_auth,
        )
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)
