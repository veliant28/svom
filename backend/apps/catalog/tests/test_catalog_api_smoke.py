from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer


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

    def test_products_endpoint_orders_by_available_stock_desc_by_default(self):
        supplier = Supplier.objects.create(name="Supplier A", code="supplier-a", is_active=True)
        low_stock_product = Product.objects.create(
            sku="SKU-LOW",
            article="ART-LOW",
            name="AAA Low Stock",
            slug="aaa-low-stock",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        high_stock_product = Product.objects.create(
            sku="SKU-HIGH",
            article="ART-HIGH",
            name="ZZZ High Stock",
            slug="zzz-high-stock",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=low_stock_product, final_price="199.99", currency="UAH")
        ProductPrice.objects.create(product=high_stock_product, final_price="199.99", currency="UAH")
        SupplierOffer.objects.create(
            supplier=supplier,
            product=low_stock_product,
            supplier_sku="LOW-1",
            purchase_price="100.00",
            stock_qty=2,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=supplier,
            product=high_stock_product,
            supplier_sku="HIGH-1",
            purchase_price="100.00",
            stock_qty=25,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="BASE-UNAVAILABLE",
            purchase_price="100.00",
            stock_qty=1000,
            is_available=False,
        )

        response = self.client.get(reverse("catalog_api:product-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["slug"] for item in response.data["results"]],
            ["zzz-high-stock", "aaa-low-stock", "test-product"],
        )
