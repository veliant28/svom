from __future__ import annotations

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment


@override_settings(FITMENT_PROVIDER="autodb")
class CatalogVehicleFilterStrictAutoDbTests(APITestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.brand = Brand.objects.create(name="AutoDb Brand", slug="autodb-strict-brand", is_active=True)
        self.category = Category.objects.create(name="AutoDb Category", slug="autodb-strict-category", is_active=True)

        self.trusted = Product.objects.create(
            sku="AUTODB-STRICT-1",
            article="AUTODB-STRICT-1",
            name="Trusted Product",
            slug="autodb-strict-trusted",
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="AUTODB-STRICT-1",
            autodb_article_key="324:AUTODB-STRICT-1",
        )
        self.suspicious = Product.objects.create(
            sku="AUTODB-STRICT-2",
            article="AUTODB-STRICT-2",
            name="Suspicious Product",
            slug="autodb-strict-suspicious",
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="AUTODB-STRICT-2",
            autodb_article_key="324:AUTODB-STRICT-2",
        )
        self.unlinked = Product.objects.create(
            sku="AUTODB-STRICT-3",
            article="AUTODB-STRICT-3",
            name="Unlinked Product",
            slug="autodb-strict-unlinked",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        AutoDbProductLinkQuality.objects.create(
            product=self.trusted,
            autodb_article_key="324:AUTODB-STRICT-1",
            autodb_supplier_id=324,
            autodb_article_number="AUTODB-STRICT-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.suspicious,
            autodb_article_key="324:AUTODB-STRICT-2",
            autodb_supplier_id=324,
            autodb_article_number="AUTODB-STRICT-2",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="suspicious",
            evidence={"source": "test"},
        )

        ProductFitment.objects.create(
            product=self.trusted,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=5001,
            linkage_type="PassengerCar",
            autodb_article_key="324:AUTODB-STRICT-1",
            supplier_id=324,
            article_number="AUTODB-STRICT-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        ProductFitment.objects.create(
            product=self.suspicious,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=5001,
            linkage_type="PassengerCar",
            autodb_article_key="324:AUTODB-STRICT-2",
            supplier_id=324,
            article_number="AUTODB-STRICT-2",
            quality_status=ProductFitment.QUALITY_STATUS_SUSPICIOUS,
            excluded_from_public_filtering=True,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )

    def test_vehicle_filter_returns_only_matching_trusted_products(self):
        response = self.client.get(f"/api/catalog/products/?vehicle_id=5001&fitment=only&category_id={self.category.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.trusted.id))

    def test_without_vehicle_filter_returns_active_public_products(self):
        response = self.client.get("/api/catalog/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_vehicle_id_without_matches_returns_zero_not_full_catalog(self):
        response = self.client.get("/api/catalog/products/?vehicle_id=999999&fitment=only")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_invalid_vehicle_value_does_not_fallback_to_all_products(self):
        response = self.client.get("/api/catalog/products/?vehicle_id=bad-value&fitment=only")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_legacy_car_modification_param_is_ignored_for_compatibility(self):
        response = self.client.get("/api/catalog/products/?car_modification=123&fitment=only")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_wheels_root_vehicle_filter_returns_all_category_products_with_badges(self):
        root = Category.objects.create(name="Колёса и шины", slug="kolesa-i-shiny", is_active=True)
        child = Category.objects.create(name="Шины", slug="tires-policy-child", parent=root, is_active=True)
        matching = self._create_autodb_product(
            slug="wheels-policy-matching",
            sku="WHEELS-POLICY-1",
            category=child,
            link_status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            fitment_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded=False,
            vehicle_id=5001,
        )
        no_fitment = Product.objects.create(
            sku="WHEELS-POLICY-2",
            article="WHEELS-POLICY-2",
            name="Wheels No Fitment",
            slug="wheels-policy-no-fitment",
            brand=self.brand,
            category=child,
            is_active=True,
        )
        suspicious = self._create_autodb_product(
            slug="wheels-policy-suspicious",
            sku="WHEELS-POLICY-3",
            category=child,
            link_status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            fitment_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded=False,
            vehicle_id=5001,
        )

        response = self.client.get(f"/api/catalog/products/?vehicle_id=5001&fitment=only&category_id={root.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = {row["slug"]: row for row in response.data["results"]}
        self.assertEqual(response.data["count"], 3)
        self.assertIn(matching.slug, rows)
        self.assertIn(no_fitment.slug, rows)
        self.assertIn(suspicious.slug, rows)
        self.assertEqual(rows[matching.slug]["vehicle_filter_policy"], "show_all_with_badges")
        self.assertTrue(rows[matching.slug]["selected_vehicle_compatibility"]["is_compatible"])
        self.assertFalse(rows[no_fitment.slug]["selected_vehicle_compatibility"]["is_compatible"])
        self.assertFalse(rows[suspicious.slug]["selected_vehicle_compatibility"]["is_compatible"])

    def test_auto_chemistry_descendant_vehicle_filter_does_not_require_fitments(self):
        root = Category.objects.create(name="Автохимия и аксессуары", slug="avtohimiia-i-aksessuary", is_active=True)
        child = Category.objects.create(name="Масла", slug="chem-policy-child", parent=root, is_active=True)
        grandchild = Category.objects.create(name="Моторные масла", slug="chem-policy-grandchild", parent=child, is_active=True)
        Product.objects.create(
            sku="CHEM-POLICY-1",
            article="CHEM-POLICY-1",
            name="Chem No Fitment",
            slug="chem-policy-no-fitment",
            brand=self.brand,
            category=grandchild,
            is_active=True,
        )

        response = self.client.get(f"/api/catalog/products/?vehicle_id=999999&fitment=only&category_id={child.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(item["slug"], "chem-policy-no-fitment")
        self.assertEqual(item["vehicle_filter_policy"], "show_all_with_badges")
        self.assertFalse(item["selected_vehicle_compatibility"]["is_compatible"])

    def test_strict_category_with_vehicle_without_fitments_returns_zero(self):
        response = self.client.get(f"/api/catalog/products/?vehicle_id=999999&fitment=only&category_id={self.category.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def _create_autodb_product(
        self,
        *,
        slug: str,
        sku: str,
        category: Category,
        link_status: str,
        fitment_status: str,
        excluded: bool,
        vehicle_id: int,
    ) -> Product:
        product = Product.objects.create(
            sku=sku,
            article=sku,
            name=slug.replace("-", " ").title(),
            slug=slug,
            brand=self.brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number=sku,
            autodb_article_key=f"324:{sku}",
        )
        AutoDbProductLinkQuality.objects.create(
            product=product,
            autodb_article_key=product.autodb_article_key,
            autodb_supplier_id=324,
            autodb_article_number=sku,
            status=link_status,
            reason="",
            evidence={"source": "test"},
        )
        ProductFitment.objects.create(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=vehicle_id,
            linkage_type="PassengerCar",
            autodb_article_key=product.autodb_article_key,
            supplier_id=324,
            article_number=sku,
            quality_status=fitment_status,
            excluded_from_public_filtering=excluded,
            is_stale=False,
            note="Auto-DB Pro applicability",
            is_exact=False,
        )
        return product
