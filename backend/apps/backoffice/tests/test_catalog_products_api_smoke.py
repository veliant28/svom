from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User


class BackofficeCatalogProductsAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="products-ops@test.local",
            first_name="products-ops",
            password="demo12345",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="products-customer@test.local",
            first_name="products-customer",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

        self.brand = Brand.objects.create(name="BOSCH", slug="bosch", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        self.target_category = Category.objects.create(name="Brakes", slug="brakes", is_active=True)
        self.product = Product.objects.create(
            sku="BOS-001",
            article="BOS-001",
            name="Bosch Oil Filter",
            slug="bosch-oil-filter",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.supplier = Supplier.objects.create(name="UTR Supplier", code="utr")
        self.import_source = ImportSource.objects.create(
            code="utr",
            name="UTR Test",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.import_run = ImportRun.objects.create(
            source=self.import_source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            dry_run=False,
            processed_rows=1,
            parsed_rows=1,
            offers_created=1,
            offers_updated=0,
            offers_skipped=0,
            errors_count=0,
            repriced_products=0,
            reindexed_products=0,
        )
        self.supplier_offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="UTR-BOS-001",
            purchase_price="120.00",
            currency="UAH",
            stock_qty=5,
            is_available=True,
        )
        self.raw_offer = SupplierRawOffer.objects.create(
            run=self.import_run,
            source=self.import_source,
            supplier=self.supplier,
            row_number=1,
            external_sku="UTR-BOS-001",
            article="BOS-001",
            normalized_article="BOS001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="Bosch Oil Filter",
            price="120.00",
            stock_qty=5,
            lead_time_days=0,
            matched_product=self.product,
            is_valid=True,
            raw_payload={
                "count_warehouse_1": "5",
                "count_warehouse_2": "0",
            },
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_staff_can_list_create_update_delete_products(self):
        list_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertIsNone(list_response.data["results"][0]["final_price"])
        self.assertIsNone(list_response.data["results"][0]["currency"])
        self.assertIsNone(list_response.data["results"][0]["price_updated_at"])
        self.assertEqual(list_response.data["results"][0]["supplier_price"], "120.00")
        self.assertEqual(list_response.data["results"][0]["supplier_currency"], "UAH")
        self.assertIsNone(list_response.data["results"][0]["applied_markup_percent"])
        self.assertEqual(list_response.data["results"][0]["applied_markup_policy_name"], "")
        self.assertEqual(
            list_response.data["results"][0]["warehouse_segments"],
            [
                {
                    "key": "count_warehouse_1",
                    "value": "5",
                    "source_code": "utr",
                },
                {
                    "key": "count_warehouse_2",
                    "value": "0",
                    "source_code": "utr",
                },
            ],
        )

        create_response = self.client.post(
            reverse("backoffice_api:catalog-product-list-create"),
            {
                "sku": "BOS-002",
                "article": "BOS-002",
                "name": "Bosch Air Filter",
                "slug": "",
                "brand": str(self.brand.id),
                "category": str(self.category.id),
                "is_active": True,
                "is_featured": True,
                "is_new": False,
                "is_bestseller": False,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(bool(create_response.data["slug"]))

        product_id = create_response.data["id"]
        update_response = self.client.patch(
            reverse("backoffice_api:catalog-product-update", kwargs={"id": product_id}),
            {
                "is_active": False,
                "is_bestseller": True,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertFalse(update_response.data["is_active"])
        self.assertTrue(update_response.data["is_bestseller"])

        filter_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"q": "air", "is_active": "false"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(filter_response.status_code, status.HTTP_200_OK)
        self.assertEqual(filter_response.data["count"], 1)

        delete_response = self.client.delete(
            reverse("backoffice_api:catalog-product-update", kwargs={"id": product_id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=product_id).exists())

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_price_is_preferred_over_supplier_offer_in_list(self):
        ProductPrice.objects.create(
            product=self.product,
            final_price="180.00",
            currency="UAH",
        )

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["final_price"], "180.00")
        self.assertEqual(response.data["results"][0]["supplier_price"], "120.00")

    def test_products_list_supports_page_size_query_param(self):
        for index in range(30):
            Product.objects.create(
                sku=f"BOS-PG-{index:03d}",
                article=f"BOS-PG-{index:03d}",
                name=f"Bosch Test Product {index:03d}",
                slug=f"bosch-test-product-{index:03d}",
                brand=self.brand,
                category=self.category,
                is_active=True,
            )

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"page_size": 15},
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 31)
        self.assertEqual(len(response.data["results"]), 15)

    @patch("apps.backoffice.api.views.pricing_actions_views.reindex_products_task")
    def test_staff_can_dispatch_product_reindex_action(self, reindex_task):
        reindex_task.delay.return_value = None

        reindex_response = self.client.post(
            reverse("backoffice_api:action-reindex-products"),
            {
                "product_ids": [str(self.product.id)],
                "dispatch_async": True,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(reindex_response.status_code, status.HTTP_200_OK)
        reindex_task.delay.assert_called_once()

    def test_staff_can_bulk_move_products_category_and_update_import_rules(self):
        response = self.client.post(
            reverse("backoffice_api:action-bulk-move-products-category"),
            {
                "product_ids": [str(self.product.id)],
                "category_id": str(self.target_category.id),
                "update_import_rules": True,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["products_requested"], 1)
        self.assertEqual(response.data["products_found"], 1)
        self.assertEqual(response.data["products_updated"], 1)
        self.assertEqual(response.data["raw_offers_total"], 1)
        self.assertEqual(response.data["raw_offers_updated"], 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.category_id, self.target_category.id)

        self.raw_offer.refresh_from_db()
        self.assertEqual(self.raw_offer.mapped_category_id, self.target_category.id)
        self.assertEqual(
            self.raw_offer.category_mapping_status,
            SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
        )
        self.assertEqual(
            self.raw_offer.category_mapping_reason,
            SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL,
        )
        self.assertEqual(self.raw_offer.category_mapped_by_id, self.staff_user.id)
