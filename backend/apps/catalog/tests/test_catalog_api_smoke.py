from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice


class CatalogAPISmokeTests(APITestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand A", slug="brand-a", is_active=True)
        self.category = Category.objects.create(name="Category A", slug="category-a", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-001",
            article="ART-001",
            name="Test Product",
            slug="test-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="199.99", currency="UAH")

    def test_products_endpoint_returns_data(self):
        response = self.client.get(reverse("catalog_api:product-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "test-product")
