from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import NovaPoshtaSenderProfile, Order, OrderItem
from apps.commerce.services.nova_poshta.client import NovaPoshtaResponse
from apps.commerce.services.nova_poshta.errors import NovaPoshtaErrorContext
from apps.users.models import User


def _np_response(payload: dict) -> NovaPoshtaResponse:
    return NovaPoshtaResponse(payload=payload, context=NovaPoshtaErrorContext())


class BackofficeOrderWaybillAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="waybill-staff@test.local",
            first_name="waybill-staff",
            password="demo12345",
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            email="waybill-user@test.local",
            first_name="waybill-user",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff)
        self.regular_token = Token.objects.create(user=self.regular)

        brand = Brand.objects.create(name="Bosch", slug="bosch")
        category = Category.objects.create(name="Filters", slug="filters")
        product = Product.objects.create(
            sku="BOS-001",
            article="BOS-001",
            name="Oil Filter",
            slug="oil-filter",
            brand=brand,
            category=category,
            is_active=True,
        )

        self.order = Order.objects.create(
            user=self.staff,
            order_number="ORD-NP-1",
            status=Order.STATUS_NEW,
            contact_full_name="Іван Іванов",
            contact_phone="+380671111111",
            contact_email="customer@test.local",
            delivery_method=Order.DELIVERY_NOVA_POSHTA,
            delivery_address="Kyiv",
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="1200.00",
            delivery_fee="0.00",
            total="1200.00",
            currency="UAH",
        )
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            quantity=1,
            unit_price="1200.00",
            line_total="1200.00",
        )

        self.sender = NovaPoshtaSenderProfile.objects.create(
            name="Main sender",
            sender_type=NovaPoshtaSenderProfile.TYPE_PRIVATE_PERSON,
            api_token="token-123",
            counterparty_ref="counterparty-ref",
            contact_ref="contact-ref",
            address_ref="address-ref",
            city_ref="city-ref",
            phone="+380671111111",
            contact_name="Іван",
            is_active=True,
            is_default=True,
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def _payload(self):
        return {
            "sender_profile_id": str(self.sender.id),
            "delivery_type": "warehouse",
            "recipient_city_ref": "recipient-city-ref",
            "recipient_city_label": "Київ",
            "recipient_address_ref": "warehouse-ref",
            "recipient_address_label": "Відділення №1",
            "recipient_name": "Петро Петров",
            "recipient_phone": "+380671234567",
            "seats_amount": 1,
            "weight": "1.200",
            "cost": "1200.00",
            "afterpayment_amount": "1200.00",
        }

    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.get_tracking_status")
    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.create_waybill")
    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.get_counterparty_options")
    def test_staff_can_create_waybill_for_order(self, mock_options, mock_create, mock_tracking):
        mock_options.return_value = _np_response({"success": True, "data": [{"CanAfterpaymentOnGoodsCost": True, "CanNonCashPayment": True}]})
        mock_create.return_value = _np_response({"success": True, "data": [{"Ref": "np-ref-1", "IntDocNumber": "20451234567890"}]})
        mock_tracking.return_value = _np_response({"success": True, "data": [{"StatusCode": "1", "Status": "Створено"}]})

        response = self.client.post(
            reverse("backoffice_api:order-waybill-create", kwargs={"order_id": self.order.id}),
            self._payload(),
            format="json",
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["np_number"], "20451234567890")

    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.get_tracking_status")
    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.update_waybill")
    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.create_waybill")
    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.get_counterparty_options")
    def test_staff_can_update_sync_and_delete_waybill(self, mock_options, mock_create, mock_update, mock_tracking):
        mock_options.return_value = _np_response({"success": True, "data": [{"CanAfterpaymentOnGoodsCost": True, "CanNonCashPayment": True}]})
        mock_create.return_value = _np_response({"success": True, "data": [{"Ref": "np-ref-1", "IntDocNumber": "20451234567890"}]})
        mock_update.return_value = _np_response({"success": True, "data": [{"Ref": "np-ref-1", "IntDocNumber": "20451234567890"}]})
        mock_tracking.return_value = _np_response({"success": True, "data": [{"StatusCode": "9", "Status": "Отримано"}]})

        create_response = self.client.post(
            reverse("backoffice_api:order-waybill-create", kwargs={"order_id": self.order.id}),
            self._payload(),
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        update_response = self.client.post(
            reverse("backoffice_api:order-waybill-update", kwargs={"order_id": self.order.id}),
            self._payload(),
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        sync_response = self.client.post(
            reverse("backoffice_api:order-waybill-sync", kwargs={"order_id": self.order.id}),
            {},
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sync_response.data["status_code"], "9")

        with patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.delete_waybill") as mock_delete:
            mock_delete.return_value = _np_response({"success": True, "data": [{"Ref": "np-ref-1"}]})
            delete_response = self.client.post(
                reverse("backoffice_api:order-waybill-delete", kwargs={"order_id": self.order.id}),
                {},
                format="json",
                **self._auth(self.staff_token.key),
            )
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertTrue(delete_response.data["is_deleted"])

    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.get_tracking_status")
    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.create_waybill")
    @patch("apps.commerce.services.nova_poshta.client.NovaPoshtaApiClient.get_counterparty_options")
    def test_orders_list_contains_waybill_columns_payload(self, mock_options, mock_create, mock_tracking):
        mock_options.return_value = _np_response({"success": True, "data": [{"CanAfterpaymentOnGoodsCost": True, "CanNonCashPayment": True}]})
        mock_create.return_value = _np_response({"success": True, "data": [{"Ref": "np-ref-1", "IntDocNumber": "20451234567890"}]})
        mock_tracking.return_value = _np_response({"success": True, "data": [{"StatusCode": "1", "Status": "Створено"}]})

        self.client.post(
            reverse("backoffice_api:order-waybill-create", kwargs={"order_id": self.order.id}),
            self._payload(),
            format="json",
            **self._auth(self.staff_token.key),
        )

        list_response = self.client.get(
            reverse("backoffice_api:order-operational-list"),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        row = list_response.data["results"][0]
        self.assertTrue(row["nova_poshta_waybill_exists"])
        self.assertEqual(row["nova_poshta_waybill_number"], "20451234567890")

    def test_non_staff_cannot_manage_waybills(self):
        response = self.client.post(
            reverse("backoffice_api:order-waybill-create", kwargs={"order_id": self.order.id}),
            self._payload(),
            format="json",
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
