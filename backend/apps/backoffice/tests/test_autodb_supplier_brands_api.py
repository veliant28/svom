from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.users.models import User


class BackofficeAutoDbSupplierBrandsApiTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="autodb-supplier-brands-staff@test.local",
            first_name="autodb-supplier-brands-staff",
            password="demo12345",
            is_staff=True,
            is_superuser=True,
        )
        self.regular_user = User.objects.create_user(
            email="autodb-supplier-brands-regular@test.local",
            first_name="autodb-supplier-brands-regular",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    @patch("apps.backoffice.api.views.autodb_supplier_brands_views.list_admin_supplier_brands")
    def test_staff_can_list_autodb_supplier_brands(self, selector_mock):
        selector_mock.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 10,
                    "name": "BOSCH",
                    "matchcode": "BOSCH",
                    "article_count": 123,
                    "is_active": True,
                }
            ],
        }

        response = self.client.get(
            reverse("backoffice_api:autodb-supplier-brand-list"),
            {"q": "bos", "is_active": "true", "page": 2, "page_size": 50},
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "BOSCH")
        selector_mock.assert_called_once_with(
            q="bos",
            is_active=True,
            page=2,
            page_size=50,
        )

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:autodb-supplier-brand-list"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
