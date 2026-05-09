from __future__ import annotations

from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product


@override_settings(FITMENT_PROVIDER="autodb")
class CatalogNoUtrRuntimeCallsTests(APITestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        brand = Brand.objects.create(name="No UTR Brand", slug="no-utr-runtime-brand", is_active=True)
        category = Category.objects.create(name="No UTR Category", slug="no-utr-runtime-category", is_active=True)
        self.product = Product.objects.create(
            sku="NO-UTR-1",
            article="NO-UTR-1",
            name="No UTR Runtime Product",
            slug="no-utr-runtime-product",
            brand=brand,
            category=category,
            is_active=True,
        )

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient.fetch_detail")
    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient.fetch_characteristics")
    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient.fetch_applicability")
    def test_public_list_and_detail_do_not_call_utr_catalog_client(
        self,
        fetch_applicability_mock,
        fetch_characteristics_mock,
        fetch_detail_mock,
    ):
        fetch_detail_mock.side_effect = AssertionError("UTR fetch_detail must not be called in catalog runtime.")
        fetch_characteristics_mock.side_effect = AssertionError(
            "UTR fetch_characteristics must not be called in catalog runtime."
        )
        fetch_applicability_mock.side_effect = AssertionError(
            "UTR fetch_applicability must not be called in catalog runtime."
        )

        list_response = self.client.get("/api/catalog/products/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        detail_response = self.client.get(f"/api/catalog/products/{self.product.slug}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
