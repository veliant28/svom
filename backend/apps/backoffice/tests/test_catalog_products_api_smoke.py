from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.catalog.models import AutoDbProductLinkQuality
from apps.catalog.services.svom_sku import is_valid_svom_sku
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User
from apps.users.rbac import set_user_system_role


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
        set_user_system_role(user=self.staff_user, role_code="administrator")

        self.brand = Brand.objects.create(name="BOSCH", slug="bosch", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        self.target_category = Category.objects.create(name="Brakes", slug="brakes", is_active=True)
        self.product = Product.objects.create(
            sku="BOS-001",
            article="BOS-001",
            name="CS0100",
            name_uk="",
            name_ru="",
            name_en="",
            name_source_text="",
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
            price_levels=[
                {"key": "Ціна ОПТ2 грн.", "label": "ОПТ2", "value": "100.00", "currency": "UAH", "is_primary": False, "order": 2},
                {"key": "РРЦ грн.", "label": "РРЦ", "value": "120.00", "currency": "UAH", "is_primary": True, "order": 100},
            ],
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
        self.product.name_uk = "Масляний фільтр"
        self.product.name_ru = "Масляный фильтр"
        self.product.name_en = "Oil Filter"
        self.product.save(update_fields=["name_uk", "name_ru", "name_en", "updated_at"])

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    @patch("apps.backoffice.api.serializers.catalog_product_serializer.get_admin_supplier_brand_name_by_id", return_value="BOSCH")
    def test_staff_can_list_create_update_delete_products(self, _supplier_lookup_mock):
        initial_supplier_sku = self.supplier_offer.supplier_sku

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
        self.assertEqual(list_response.data["results"][0]["supplier_price_levels"][0]["label"], "ОПТ2")
        self.assertEqual(list_response.data["results"][0]["supplier_price_levels"][1]["label"], "РРЦ")
        self.assertTrue(list_response.data["results"][0]["supplier_price_levels"][1]["is_primary"])
        self.assertEqual(list_response.data["results"][0]["stock_qty"], 5)
        self.assertEqual(list_response.data["results"][0]["supplier_offer_stock_sum"], 5)
        self.assertIn("price_tooltip_summary", list_response.data["results"][0])
        self.assertEqual(list_response.data["results"][0]["price_tooltip_summary"]["utr_price"], "120.00")
        self.assertIsNone(list_response.data["results"][0]["price_tooltip_summary"]["gpl_rrc_price"])
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
                "autodb_supplier_id": 1,
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
        self.assertTrue(is_valid_svom_sku(create_response.data["svom_sku"]))
        self.assertRegex(str(create_response.data["svom_sku"]), r"^\dS\dV\dO\dM\d{4}$")

        product_id = create_response.data["id"]
        created_product = Product.objects.get(id=product_id)
        created_svom_sku = str(created_product.svom_sku or "")
        self.assertEqual(created_product.sku, "BOS-002")
        self.assertTrue(is_valid_svom_sku(created_svom_sku))

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
        self.assertEqual(update_response.data["sku"], created_svom_sku)
        self.assertEqual(update_response.data["svom_sku"], created_svom_sku)

        created_product.refresh_from_db()
        self.assertEqual(created_product.sku, "BOS-002")
        self.assertEqual(created_product.svom_sku, created_svom_sku)
        self.supplier_offer.refresh_from_db()
        self.assertEqual(self.supplier_offer.supplier_sku, initial_supplier_sku)

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

    def test_utr_warehouse_segments_include_all_known_warehouses_with_zero_values(self):
        utr_product = Product.objects.create(
            sku="UTR-WH-015",
            article="UTR-WH-015",
            name="UTR Warehouse Product",
            slug="utr-warehouse-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=utr_product,
            supplier_sku="UTR-WH-015",
            purchase_price="55.00",
            currency="UAH",
            stock_qty=12,
            is_available=True,
        )
        SupplierRawOffer.objects.create(
            run=self.import_run,
            source=self.import_source,
            supplier=self.supplier,
            row_number=2,
            external_sku="UTR-WH-015",
            article="UTR-WH-015",
            normalized_article="UTRWH015",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="UTR Warehouse Product",
            price="55.00",
            stock_qty=12,
            lead_time_days=0,
            matched_product=utr_product,
            is_valid=True,
            raw_payload={
                "Миколаївська обл.": "",
                "Одеська обл.": "3",
                "КИЇВ-2": "> 10",
            },
        )

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"q": "UTR-WH-015"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        segments = response.data["results"][0]["warehouse_segments"]
        self.assertEqual(len(segments), 15)
        self.assertEqual(segments[0]["key"], "Миколаївська обл.")
        self.assertEqual(segments[0]["value"], "0")
        self.assertEqual(segments[1]["key"], "Одеська обл.")
        self.assertEqual(segments[1]["value"], "3")
        kyiv2 = [item for item in segments if item["key"] == "КИЇВ-2"][0]
        self.assertEqual(kyiv2["value"], "> 10")
        self.assertTrue(all(item["source_code"] == "utr" for item in segments))
        summary = response.data["results"][0]["warehouse_summary"]
        self.assertEqual(summary["warehouse_total_count"], 15)
        self.assertEqual(summary["warehouse_nonzero_count"], 2)
        self.assertEqual(summary["supplier_offer_stock_sum"], 12)

    def test_products_filters_supplier_has_product_price_and_status_fields(self):
        priced_product = Product.objects.create(
            sku="UTR-PRICED-1",
            article="UTR-PRICED-1",
            name="UTR Priced",
            slug="utr-priced-1",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=priced_product,
            supplier_sku="UTR-PRICED-1",
            purchase_price="50.00",
            currency="UAH",
            stock_qty=4,
            is_available=True,
        )
        ProductPrice.objects.create(
            product=priced_product,
            purchase_price="50.00",
            landed_cost="50.00",
            raw_sale_price="60.00",
            final_price="60.00",
        )

        no_price_product = Product.objects.create(
            sku="UTR-NOPRICE-1",
            article="UTR-NOPRICE-1",
            name="UTR NoPrice",
            slug="utr-noprice-1",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=no_price_product,
            supplier_sku="UTR-NOPRICE-1",
            purchase_price="40.00",
            currency="UAH",
            stock_qty=1,
            is_available=True,
        )

        no_offer_product = Product.objects.create(
            sku="UTR-NOOFFER-1",
            article="UTR-NOOFFER-1",
            name="UTR NoOffer",
            slug="utr-nooffer-1",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=no_offer_product,
            supplier_sku="UTR-NOOFFER-1",
            purchase_price="40.00",
            currency="UAH",
            stock_qty=0,
            is_available=False,
        )

        gpl_supplier = Supplier.objects.create(name="GPL Supplier", code="gpl")
        gpl_product = Product.objects.create(
            sku="GPL-ONLY-1",
            article="GPL-ONLY-1",
            name="GPL Product",
            slug="gpl-only-1",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=gpl_supplier,
            product=gpl_product,
            supplier_sku="GPL-ONLY-1",
            purchase_price="70.00",
            currency="UAH",
            stock_qty=2,
            is_available=True,
        )

        AutoDbProductLinkQuality.objects.create(
            product=priced_product,
            autodb_article_key="KEY-UTR-PRICED-1",
            autodb_supplier_id=1,
            autodb_article_number="UTR-PRICED-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        )
        priced_product.autodb_supplier_id = 1
        priced_product.autodb_article_number = "UTR-PRICED-1"
        priced_product.autodb_article_key = "KEY-UTR-PRICED-1"
        priced_product.save(update_fields=["autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"])

        utr_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"supplier": "utr", "page_size": 500},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(utr_response.status_code, status.HTTP_200_OK)
        utr_skus = {row["sku"] for row in utr_response.data["results"]}
        self.assertIn("UTR-PRICED-1", utr_skus)
        self.assertIn("UTR-NOPRICE-1", utr_skus)
        self.assertIn("UTR-NOOFFER-1", utr_skus)
        self.assertNotIn("GPL-ONLY-1", utr_skus)

        no_price_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"supplier": "utr", "has_product_price": "false", "page_size": 500},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(no_price_response.status_code, status.HTTP_200_OK)
        no_price_skus = {row["sku"] for row in no_price_response.data["results"]}
        self.assertIn("UTR-NOPRICE-1", no_price_skus)
        self.assertIn("UTR-NOOFFER-1", no_price_skus)
        self.assertNotIn("UTR-PRICED-1", no_price_skus)

        priced_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"supplier": "utr", "has_product_price": "true", "page_size": 500},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(priced_response.status_code, status.HTTP_200_OK)
        priced_skus = {row["sku"] for row in priced_response.data["results"]}
        self.assertIn("UTR-PRICED-1", priced_skus)
        self.assertNotIn("UTR-NOPRICE-1", priced_skus)

        unavailable_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"supplier": "utr", "has_available_offer": "false", "page_size": 500},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(unavailable_response.status_code, status.HTTP_200_OK)
        unavailable_skus = {row["sku"] for row in unavailable_response.data["results"]}
        self.assertIn("UTR-NOOFFER-1", unavailable_skus)
        self.assertNotIn("UTR-PRICED-1", unavailable_skus)

        status_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"q": "UTR-", "supplier": "utr", "page_size": 500},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        by_sku = {row["sku"]: row for row in status_response.data["results"]}
        self.assertIn("UTR-PRICED-1", by_sku)
        self.assertEqual(by_sku["UTR-PRICED-1"]["product_display_sku"], "UTR-PRICED-1")
        self.assertEqual(by_sku["UTR-PRICED-1"]["productprice_status"], "has_price")
        self.assertEqual(by_sku["UTR-NOPRICE-1"]["productprice_status"], "no_product_price")
        self.assertEqual(by_sku["UTR-NOOFFER-1"]["productprice_status"], "no_available_offer")
        self.assertEqual(by_sku["UTR-PRICED-1"]["supplier_code"], "utr")
        self.assertTrue(by_sku["UTR-PRICED-1"]["has_available_offer"])
        self.assertTrue(by_sku["UTR-PRICED-1"]["has_product_price"])
        self.assertEqual(by_sku["UTR-PRICED-1"]["autodb_link_status"], "trusted")

    def test_selected_offer_source_fields_follow_productprice_selected_offer(self):
        gpl_supplier = Supplier.objects.create(name="GPL Supplier", code="gpl", priority=1)
        utr_supplier = Supplier.objects.create(name="UTR Supplier 2", code="utr2", priority=100)
        mixed_product = Product.objects.create(
            sku="000000000296825",
            svom_sku="1S5V0O4M9273",
            article="75.11",
            name="POLMO Mixed",
            slug="polmo-mixed",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=gpl_supplier,
            product=mixed_product,
            supplier_sku="000000000296825",
            purchase_price="6312.00",
            currency="UAH",
            stock_qty=5,
            is_available=True,
        )
        selected_offer = SupplierOffer.objects.create(
            supplier=utr_supplier,
            product=mixed_product,
            supplier_sku="OSR7511",
            purchase_price="29.01",
            currency="UAH",
            stock_qty=81,
            is_available=True,
        )
        ProductPrice.objects.create(
            product=mixed_product,
            currency="UAH",
            purchase_price="29.01",
            logistics_cost="0.00",
            extra_cost="0.00",
            landed_cost="29.01",
            raw_sale_price="31.91",
            final_price="31.91",
        )
        SupplierRawOffer.objects.create(
            run=self.import_run,
            source=self.import_source,
            supplier=utr_supplier,
            row_number=7,
            external_sku="OSR7511",
            article="7511",
            normalized_article="7511",
            brand_name="POLMO",
            normalized_brand="POLMO",
            product_name="POLMO Mixed",
            price="29.01",
            stock_qty=81,
            lead_time_days=0,
            matched_product=mixed_product,
            is_valid=True,
            raw_payload={"article": "7511", "brand": "POLMO"},
        )

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"q": "POLMO Mixed", "page_size": 50},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]

        self.assertEqual(row["sku"], "1S5V0O4M9273")
        self.assertEqual(row["product_display_sku"], "1S5V0O4M9273")
        self.assertEqual(row["svom_sku"], "1S5V0O4M9273")
        self.assertEqual(row["selected_offer_supplier_code"], "utr2")
        self.assertEqual(row["selected_offer_supplier_sku"], "OSR7511")
        self.assertEqual(row["selected_offer_purchase_price"], "29.01")
        self.assertEqual(row["selected_offer_stock_qty"], 81)
        self.assertEqual(row["selected_offer_raw_article"], "7511")
        self.assertEqual(row["selected_offer_raw_brand"], "POLMO")
        self.assertEqual(row["supplier_sku"], selected_offer.supplier_sku)
        self.assertEqual(row["primary_supplier_code"], "utr2")

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_gpl_product_exposes_display_sku_and_keeps_internal_import_key(self):
        gpl_supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        gpl_source = ImportSource.objects.create(
            code="gpl",
            name="GPL Test Source",
            supplier=gpl_supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        gpl_run = ImportRun.objects.create(
            source=gpl_source,
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
        gpl_product = Product.objects.create(
            sku="GPL-000000004363234",
            article="V208",
            name="K2 COSMO",
            slug="k2-cosmo",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=gpl_supplier,
            product=gpl_product,
            supplier_sku="000000004363234",
            purchase_price="100.00",
            currency="UAH",
            stock_qty=1,
            is_available=True,
        )
        SupplierRawOffer.objects.create(
            run=gpl_run,
            source=gpl_source,
            supplier=gpl_supplier,
            row_number=2,
            external_sku="000000004363234",
            article="K20849",
            normalized_article="K20849",
            brand_name="K2",
            normalized_brand="K2",
            product_name="K2 COSMO",
            price="100.00",
            stock_qty=1,
            lead_time_days=0,
            matched_product=gpl_product,
            is_valid=True,
            raw_payload={"Код": "000000004363234", "Артикул": "K20849", "Артикул ТД": "V208"},
        )

        list_response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"q": "000000004363234"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        row = list_response.data["results"][0]
        self.assertEqual(row["sku"], "000000004363234")
        self.assertEqual(row["product_display_sku"], "000000004363234")
        self.assertEqual(row["internal_import_key"], "GPL-000000004363234")

        detail_response = self.client.get(
            reverse("backoffice_api:catalog-product-update", kwargs={"id": gpl_product.id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["sku"], "000000004363234")
        self.assertEqual(detail_response.data["product_display_sku"], "000000004363234")
        self.assertEqual(detail_response.data["internal_import_key"], "GPL-000000004363234")

    def test_gpl_price_type_fields_are_exposed_as_wholesale_price_levels(self):
        gpl_supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        gpl_source = ImportSource.objects.create(
            code="gpl",
            name="GPL Test Source",
            supplier=gpl_supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        gpl_run = ImportRun.objects.create(
            source=gpl_source,
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
        gpl_product = Product.objects.create(
            sku="GPL-000000000099999",
            article="TEST-OPT",
            name="K2 Test",
            slug="k2-test-opt",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=gpl_supplier,
            product=gpl_product,
            supplier_sku="000000000099999",
            purchase_price="100.00",
            currency="UAH",
            price_levels=[{"key": "price_type_10", "label": "РРЦ", "value": "199.99", "currency": "UAH", "is_primary": True, "order": 100}],
            stock_qty=1,
            is_available=True,
        )
        SupplierRawOffer.objects.create(
            run=gpl_run,
            source=gpl_source,
            supplier=gpl_supplier,
            row_number=1,
            external_sku="000000000099999",
            article="TEST-OPT",
            normalized_article="TESTOPT",
            brand_name="K2",
            normalized_brand="K2",
            product_name="K2 Test",
            price="199.99",
            stock_qty=1,
            lead_time_days=0,
            matched_product=gpl_product,
            is_valid=True,
            raw_payload={
                "price_type_1": "140.24",
                "price_type_2": "130.24",
                "price_type_9": "120.24",
                "price_type_10": "199.99",
                "count_warehouse_1": "3",
            },
        )

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"q": "000000000099999"},
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        labels = [row["label"] for row in response.data["results"][0]["supplier_price_levels"]]
        self.assertEqual(labels, ["ОПТ2", "ОПТ4", "ОПТ10", "РРЦ"])

    def test_backoffice_product_list_uses_localized_display_name(self):
        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"locale": "ru"},
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertEqual(item["name"], "Масляный фильтр")
        self.assertEqual(item["display_name"], "Масляный фильтр")
        self.assertEqual(item["display_name_source"], "name_ru")
        self.assertEqual(item["name_uk"], "Масляний фільтр")
        self.assertEqual(item["name_ru"], "Масляный фильтр")
        self.assertEqual(item["name_en"], "Oil Filter")
        self.assertIn("name_source", item)
        self.assertEqual(item["raw_supplier_name"], "Bosch Oil Filter")
        self.assertNotEqual(item["name"], item["raw_supplier_name"])

    def test_backoffice_product_list_uses_selected_language(self):
        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"locale": "en"},
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertEqual(item["display_name"], "Oil Filter")
        self.assertEqual(item["display_name_source"], "name_en")

    def test_backoffice_product_list_avoids_code_like_title(self):
        self.product.name = "CS0100"
        self.product.name_uk = "CS0100"
        self.product.name_ru = "CS0100"
        self.product.name_en = "CS0100"
        self.product.name_source_text = ""
        self.product.save(
            update_fields=[
                "name",
                "name_uk",
                "name_ru",
                "name_en",
                "name_source_text",
                "updated_at",
            ]
        )

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"locale": "uk"},
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertEqual(item["display_name"], "Товар без названия BOSCH BOS-001")
        self.assertEqual(item["display_name_source"], "fallback")

    def test_backoffice_product_list_respects_manual_locked_name(self):
        self.product.name_manually_locked = True
        self.product.name_uk = "Ручна назва товару"
        self.product.name_ru = "Ручное название товара"
        self.product.name_en = "Manual product title"
        self.product.save(update_fields=["name_manually_locked", "name_uk", "name_ru", "name_en", "updated_at"])

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"locale": "uk"},
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertTrue(item["name_manually_locked"])
        self.assertEqual(item["display_name"], "Ручна назва товару")
        self.assertEqual(item["name"], "Ручна назва товару")

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

    def test_products_list_keeps_products_with_null_category_visible(self):
        self.product.category = None
        self.product.save(update_fields=["category", "updated_at"])

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            {"page": 1, "page_size": 25},
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIsNone(response.data["results"][0]["category"])

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

    def test_backoffice_stock_qty_prefers_cached_value_when_present(self):
        self.product.available_stock_qty_cached = 9
        self.product.save(update_fields=["available_stock_qty_cached", "updated_at"])

        response = self.client.get(
            reverse("backoffice_api:catalog-product-list-create"),
            **self._auth(self.staff_token.key),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertEqual(item["stock_qty"], 9)
        self.assertEqual(item["supplier_offer_stock_sum"], 5)
