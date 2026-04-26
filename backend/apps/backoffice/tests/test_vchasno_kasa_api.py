from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Order, OrderItem, OrderReceipt, VchasnoKasaSettings
from apps.pricing.models import ProductPrice
from apps.users.models import User


class BackofficeVchasnoKasaAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="vchasno-staff@test.local",
            first_name="staff",
            password="demo12345",
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

        self.customer = User.objects.create_user(
            email="vchasno-customer@test.local",
            first_name="customer",
            password="demo12345",
        )

        brand = Brand.objects.create(name="Vchasno Brand", slug="vchasno-brand", is_active=True)
        category = Category.objects.create(name="Vchasno Category", slug="vchasno-category", is_active=True)
        self.product = Product.objects.create(
            sku="VCH-001",
            article="VCH-001",
            name="Vchasno Product",
            slug="vchasno-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="120.00", currency="UAH")

        self.order = Order.objects.create(
            user=self.customer,
            order_number="ORD-VCH-1001",
            status=Order.STATUS_SHIPPED,
            contact_full_name="Receipt Customer",
            contact_phone="+380000000001",
            contact_email="vchasno-customer@test.local",
            delivery_method=Order.DELIVERY_PICKUP,
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="120.00",
            delivery_fee="0.00",
            total="120.00",
            currency="UAH",
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=1,
            unit_price="120.00",
            line_total="120.00",
        )

    def test_settings_mask_token_and_validate_required_fields(self):
        invalid_response = self.client.patch(
            reverse("backoffice_api:vchasno-kasa-settings"),
            {"is_enabled": True},
            format="json",
            **self.auth,
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("api_token", invalid_response.data)

        save_response = self.client.patch(
            reverse("backoffice_api:vchasno-kasa-settings"),
            {
                "is_enabled": True,
                "api_token": "secret-token-1234",
                "fiscal_api_token": "fiscal-secret-5678",
                "rro_fn": "PRRO-77",
                "default_payment_type": 1,
                "selected_payment_methods": ["1"],
                "selected_tax_groups": ["Б"],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("api_token", save_response.data)
        self.assertNotIn("fiscal_api_token", save_response.data)
        self.assertTrue(save_response.data["api_token_masked"].endswith("1234"))
        self.assertTrue(save_response.data["fiscal_api_token_masked"].endswith("5678"))

        get_response = self.client.get(reverse("backoffice_api:vchasno-kasa-settings"), **self.auth)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("api_token", get_response.data)
        self.assertNotIn("fiscal_api_token", get_response.data)
        self.assertTrue(get_response.data["api_token_masked"].endswith("1234"))
        self.assertTrue(get_response.data["fiscal_api_token_masked"].endswith("5678"))

    def test_settings_accept_multiple_payment_methods_and_tax_groups(self):
        response = self.client.patch(
            reverse("backoffice_api:vchasno-kasa-settings"),
            {
                "is_enabled": True,
                "api_token": "secret-token-5678",
                "rro_fn": "PRRO-88",
                "selected_payment_methods": ["17", "20", "2"],
                "selected_tax_groups": ["Б", "А", "ИК"],
            },
            format="json",
            **self.auth,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["selected_payment_methods"], ["17", "20", "2"])
        self.assertEqual(response.data["selected_tax_groups"], ["Б", "А", "ИК"])

        settings = VchasnoKasaSettings.objects.get(code=VchasnoKasaSettings.DEFAULT_CODE)
        self.assertEqual(settings.selected_payment_methods, ["17", "20", "2"])
        self.assertEqual(settings.selected_tax_groups, ["Б", "А", "ИК"])

    @patch("apps.backoffice.api.views.vchasno_kasa_views.get_vchasno_shift_status")
    def test_shift_status_endpoint_returns_payload(self, mock_get_shift_status):
        mock_get_shift_status.return_value = {
            "status_key": "closed",
            "is_open": False,
            "shift_id": "",
            "shift_link": "",
            "message": "Необхідно відкрити зміну",
            "checked_at": timezone.now(),
            "can_open": True,
            "response_code": 2007,
        }

        response = self.client.get(reverse("backoffice_api:vchasno-kasa-shift-status"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status_key"], "closed")
        self.assertTrue(response.data["can_open"])

    @patch("apps.backoffice.api.views.vchasno_kasa_views.open_vchasno_shift")
    def test_open_shift_endpoint_returns_payload(self, mock_open_shift):
        mock_open_shift.return_value = {
            "status_key": "open",
            "is_open": True,
            "shift_id": "shift-1",
            "shift_link": "39",
            "message": "Зміну відкрито.",
            "checked_at": timezone.now(),
            "can_open": False,
            "response_code": 0,
        }

        response = self.client.post(reverse("backoffice_api:vchasno-kasa-open-shift"), {}, format="json", **self.auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status_key"], "open")
        self.assertEqual(response.data["shift_id"], "shift-1")

    @patch("apps.backoffice.api.views.vchasno_kasa_views.close_vchasno_shift")
    def test_close_shift_endpoint_returns_payload(self, mock_close_shift):
        mock_close_shift.return_value = {
            "status_key": "closed",
            "is_open": False,
            "shift_id": "shift-1",
            "shift_link": "39",
            "message": "Зміну закрито.",
            "checked_at": timezone.now(),
            "can_open": True,
            "response_code": 0,
        }

        response = self.client.post(reverse("backoffice_api:vchasno-kasa-close-shift"), {}, format="json", **self.auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status_key"], "closed")
        self.assertEqual(response.data["shift_id"], "shift-1")

    @patch("apps.commerce.services.vchasno_kasa.service.VchasnoKasaApiClient.create_order")
    def test_issue_receipt_is_idempotent(self, mock_create_order):
        settings = VchasnoKasaSettings.objects.create(
            code=VchasnoKasaSettings.DEFAULT_CODE,
            is_enabled=True,
            api_token="token-1234",
            rro_fn="PRRO-77",
            selected_payment_methods=["4"],
            selected_tax_groups=["Б"],
        )
        mock_create_order.return_value = {
            "order_number": self.order.order_number,
            "statusCode": 11,
            "checkFn": "FN-001",
            "receiptUrl": "https://kasa.vchasno.ua/check/1",
        }

        first = self.client.post(
            reverse("backoffice_api:order-vchasno-kasa-issue", kwargs={"order_id": str(self.order.id)}),
            {},
            format="json",
            **self.auth,
        )
        second = self.client.post(
            reverse("backoffice_api:order-vchasno-kasa-issue", kwargs={"order_id": str(self.order.id)}),
            {},
            format="json",
            **self.auth,
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(OrderReceipt.objects.filter(order=self.order).count(), 1)
        self.assertFalse(first.data["already_exists"])
        self.assertTrue(second.data["already_exists"])
        self.assertEqual(mock_create_order.call_count, 1)
        settings.refresh_from_db()
        self.assertTrue(settings.is_enabled)

    @patch("apps.commerce.tasks.vchasno_kasa.issue_vchasno_kasa_receipt_task.delay")
    @patch("apps.backoffice.services.order_operations_service.transaction.on_commit", side_effect=lambda callback: callback())
    def test_completed_status_enqueues_receipt_task(self, _mock_on_commit, mock_delay):
        VchasnoKasaSettings.objects.create(
            code=VchasnoKasaSettings.DEFAULT_CODE,
            is_enabled=True,
            api_token="token-1234",
            rro_fn="PRRO-77",
            selected_payment_methods=["4"],
            selected_tax_groups=["Б"],
            auto_issue_on_completed=True,
        )

        response = self.client.post(
            reverse("backoffice_api:order-action-complete"),
            {"order_id": str(self.order.id)},
            format="json",
            **self.auth,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["receipt_notice_code"], "vchasno_issue_started")
        mock_delay.assert_called_once()
