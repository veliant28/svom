from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.commerce.models import CheckoutMethodSettings
from apps.users.models import User
from apps.users.rbac import set_user_system_role


class BackofficeCheckoutMethodSettingsAPITests(APITestCase):
    def setUp(self):
        self.administrator = User.objects.create_user(
            email="admin-checkout-methods@test.local",
            first_name="Admin",
            password="pass12345",
            is_staff=True,
        )
        self.manager = User.objects.create_user(
            email="manager-checkout-methods@test.local",
            first_name="Manager",
            password="pass12345",
            is_staff=True,
        )
        set_user_system_role(user=self.administrator, role_code="administrator")
        set_user_system_role(user=self.manager, role_code="manager")
        self.admin_token = Token.objects.create(user=self.administrator)
        self.manager_token = Token.objects.create(user=self.manager)

    def test_administrator_can_read_and_update_checkout_methods(self):
        url = reverse("backoffice_api:payments-checkout-methods")

        get_response = self.client.get(url, HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertTrue(get_response.data["pickup_enabled"])
        self.assertTrue(get_response.data["novapay_enabled"])

        patch_response = self.client.patch(
            url,
            {
                "pickup_enabled": False,
                "cash_on_delivery_enabled": False,
                "novapay_enabled": False,
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        settings = CheckoutMethodSettings.objects.get(code=CheckoutMethodSettings.DEFAULT_CODE)
        self.assertFalse(settings.pickup_enabled)
        self.assertFalse(settings.cash_on_delivery_enabled)
        self.assertFalse(settings.novapay_enabled)

    def test_manager_without_capability_cannot_access_checkout_methods(self):
        response = self.client.get(
            reverse("backoffice_api:payments-checkout-methods"),
            HTTP_AUTHORIZATION=f"Token {self.manager_token.key}",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_disable_all_delivery_or_payment_methods(self):
        url = reverse("backoffice_api:payments-checkout-methods")

        delivery_response = self.client.patch(
            url,
            {
                "pickup_enabled": False,
                "nova_poshta_enabled": False,
                "courier_enabled": False,
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )
        self.assertEqual(delivery_response.status_code, status.HTTP_400_BAD_REQUEST)

        payment_response = self.client.patch(
            url,
            {
                "cash_on_delivery_enabled": False,
                "monobank_enabled": False,
                "novapay_enabled": False,
                "liqpay_enabled": False,
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )
        self.assertEqual(payment_response.status_code, status.HTTP_400_BAD_REQUEST)
