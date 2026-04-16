from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.users.models import User


class BackofficeCatalogCategoriesAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="categories-ops@test.local",
            username="categories-ops",
            password="demo12345",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="categories-customer@test.local",
            username="categories-customer",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

        self.root_category = Category.objects.create(
            name="Кузовні запчастини",
            slug="kuzovni-zapchastyny",
            is_active=True,
        )
        self.child_category = Category.objects.create(
            name="Підвіска",
            slug="pidviska",
            parent=self.root_category,
            is_active=True,
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_staff_can_list_create_and_update_categories(self):
        list_response = self.client.get(
            reverse("backoffice_api:catalog-category-list-create"),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 2)

        create_response = self.client.post(
            reverse("backoffice_api:catalog-category-list-create"),
            {
                "name": "Фільтри",
                "parent": str(self.child_category.id),
                "is_active": True,
                "slug": "",
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["name"], "Фільтри")
        self.assertEqual(str(create_response.data["parent"]), str(self.child_category.id))
        self.assertTrue(bool(create_response.data["slug"]))

        category_id = create_response.data["id"]
        update_response = self.client.patch(
            reverse("backoffice_api:catalog-category-update", kwargs={"id": category_id}),
            {
                "name": "Паливні фільтри",
                "is_active": False,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["name"], "Паливні фільтри")
        self.assertFalse(update_response.data["is_active"])

        search_response = self.client.get(
            reverse("backoffice_api:catalog-category-list-create"),
            {"q": "підв"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(search_response.data["count"], 1)

    def test_create_blocks_duplicate_name_within_same_parent(self):
        response = self.client.post(
            reverse("backoffice_api:catalog-category-list-create"),
            {
                "name": "ПІДВІСКА",
                "parent": str(self.root_category.id),
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:catalog-category-list-create"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_delete_unlinked_leaf_category(self):
        response = self.client.delete(
            reverse("backoffice_api:catalog-category-update", kwargs={"id": self.child_category.id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=self.child_category.id).exists())

    def test_delete_returns_conflict_when_category_has_products(self):
        brand = Brand.objects.create(name="OEM", slug="oem", is_active=True)
        Product.objects.create(
            sku="CAT-001",
            article="CAT-001",
            name="Category Product",
            slug="category-product",
            brand=brand,
            category=self.child_category,
            is_active=True,
        )

        response = self.client.delete(
            reverse("backoffice_api:catalog-category-update", kwargs={"id": self.child_category.id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("detail", response.data)
        self.assertGreaterEqual(response.data.get("linked_products", 0), 1)
