from __future__ import annotations

from django.test import TestCase

from apps.catalog.api.serializers.product_detail_serializer import ProductDetailSerializer
from apps.catalog.api.serializers.product_list_serializer import ProductListSerializer
from apps.catalog.models import Brand, Category, Product


class ProductBrandSerializersTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="LEGACY", slug="legacy", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        self.product = Product.objects.create(
            sku="WIX-1",
            article="WIX-1",
            name="Filter",
            slug="filter-1",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=324,
            autodb_supplier_name="WIX FILTERS",
            display_brand_name="WIX FILTERS",
            brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
            is_active=True,
        )

    def test_public_list_serializer_uses_display_brand(self):
        serializer = ProductListSerializer(context={})
        self.assertEqual(serializer.get_display_brand(self.product), "WIX FILTERS")
        self.assertEqual(serializer.get_brand_source(self.product), Product.BRAND_SOURCE_AUTODB_PRO)
        brand_payload = serializer.get_brand(self.product)
        self.assertEqual(brand_payload["name"], "WIX FILTERS")

    def test_public_detail_serializer_uses_display_brand(self):
        serializer = ProductDetailSerializer(context={})
        self.assertEqual(serializer.get_display_brand(self.product), "WIX FILTERS")
        self.assertEqual(serializer.get_brand_source(self.product), Product.BRAND_SOURCE_AUTODB_PRO)
        brand_payload = serializer.get_brand(self.product)
        self.assertEqual(brand_payload["name"], "WIX FILTERS")
