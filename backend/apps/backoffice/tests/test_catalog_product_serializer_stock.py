from __future__ import annotations

from django.test import TestCase

from apps.backoffice.api.serializers import BackofficeCatalogProductSerializer
from apps.catalog.models import Brand, Product
from apps.pricing.models import Supplier, SupplierOffer


class BackofficeCatalogProductSerializerStockTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-1",
            article="ART-1",
            name="Product 1",
            slug="product-1",
            brand=self.brand,
            is_active=True,
            available_stock_qty_cached=0,
        )
        self.supplier = Supplier.objects.create(name="Supplier 1", code="supplier-1", is_active=True)
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="SUP-1",
            purchase_price="100.00",
            stock_qty=5,
            is_available=True,
        )

    def test_serializer_uses_supplier_offer_stock_when_cached_empty(self):
        payload = BackofficeCatalogProductSerializer(instance=self.product).data
        self.assertEqual(payload["stock_qty"], 5)
        self.assertEqual(payload["supplier_offer_stock_sum"], 5)
        self.assertEqual(payload["supplier_code"], "supplier-1")
        self.assertEqual(payload["supplier_codes"], ["supplier-1"])
        self.assertTrue(payload["has_available_offer"])
        self.assertFalse(payload["has_product_price"])
        self.assertEqual(payload["productprice_status"], "no_product_price")

    def test_serializer_prefers_cached_stock_when_present(self):
        self.product.available_stock_qty_cached = 9
        self.product.save(update_fields=["available_stock_qty_cached", "updated_at"])

        payload = BackofficeCatalogProductSerializer(instance=self.product).data
        self.assertEqual(payload["stock_qty"], 9)
        self.assertEqual(payload["supplier_offer_stock_sum"], 5)
