from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.users.rbac import set_user_system_role


class LoyaltyBackofficeAPITests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(email="manager-loyalty@test.local", first_name="Manager", password="pass12345", is_staff=True)
        self.operator = User.objects.create_user(email="operator-loyalty@test.local", first_name="Operator", password="pass12345", is_staff=True)
        self.customer = User.objects.create_user(email="customer-loyalty@test.local", first_name="Customer", password="pass12345")

        set_user_system_role(user=self.manager, role_code="manager")
        set_user_system_role(user=self.operator, role_code="operator")

        self.manager_token = Token.objects.create(user=self.manager)
        self.operator_token = Token.objects.create(user=self.operator)

    def test_manager_with_capability_can_issue_promo(self):
        response = self.client.post(
            reverse("backoffice_api:loyalty-issue"),
            {
                "customer_id": self.customer.id,
                "reason": "Retention",
                "discount_type": "delivery_fee",
                "discount_percent": "15.00",
                "usage_limit": 1,
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.manager_token.key}",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("code", response.data)

    def test_operator_without_capability_cannot_issue_promo(self):
        response = self.client.post(
            reverse("backoffice_api:loyalty-issue"),
            {
                "customer_id": self.customer.id,
                "reason": "Retention",
                "discount_type": "delivery_fee",
                "discount_percent": "15.00",
                "usage_limit": 1,
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.operator_token.key}",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
