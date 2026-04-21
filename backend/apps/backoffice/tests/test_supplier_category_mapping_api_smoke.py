from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Category
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User


class SupplierCategoryMappingAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="ops-category-map@test.local",
            first_name="ops-category-map",
            password="demo12345",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="customer-category-map@test.local",
            first_name="customer-category-map",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

        self.root_category = Category.objects.create(name="Двигун", slug="dvygun", is_active=True)
        self.leaf_category = Category.objects.create(name="Фільтри", slug="filtry", parent=self.root_category, is_active=True)
        self.secondary_category = Category.objects.create(name="Гальма", slug="halma", is_active=True)

        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test")
        self.raw_offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="SKU-001",
            article="ART-001",
            normalized_article="ART001",
            brand_name="TEST",
            normalized_brand="TEST",
            product_name="Фільтр масляний",
            currency="UAH",
            price=Decimal("100.00"),
            stock_qty=3,
            is_valid=False,
            skip_reason="unmatched",
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_staff_can_get_set_and_clear_category_mapping(self):
        detail_response = self.client.get(
            reverse("backoffice_api:raw-offer-category-mapping", kwargs={"raw_offer_id": self.raw_offer.id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["category_mapping_status"], SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED)

        save_response = self.client.patch(
            reverse("backoffice_api:raw-offer-category-mapping", kwargs={"raw_offer_id": self.raw_offer.id}),
            {"category_id": str(self.leaf_category.id)},
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)
        self.assertEqual(save_response.data["category_mapping_status"], SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED)
        self.assertIsNotNone(save_response.data["mapped_category"])
        self.assertEqual(save_response.data["mapped_category"]["id"], str(self.leaf_category.id))

        clear_response = self.client.delete(
            reverse("backoffice_api:raw-offer-category-mapping", kwargs={"raw_offer_id": self.raw_offer.id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(clear_response.status_code, status.HTTP_200_OK)
        self.assertEqual(clear_response.data["category_mapping_status"], SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED)
        self.assertIsNone(clear_response.data["mapped_category"])

    def test_staff_can_search_categories_with_breadcrumbs(self):
        response = self.client.get(
            reverse("backoffice_api:raw-offer-category-search"),
            {"q": "фільтр", "locale": "uk"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 1)
        first = response.data["results"][0]
        self.assertIn("breadcrumb", first)
        self.assertIn("name", first)
        self.assertIn("is_leaf", first)

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:raw-offer-category-search"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
