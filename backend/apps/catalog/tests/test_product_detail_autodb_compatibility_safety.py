from __future__ import annotations

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment


@override_settings(FITMENT_PROVIDER="autodb")
class ProductDetailAutoDbCompatibilitySafetyTests(APITestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        brand = Brand.objects.create(name="Brand", slug="detail-compat-brand", is_active=True)
        category = Category.objects.create(name="Category", slug="detail-compat-category", is_active=True)

        self.clean = Product.objects.create(
            sku="DETAIL-CLEAN-1",
            article="DETAIL-CLEAN-1",
            name="Detail Clean",
            slug="detail-clean",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="DETAIL-CLEAN-1",
            autodb_article_key="324:DETAIL-CLEAN-1",
        )
        self.suspicious = Product.objects.create(
            sku="DETAIL-SUSP-1",
            article="DETAIL-SUSP-1",
            name="Detail Suspicious",
            slug="detail-suspicious",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="DETAIL-SUSP-1",
            autodb_article_key="324:DETAIL-SUSP-1",
        )
        self.needs_review = Product.objects.create(
            sku="DETAIL-REVIEW-1",
            article="DETAIL-REVIEW-1",
            name="Detail Review",
            slug="detail-review",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="DETAIL-REVIEW-1",
            autodb_article_key="324:DETAIL-REVIEW-1",
        )

        AutoDbProductLinkQuality.objects.create(
            product=self.clean,
            autodb_article_key="324:DETAIL-CLEAN-1",
            autodb_supplier_id=324,
            autodb_article_number="DETAIL-CLEAN-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.suspicious,
            autodb_article_key="324:DETAIL-SUSP-1",
            autodb_supplier_id=324,
            autodb_article_number="DETAIL-SUSP-1",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="suspicious",
            evidence={"source": "test"},
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.needs_review,
            autodb_article_key="324:DETAIL-REVIEW-1",
            autodb_supplier_id=324,
            autodb_article_number="DETAIL-REVIEW-1",
            status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
            reason="needs_review",
            evidence={"source": "test"},
        )

        ProductFitment.objects.create(
            product=self.clean,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=123,
            linkage_type="PassengerCar",
            autodb_article_key="324:DETAIL-CLEAN-1",
            supplier_id=324,
            article_number="DETAIL-CLEAN-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        ProductFitment.objects.create(
            product=self.suspicious,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=124,
            linkage_type="PassengerCar",
            autodb_article_key="324:DETAIL-SUSP-1",
            supplier_id=324,
            article_number="DETAIL-SUSP-1",
            quality_status=ProductFitment.QUALITY_STATUS_SUSPICIOUS,
            excluded_from_public_filtering=True,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        ProductFitment.objects.create(
            product=self.needs_review,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=125,
            linkage_type="PassengerCar",
            autodb_article_key="324:DETAIL-REVIEW-1",
            supplier_id=324,
            article_number="DETAIL-REVIEW-1",
            quality_status=ProductFitment.QUALITY_STATUS_NEEDS_MANUAL_REVIEW,
            excluded_from_public_filtering=True,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )

    def test_clean_trusted_product_exposes_compatibility(self):
        response = self.client.get(f"/api/catalog/products/{self.clean.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_autodb_compatible_data_available"])
        self.assertGreater(response.data["fitment_count"], 0)
        self.assertEqual(response.data["link_quality_status"], AutoDbProductLinkQuality.STATUS_TRUSTED)

    def test_suspicious_and_needs_review_products_do_not_expose_usable_compatibility(self):
        suspicious_response = self.client.get(f"/api/catalog/products/{self.suspicious.slug}/")
        self.assertEqual(suspicious_response.status_code, status.HTTP_200_OK)
        self.assertFalse(suspicious_response.data["is_autodb_compatible_data_available"])
        self.assertEqual(suspicious_response.data["fitment_count"], 0)
        self.assertEqual(
            suspicious_response.data["link_quality_status"],
            AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
        )

        review_response = self.client.get(f"/api/catalog/products/{self.needs_review.slug}/")
        self.assertEqual(review_response.status_code, status.HTTP_200_OK)
        self.assertFalse(review_response.data["is_autodb_compatible_data_available"])
        self.assertEqual(review_response.data["fitment_count"], 0)
        self.assertEqual(
            review_response.data["link_quality_status"],
            AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        )
