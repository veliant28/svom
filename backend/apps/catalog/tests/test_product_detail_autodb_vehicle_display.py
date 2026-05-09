from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice


class ProductDetailAutoDbVehicleDisplayTests(APITestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        brand = Brand.objects.create(name="BRISK", slug="brisk", is_active=True)
        category = Category.objects.create(name="Свечи", slug="spark-plugs", is_active=True)
        self.product = Product.objects.create(
            sku="GPL-000000000024868",
            article="1462",
            name="BRISK Silver DR15YS9-1",
            slug="brisk-silver-dr15ys9-1-1462",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=494,
            autodb_article_number="1462",
            autodb_article_key="494:1462",
        )
        ProductPrice.objects.create(product=self.product, final_price="100.00", currency="UAH")
        AutoDbProductLinkQuality.objects.create(
            product=self.product,
            autodb_article_key="494:1462",
            autodb_supplier_id=494,
            autodb_article_number="1462",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        ProductFitment.objects.create(
            product=self.product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=677,
            linkage_type="PassengerCar",
            autodb_article_key="494:1462",
            supplier_id=494,
            article_number="1462",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )

    @patch("apps.catalog.api.serializers.product_detail_serializer.get_autodb_product_content", return_value=SimpleNamespace(image_urls=[]))
    @patch(
        "apps.catalog.services.product_fitment_lookup.list_passanger_cars_by_ids",
        return_value={
            677: {
                "vehicle_id": 677,
                "model_id": 1234,
                "make": "Volkswagen",
                "model": "Golf IV",
                "modification": "1.4 16V",
                "years": "1997–2005",
                "engine": "1.4 бензин · 55 kW / 75 hp",
                "body": "",
                "label": "Volkswagen Golf IV 1.4 16V (1997–2005)",
                "subtitle": "1.4 бензин · 55 kW / 75 hp",
            }
        },
    )
    def test_product_detail_uses_readable_selected_vehicle_label_when_selector_has_metadata(self, _selector_mock, _content_mock):
        response = self.client.get(
            reverse("catalog_api:product-detail", kwargs={"slug": self.product.slug}),
            {"vehicle_id": "677"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = response.data["compatibility_summary"]
        self.assertTrue(summary["available"])
        self.assertEqual(summary["fitment_count"], 1)
        self.assertTrue(summary["selected_vehicle"]["is_compatible"])
        self.assertIn("Volkswagen Golf IV", summary["selected_vehicle"]["label"])
        self.assertNotIn("PassengerCar #", summary["selected_vehicle"]["label"])

        fitments = response.data["fitments"]
        self.assertGreaterEqual(len(fitments), 1)
        self.assertIn("Volkswagen Golf IV", fitments[0]["label"])
        self.assertNotIn("PassengerCar #", fitments[0]["label"])

    @patch("apps.catalog.api.serializers.product_detail_serializer.get_autodb_product_content", return_value=SimpleNamespace(image_urls=[]))
    @patch(
        "apps.catalog.services.product_fitment_lookup.list_passanger_cars_by_ids",
        return_value={
            677: {
                "vehicle_id": 677,
                "model_id": 1234,
                "make": "Volkswagen",
                "model": "Golf IV",
                "modification": "1.4 16V",
                "years": "1997–2005",
                "engine": "",
                "body": "",
                "label": "Volkswagen Golf IV 1.4 16V (1997–2005)",
                "subtitle": "",
            }
        },
    )
    def test_fitment_options_fallback_uses_selector_vehicle_metadata(self, _selector_mock, _content_mock):
        response = self.client.get(
            reverse("catalog_api:product-fitment-options", kwargs={"slug": self.product.slug}),
            {"vehicle_id": "677"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_fitments"], 1)
        self.assertEqual(response.data["selected_modification"], "677")
        self.assertIn({"value": "Volkswagen", "label": "Volkswagen"}, response.data["makes"])
        self.assertIn({"value": "Golf IV", "label": "Golf IV"}, response.data["models"])
        self.assertTrue(any(option["value"] == "677" for option in response.data["modifications"]))
