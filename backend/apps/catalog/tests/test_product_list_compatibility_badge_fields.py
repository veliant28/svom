from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice


class ProductListCompatibilityBadgeFieldsTests(APITestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        category = Category.objects.create(name="Масла", slug="oils", is_active=True)

        self.trusted = Product.objects.create(
            sku="GPL-0001",
            article="ART-1",
            name="Oil Trusted",
            slug="oil-trusted",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=494,
            autodb_article_number="1462",
            autodb_article_key="494:1462",
        )
        self.excluded = Product.objects.create(
            sku="GPL-0002",
            article="ART-2",
            name="Oil Excluded",
            slug="oil-excluded",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=494,
            autodb_article_number="1463",
            autodb_article_key="494:1463",
        )

        ProductPrice.objects.create(product=self.trusted, final_price="100.00", currency="UAH")
        ProductPrice.objects.create(product=self.excluded, final_price="100.00", currency="UAH")

        AutoDbProductLinkQuality.objects.create(
            product=self.trusted,
            autodb_article_key=self.trusted.autodb_article_key,
            autodb_supplier_id=494,
            autodb_article_number="1462",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={},
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.excluded,
            autodb_article_key=self.excluded.autodb_article_key,
            autodb_supplier_id=494,
            autodb_article_number="1463",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="",
            evidence={},
        )

        ProductFitment.objects.create(
            product=self.trusted,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=677,
            linkage_type="PassengerCar",
            autodb_article_key=self.trusted.autodb_article_key,
            supplier_id=494,
            article_number="1462",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            is_stale=False,
        )
        ProductFitment.objects.create(
            product=self.excluded,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=677,
            linkage_type="PassengerCar",
            autodb_article_key=self.excluded.autodb_article_key,
            supplier_id=494,
            article_number="1463",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=True,
            is_stale=False,
        )

    def test_list_exposes_compatibility_badge_fields(self):
        response = self.client.get(reverse("catalog_api:product-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = next(row for row in response.data["results"] if row["slug"] == self.trusted.slug)
        self.assertIn("fitment_count", item)
        self.assertIn("is_autodb_compatible_data_available", item)
        self.assertIn("link_quality_status", item)
        self.assertIn("selected_vehicle_compatibility", item)
        self.assertEqual(item["fitment_count"], 1)
        self.assertTrue(item["is_autodb_compatible_data_available"])
        self.assertEqual(item["link_quality_status"], AutoDbProductLinkQuality.STATUS_TRUSTED)
        self.assertIsNone(item["selected_vehicle_compatibility"])

    def test_selected_vehicle_compatibility_and_excluded_fitments(self):
        response = self.client.get(
            reverse("catalog_api:product-list"),
            {"vehicle_id": "677", "fitment": "all"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = {row["slug"]: row for row in response.data["results"]}

        trusted = rows[self.trusted.slug]
        self.assertTrue(trusted["fits_selected_vehicle"])
        self.assertEqual(
            trusted["selected_vehicle_compatibility"],
            {"vehicle_id": 677, "is_compatible": True},
        )

        excluded = rows[self.excluded.slug]
        self.assertFalse(excluded["fits_selected_vehicle"])
        self.assertEqual(excluded["fitment_count"], 0)
        self.assertFalse(excluded["is_autodb_compatible_data_available"])
