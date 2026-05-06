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
            name_uk="0005 Свічка запалювання ART-001",
            name_ru="Свеча зажигания",
            name_en="Spark Plug",
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
        self.assertEqual(response.data["results"][0]["name"], "Свічка запалювання")

    def test_product_detail_works_by_slug_and_article_fallback(self):
        by_slug = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "test-product"}), {"locale": "ru"})
        by_article = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "ART-001"}), {"locale": "en"})

        self.assertEqual(by_slug.status_code, status.HTTP_200_OK)
        self.assertEqual(by_article.status_code, status.HTTP_200_OK)
        self.assertEqual(by_slug.data["id"], str(self.product.id))
        self.assertEqual(by_article.data["id"], str(self.product.id))
        self.assertEqual(by_slug.data["name"], "Свеча зажигания")
        self.assertEqual(by_article.data["name"], "Spark Plug")

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
            available_stock_qty_cached=2,
        )
        high_stock_product = Product.objects.create(
            sku="SKU-HIGH",
            article="ART-HIGH",
            name="ZZZ High Stock",
            slug="zzz-high-stock",
            brand=self.brand,
            category=self.category,
            is_active=True,
            available_stock_qty_cached=25,
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

    def test_popular_query_uses_stock_and_price_fallback_when_featured_empty(self):
        self.product.is_featured = False
        self.product.available_stock_qty_cached = 12
        self.product.save(update_fields=["is_featured", "available_stock_qty_cached", "updated_at"])
        supplier = Supplier.objects.create(name="Supplier Popular", code="supplier-popular", is_active=True)
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="POP-BASE",
            purchase_price="100.00",
            stock_qty=3,
            is_available=True,
        )
        Product.objects.create(
            sku="SKU-POPULAR-2",
            article="ART-POPULAR-2",
            name="Свічка запалювання 2",
            name_uk="Свічка запалювання 2",
            slug="spark-plug-2",
            brand=self.brand,
            category=self.category,
            is_active=True,
            is_featured=False,
            available_stock_qty_cached=5,
        )
        second = Product.objects.get(slug="spark-plug-2")
        ProductPrice.objects.create(product=second, final_price="123.45", currency="UAH")
        SupplierOffer.objects.create(
            supplier=supplier,
            product=second,
            supplier_sku="POP-2",
            purchase_price="70.00",
            stock_qty=5,
            is_available=True,
        )

        response = self.client.get(reverse("catalog_api:product-list"), {"popular": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data["count"], 0)
