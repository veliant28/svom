from __future__ import annotations

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment


@override_settings(FITMENT_PROVIDER="autodb")
class CommercialVehicleFitmentVisibilityTests(APITestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        brand = Brand.objects.create(name="Brand CV", slug="brand-cv", is_active=True)
        category = Category.objects.create(name="Category CV", slug="category-cv", is_active=True)
        self.product = Product.objects.create(
            sku="CV-ONLY-1",
            article="CV-ONLY-1",
            name="Commercial Only Product",
            slug="commercial-only-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="CV-ONLY-1",
            autodb_article_key="324:CV-ONLY-1",
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.product,
            autodb_article_key="324:CV-ONLY-1",
            autodb_supplier_id=324,
            autodb_article_number="CV-ONLY-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        ProductFitment.objects.create(
            product=self.product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=900,
            linkage_type="CommercialVehicle",
            autodb_article_key="324:CV-ONLY-1",
            supplier_id=324,
            article_number="CV-ONLY-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )

    def test_detail_exposes_commercial_fitment_as_compatibility(self):
        response = self.client.get(f"/api/catalog/products/{self.product.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_fitment_data"])
        self.assertGreater(response.data["fitment_count"], 0)
        self.assertTrue(response.data["compatibility_summary"]["available"])
        self.assertEqual(response.data["compatibility_summary"]["fitment_count"], response.data["fitment_count"])

    def test_selected_vehicle_compatibility_stays_passenger_only(self):
        response = self.client.get(f"/api/catalog/products/{self.product.slug}/?vehicle_id=900")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        selected_vehicle = response.data["compatibility_summary"]["selected_vehicle"]
        self.assertIsNotNone(selected_vehicle)
        self.assertFalse(selected_vehicle["is_compatible"])
