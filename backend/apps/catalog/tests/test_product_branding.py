from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.catalog.models import Product
from apps.catalog.services.product_branding import get_product_display_brand_payload


class ProductBrandingTests(SimpleTestCase):
    def test_linked_product_uses_autodb_supplier_name(self):
        product = SimpleNamespace(
            autodb_supplier_id=324,
            autodb_supplier_name="WIX FILTERS",
            display_brand_name="OLD BRAND",
            brand_source=Product.BRAND_SOURCE_MANUAL,
            brand=SimpleNamespace(name="Legacy"),
        )
        payload = get_product_display_brand_payload(product)
        self.assertEqual(payload.display_brand, "WIX FILTERS")
        self.assertEqual(payload.brand_source, Product.BRAND_SOURCE_AUTODB_PRO)

    def test_unlinked_product_uses_cached_display_brand(self):
        product = SimpleNamespace(
            autodb_supplier_id=None,
            autodb_supplier_name="",
            display_brand_name="NGK",
            brand_source=Product.BRAND_SOURCE_SUPPLIER_FALLBACK,
            brand=SimpleNamespace(name="Legacy NGK"),
        )
        payload = get_product_display_brand_payload(product)
        self.assertEqual(payload.display_brand, "NGK")
        self.assertEqual(payload.brand_source, Product.BRAND_SOURCE_SUPPLIER_FALLBACK)

    def test_no_cached_brand_falls_back_to_legacy_brand_for_unlinked(self):
        product = SimpleNamespace(
            autodb_supplier_id=None,
            autodb_supplier_name="",
            display_brand_name="",
            brand_source="",
            normalized_brand="",
            brand=SimpleNamespace(name="Legacy"),
        )
        payload = get_product_display_brand_payload(product)
        self.assertEqual(payload.display_brand, "Legacy")
        self.assertEqual(payload.brand_source, Product.BRAND_SOURCE_SUPPLIER_FALLBACK)
