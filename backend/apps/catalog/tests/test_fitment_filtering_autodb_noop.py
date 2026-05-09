from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.catalog.services.fitment_filtering import FitmentFilteringService
from apps.compatibility.models import ProductFitment
from apps.users.models import GarageVehicle


@override_settings(FITMENT_PROVIDER="autodb")
class FitmentFilteringAutodbNoopTests(TestCase):
    def test_autodb_source_product_fitments_do_not_enable_public_fitment_mode(self):
        brand = Brand.objects.create(name="Brand", slug="brand-fitment-noop", is_active=True)
        category = Category.objects.create(name="Category", slug="category-fitment-noop", is_active=True)
        product = Product.objects.create(
            sku="NOOP-FIT-1",
            article="NOOP-FIT-1",
            name="Noop Fitment Product",
            slug="noop-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductFitment.objects.create(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=101,
            linkage_type="PassengerCar",
            autodb_article_key="324:92131E",
            supplier_id=324,
            article_number="92131E",
            note="Auto-DB Pro applicability",
            is_exact=False,
        )

        queryset = Product.objects.filter(id=product.id)
        filtered, _ = FitmentFilteringService().apply(queryset=queryset, params={"fitment": "with_data"})

        self.assertEqual(filtered.count(), 0)

    def test_autodb_trusted_fitments_enable_vehicle_filter_and_needs_review_is_excluded(self):
        brand = Brand.objects.create(name="Brand 2", slug="brand-fitment-trusted", is_active=True)
        category = Category.objects.create(name="Category 2", slug="category-fitment-trusted", is_active=True)
        trusted = Product.objects.create(
            sku="TRUST-FIT-1",
            article="TRUST-FIT-1",
            name="Trusted Fitment Product",
            slug="trusted-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="TRUST-FIT-1",
            autodb_article_key="324:TRUST-FIT-1",
        )
        review = Product.objects.create(
            sku="REVIEW-FIT-1",
            article="REVIEW-FIT-1",
            name="Review Fitment Product",
            slug="review-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="REVIEW-FIT-1",
            autodb_article_key="324:REVIEW-FIT-1",
        )
        ProductFitment.objects.create(
            product=trusted,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=901,
            linkage_type="PassengerCar",
            autodb_article_key="324:TRUST-FIT-1",
            supplier_id=324,
            article_number="TRUST-FIT-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        ProductFitment.objects.create(
            product=review,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=901,
            linkage_type="PassengerCar",
            autodb_article_key="324:REVIEW-FIT-1",
            supplier_id=324,
            article_number="REVIEW-FIT-1",
            quality_status=ProductFitment.QUALITY_STATUS_NEEDS_MANUAL_REVIEW,
            excluded_from_public_filtering=True,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        AutoDbProductLinkQuality.objects.create(
            product=trusted,
            autodb_article_key="324:TRUST-FIT-1",
            autodb_supplier_id=324,
            autodb_article_number="TRUST-FIT-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        AutoDbProductLinkQuality.objects.create(
            product=review,
            autodb_article_key="324:REVIEW-FIT-1",
            autodb_supplier_id=324,
            autodb_article_number="REVIEW-FIT-1",
            status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
            reason="manual_review",
            evidence={"source": "test"},
        )

        queryset = Product.objects.filter(id__in=[trusted.id, review.id]).order_by("slug")
        filtered, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params={"fitment": "only", "vehicle_id": "901"},
        )

        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().id, trusted.id)

    def test_autodb_fitment_with_non_trusted_link_quality_is_excluded(self):
        brand = Brand.objects.create(name="Brand 3", slug="brand-fitment-susp", is_active=True)
        category = Category.objects.create(name="Category 3", slug="category-fitment-susp", is_active=True)
        suspicious = Product.objects.create(
            sku="SUSP-FIT-1",
            article="SUSP-FIT-1",
            name="Suspicious Fitment Product",
            slug="suspicious-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="SUSP-FIT-1",
            autodb_article_key="324:SUSP-FIT-1",
        )
        ProductFitment.objects.create(
            product=suspicious,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=902,
            linkage_type="PassengerCar",
            autodb_article_key="324:SUSP-FIT-1",
            supplier_id=324,
            article_number="SUSP-FIT-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        AutoDbProductLinkQuality.objects.create(
            product=suspicious,
            autodb_article_key="324:SUSP-FIT-1",
            autodb_supplier_id=324,
            autodb_article_number="SUSP-FIT-1",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="quality_flag",
            evidence={"source": "test"},
        )

        queryset = Product.objects.filter(id=suspicious.id)
        filtered, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params={"fitment": "only", "vehicle_id": "902"},
        )

        self.assertEqual(filtered.count(), 0)

    def test_unknown_vehicle_id_returns_empty_for_fitment_only(self):
        brand = Brand.objects.create(name="Brand 4", slug="brand-fitment-empty", is_active=True)
        category = Category.objects.create(name="Category 4", slug="category-fitment-empty", is_active=True)
        product = Product.objects.create(
            sku="EMPTY-FIT-1",
            article="EMPTY-FIT-1",
            name="Empty Fitment Product",
            slug="empty-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="EMPTY-FIT-1",
            autodb_article_key="324:EMPTY-FIT-1",
        )
        ProductFitment.objects.create(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=77701,
            linkage_type="PassengerCar",
            autodb_article_key="324:EMPTY-FIT-1",
            supplier_id=324,
            article_number="EMPTY-FIT-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        AutoDbProductLinkQuality.objects.create(
            product=product,
            autodb_article_key="324:EMPTY-FIT-1",
            autodb_supplier_id=324,
            autodb_article_number="EMPTY-FIT-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )

        queryset = Product.objects.filter(id=product.id)
        filtered, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params={"fitment": "only", "vehicle_id": "999999"},
        )

        self.assertEqual(filtered.count(), 0)

    def test_legacy_vehicle_params_are_not_used_for_utr_compatibility(self):
        brand = Brand.objects.create(name="Brand 5", slug="brand-fitment-legacy", is_active=True)
        category = Category.objects.create(name="Category 5", slug="category-fitment-legacy", is_active=True)
        product = Product.objects.create(
            sku="LEGACY-FIT-1",
            article="LEGACY-FIT-1",
            name="Legacy Fitment Product",
            slug="legacy-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="LEGACY-FIT-1",
            autodb_article_key="324:LEGACY-FIT-1",
        )
        queryset = Product.objects.filter(id=product.id)
        filtered, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params={"fitment": "only", "car_modification": "123"},
        )
        self.assertEqual(filtered.count(), 0)

    def test_garage_vehicle_with_autodb_passanger_car_id_is_used_for_filter(self):
        brand = Brand.objects.create(name="Brand 6", slug="brand-fitment-garage", is_active=True)
        category = Category.objects.create(name="Category 6", slug="category-fitment-garage", is_active=True)
        product = Product.objects.create(
            sku="GARAGE-FIT-1",
            article="GARAGE-FIT-1",
            name="Garage Fitment Product",
            slug="garage-fitment-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="GARAGE-FIT-1",
            autodb_article_key="324:GARAGE-FIT-1",
        )
        ProductFitment.objects.create(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=88801,
            linkage_type="PassengerCar",
            autodb_article_key="324:GARAGE-FIT-1",
            supplier_id=324,
            article_number="GARAGE-FIT-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        AutoDbProductLinkQuality.objects.create(
            product=product,
            autodb_article_key="324:GARAGE-FIT-1",
            autodb_supplier_id=324,
            autodb_article_number="GARAGE-FIT-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        user = get_user_model().objects.create_user(
            username="fitment-garage-user",
            email="fitment-garage@example.com",
            password="test-pass-123",
        )
        garage_vehicle = GarageVehicle.objects.create(
            user=user,
            catalog_source=GarageVehicle.CATALOG_SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=88801,
            autodb_vehicle_label="AutoDB Garage Vehicle",
            is_primary=True,
        )

        queryset = Product.objects.filter(id=product.id)
        filtered, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params={"fitment": "only", "garage_vehicle": str(garage_vehicle.id)},
        )
        self.assertEqual(filtered.count(), 1)
