from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User


class SupplierPublishMappedProductsAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="supplier-publish-ops@test.local",
            first_name="supplier-publish-ops",
            password="demo12345",
            is_staff=True,
        )
        self.staff_token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.staff_token.key}"}

        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
        )
        self.run_old = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test-old")
        self.run_new = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test-new")

        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        self.brand = Brand.objects.create(name="BOSCH", slug="bosch", is_active=True)
        self.existing_product = Product.objects.create(
            sku="EX-001",
            article="EX-001",
            name="Existing Product",
            slug="existing-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        old_offer = SupplierRawOffer.objects.create(
            run=self.run_old,
            source=self.source,
            supplier=self.supplier,
            external_sku="A-001",
            article="A-001",
            normalized_article="A001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="Old name",
            currency="UAH",
            price=Decimal("90.00"),
            stock_qty=2,
            mapped_category=self.category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
        )
        old_offer.updated_at = timezone.now() - timedelta(days=2)
        old_offer.save(update_fields=("updated_at",))

        latest_offer = SupplierRawOffer.objects.create(
            run=self.run_new,
            source=self.source,
            supplier=self.supplier,
            external_sku="A-001",
            article="A-001",
            normalized_article="A001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="Oil filter",
            currency="UAH",
            price=Decimal("110.00"),
            stock_qty=3,
            mapped_category=self.category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
            raw_payload={"Зображення товару": "https://example.com/gpl/a001.webp"},
        )
        latest_offer.updated_at = timezone.now() - timedelta(hours=1)
        latest_offer.save(update_fields=("updated_at",))

        SupplierRawOffer.objects.create(
            run=self.run_new,
            source=self.source,
            supplier=self.supplier,
            external_sku="B-001",
            article="B-001",
            normalized_article="B001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="Existing linked",
            currency="UAH",
            price=Decimal("125.00"),
            stock_qty=1,
            matched_product=self.existing_product,
            mapped_category=self.category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
            raw_payload={"Зображення товару": "https://example.com/gpl/b001.webp"},
        )

        SupplierRawOffer.objects.create(
            run=self.run_new,
            source=self.source,
            supplier=self.supplier,
            external_sku="C-001",
            article="C-001",
            normalized_article="C001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="Needs review",
            currency="UAH",
            price=Decimal("90.00"),
            stock_qty=1,
            mapped_category=self.category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW,
        )

        SupplierRawOffer.objects.create(
            run=self.run_new,
            source=self.source,
            supplier=self.supplier,
            external_sku="D-001",
            article="D-001",
            normalized_article="D001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="No category",
            currency="UAH",
            price=Decimal("99.00"),
            stock_qty=2,
            mapped_category=None,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED,
        )

        SupplierRawOffer.objects.create(
            run=self.run_new,
            source=self.source,
            supplier=self.supplier,
            external_sku="E-001",
            article="E-001",
            normalized_article="E001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="No price",
            currency="UAH",
            price=None,
            stock_qty=2,
            mapped_category=self.category,
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
        )

    def test_publish_mapped_products_is_idempotent_and_skips_non_publishable(self):
        with patch(
            "apps.supplier_imports.services.mapped_offer_publish.images._download_image",
            return_value=(b"fake-image-bytes", "image/webp"),
        ):
            response = self.client.post(
                reverse("backoffice_api:supplier-publish-mapped-products", kwargs={"code": "gpl"}),
                {"reprice_after_publish": False},
                format="json",
                **self.auth,
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result = response.data["result"]
        self.assertEqual(result["supplier_code"], "gpl")
        self.assertEqual(result["eligible_rows"], 2)
        self.assertEqual(result["created_rows"], 2)
        self.assertEqual(result["updated_rows"], 0)
        self.assertEqual(result["offers_created"], 2)
        self.assertEqual(result["products_created"], 1)
        self.assertGreaterEqual(result["skipped_rows"], 3)

        self.assertEqual(Product.objects.filter(sku="A-001").count(), 1)
        self.assertEqual(Product.objects.filter(sku="B-001").count(), 1)
        self.assertEqual(SupplierOffer.objects.filter(supplier=self.supplier).count(), 2)
        self.assertEqual(ProductImage.objects.filter(product__sku="A-001").count(), 1)
        self.assertEqual(ProductImage.objects.filter(product__sku="B-001").count(), 1)

        with patch(
            "apps.supplier_imports.services.mapped_offer_publish.images._download_image",
            return_value=(b"fake-image-bytes", "image/webp"),
        ):
            second_response = self.client.post(
                reverse("backoffice_api:supplier-publish-mapped-products", kwargs={"code": "gpl"}),
                {"reprice_after_publish": False},
                format="json",
                **self.auth,
            )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        second_result = second_response.data["result"]
        self.assertEqual(second_result["eligible_rows"], 2)
        self.assertEqual(second_result["created_rows"], 0)
        self.assertEqual(second_result["updated_rows"], 2)
        self.assertEqual(second_result["offers_created"], 0)
        self.assertEqual(second_result["offers_updated"], 0)

        self.assertEqual(Product.objects.filter(sku="A-001").count(), 1)
        self.assertEqual(Product.objects.filter(sku="B-001").count(), 1)
        self.assertEqual(SupplierOffer.objects.filter(supplier=self.supplier).count(), 2)
