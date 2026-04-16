from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.users.models import User


class BackofficeCatalogBrandsAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="brands-ops@test.local",
            username="brands-ops",
            password="demo12345",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="brands-customer@test.local",
            username="brands-customer",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

        self.existing_brand = Brand.objects.create(
            name="MANN FILTER",
            slug="mann-filter",
            is_active=True,
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_staff_can_list_create_and_update_brands(self):
        list_response = self.client.get(
            reverse("backoffice_api:catalog-brand-list-create"),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)

        create_response = self.client.post(
            reverse("backoffice_api:catalog-brand-list-create"),
            {
                "name": "BOSCH",
                "country": "Germany",
                "description": "OEM supplier",
                "is_active": True,
                "slug": "",
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["name"], "BOSCH")
        self.assertTrue(create_response.data["slug"].startswith("bosch"))

        brand_id = create_response.data["id"]
        update_response = self.client.patch(
            reverse("backoffice_api:catalog-brand-update", kwargs={"id": brand_id}),
            {
                "country": "DE",
                "is_active": False,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["country"], "DE")
        self.assertFalse(update_response.data["is_active"])

        search_response = self.client.get(
            reverse("backoffice_api:catalog-brand-list-create"),
            {"q": "bos"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(search_response.data["count"], 1)

    def test_create_blocks_normalized_duplicate_name(self):
        response = self.client.post(
            reverse("backoffice_api:catalog-brand-list-create"),
            {
                "name": "MANN-FILTER",
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:catalog-brand-list-create"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_delete_unlinked_brand(self):
        response = self.client.delete(
            reverse("backoffice_api:catalog-brand-update", kwargs={"id": self.existing_brand.id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Brand.objects.filter(id=self.existing_brand.id).exists())

    def test_delete_returns_conflict_when_brand_has_products(self):
        category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        Product.objects.create(
            sku="MANN-001",
            article="MANN-001",
            name="MANN Product",
            slug="mann-product",
            brand=self.existing_brand,
            category=category,
            is_active=True,
        )

        response = self.client.delete(
            reverse("backoffice_api:catalog-brand-update", kwargs={"id": self.existing_brand.id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("detail", response.data)
        self.assertGreaterEqual(response.data.get("linked_products", 0), 1)
