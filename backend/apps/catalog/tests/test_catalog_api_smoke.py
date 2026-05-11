from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class CatalogAPISmokeTests(APITestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand A", slug="brand-a", is_active=True)
        self.category = Category.objects.create(
            name="Category A",
            slug="category-a",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
        )
        self.product = Product.objects.create(
            sku="SKU-001",
            article="ART-001",
            name="Test Product",
            name_uk="0005 Свічка запалювання ART-001",
            name_ru="Свеча зажигания",
            name_en="Spark Plug",
            slug="test-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="199.99", currency="UAH")

    def test_products_endpoint_returns_data(self):
        response = self.client.get(reverse("catalog_api:product-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "test-product")
        self.assertEqual(response.data["results"][0]["name"], "Свічка запалювання")

    def test_products_endpoint_out_of_range_page_falls_back_to_first_page(self):
        response = self.client.get(reverse("catalog_api:product-list"), {"page": 999, "page_size": 52})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "test-product")

    def test_product_detail_works_by_slug_and_article_fallback(self):
        by_slug = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "test-product"}), {"locale": "ru"})
        by_article = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "ART-001"}), {"locale": "en"})

        self.assertEqual(by_slug.status_code, status.HTTP_200_OK)
        self.assertEqual(by_article.status_code, status.HTTP_200_OK)
        self.assertEqual(by_slug.data["id"], str(self.product.id))
        self.assertEqual(by_article.data["id"], str(self.product.id))
        self.assertEqual(by_slug.data["name"], "Свеча зажигания")
        self.assertEqual(by_article.data["name"], "Spark Plug")

    def test_products_endpoint_orders_by_available_stock_desc_by_default(self):
        supplier = Supplier.objects.create(name="Supplier A", code="supplier-a", is_active=True)
        low_stock_product = Product.objects.create(
            sku="SKU-LOW",
            article="ART-LOW",
            name="AAA Low Stock",
            slug="aaa-low-stock",
            brand=self.brand,
            category=self.category,
            is_active=True,
            available_stock_qty_cached=2,
        )
        high_stock_product = Product.objects.create(
            sku="SKU-HIGH",
            article="ART-HIGH",
            name="ZZZ High Stock",
            slug="zzz-high-stock",
            brand=self.brand,
            category=self.category,
            is_active=True,
            available_stock_qty_cached=25,
        )
        ProductPrice.objects.create(product=low_stock_product, final_price="199.99", currency="UAH")
        ProductPrice.objects.create(product=high_stock_product, final_price="199.99", currency="UAH")
        SupplierOffer.objects.create(
            supplier=supplier,
            product=low_stock_product,
            supplier_sku="LOW-1",
            purchase_price="100.00",
            stock_qty=2,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=supplier,
            product=high_stock_product,
            supplier_sku="HIGH-1",
            purchase_price="100.00",
            stock_qty=25,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="BASE-UNAVAILABLE",
            purchase_price="100.00",
            stock_qty=1000,
            is_available=False,
        )

        response = self.client.get(reverse("catalog_api:product-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["slug"] for item in response.data["results"]],
            ["zzz-high-stock", "aaa-low-stock", "test-product"],
        )

    def test_popular_query_uses_stock_and_price_fallback_when_featured_empty(self):
        self.product.is_featured = False
        self.product.available_stock_qty_cached = 12
        self.product.save(update_fields=["is_featured", "available_stock_qty_cached", "updated_at"])
        supplier = Supplier.objects.create(name="Supplier Popular", code="supplier-popular", is_active=True)
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="POP-BASE",
            purchase_price="100.00",
            stock_qty=3,
            is_available=True,
        )
        Product.objects.create(
            sku="SKU-POPULAR-2",
            article="ART-POPULAR-2",
            name="Свічка запалювання 2",
            name_uk="Свічка запалювання 2",
            slug="spark-plug-2",
            brand=self.brand,
            category=self.category,
            is_active=True,
            is_featured=False,
            available_stock_qty_cached=5,
        )
        second = Product.objects.get(slug="spark-plug-2")
        ProductPrice.objects.create(product=second, final_price="123.45", currency="UAH")
        SupplierOffer.objects.create(
            supplier=supplier,
            product=second,
            supplier_sku="POP-2",
            purchase_price="70.00",
            stock_qty=5,
            is_available=True,
        )

        response = self.client.get(reverse("catalog_api:product-list"), {"popular": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data["count"], 0)

    def test_public_stock_uses_supplier_offer_sum_when_cached_stock_is_zero(self):
        supplier = Supplier.objects.create(name="Supplier Stock", code="supplier-stock", is_active=True)
        self.product.available_stock_qty_cached = 0
        self.product.save(update_fields=["available_stock_qty_cached", "updated_at"])
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="STOCK-BASE",
            purchase_price="100.00",
            stock_qty=7,
            is_available=True,
        )

        list_response = self.client.get(reverse("catalog_api:product-list"))
        detail_response = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "test-product"}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["results"][0]["total_stock_qty"], 7)
        self.assertEqual(detail_response.data["total_stock_qty"], 7)

    def test_categories_scope_header_uses_navigation_visibility(self):
        Category.objects.create(
            name="Амортизатор",
            slug="autodb-shock",
            source=Category.SOURCE_AUTODB_PRO,
            show_in_header=False,
            is_active=True,
        )
        response = self.client.get(reverse("catalog_api:category-list"), {"scope": "header"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data]
        self.assertIn("Category A", names)
        self.assertNotIn("Амортизатор", names)

    def test_products_endpoint_uses_remote_url_when_local_image_file_missing(self):
        ProductImage.objects.create(
            product=self.product,
            image=None,
            remote_url="https://cdn.example.test/test-product.webp",
            is_primary=True,
            source=ProductImage.SOURCE_GPL_PRICE,
        )

        response = self.client.get(reverse("catalog_api:product-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["primary_image"], "https://cdn.example.test/test-product.webp")

    def test_gpl_product_exposes_display_sku_without_internal_prefix(self):
        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        gpl_product = Product.objects.create(
            sku="GPL-000000004363234",
            article="V208",
            name="K2 COSMO",
            slug="k2-cosmo",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=gpl_product, final_price="100.00", currency="UAH")
        SupplierOffer.objects.create(
            supplier=supplier,
            product=gpl_product,
            supplier_sku="000000004363234",
            purchase_price="75.00",
            stock_qty=3,
            is_available=True,
        )

        list_response = self.client.get(reverse("catalog_api:product-list"), {"q": "k2"})
        detail_response = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "k2-cosmo"}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["results"][0]["sku"], "000000004363234")
        self.assertEqual(detail_response.data["sku"], "000000004363234")

    def test_multi_supplier_product_uses_canonical_identity_and_selected_offer_source(self):
        gpl_supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True, priority=1)
        utr_supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True, priority=100)
        utr_source = ImportSource.objects.create(
            code="utr-smoke",
            name="UTR Smoke",
            supplier=utr_supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
        )
        utr_run = ImportRun.objects.create(
            source=utr_source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            dry_run=False,
        )
        mixed_product = Product.objects.create(
            sku="000000000296825",
            svom_sku="1S5V0O4M9273",
            article="75.11",
            name="Глушник POLMO Volvo FH12 алюмінізована сталь (75.11)",
            slug="polmo-75-11",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=mixed_product, purchase_price="29.01", final_price="31.91", currency="UAH")
        SupplierOffer.objects.create(
            supplier=gpl_supplier,
            product=mixed_product,
            supplier_sku="000000000296825",
            purchase_price="6312.00",
            stock_qty=5,
            is_available=False,
        )
        SupplierOffer.objects.create(
            supplier=utr_supplier,
            product=mixed_product,
            supplier_sku="OSR7511",
            purchase_price="29.01",
            stock_qty=81,
            is_available=True,
        )
        SupplierRawOffer.objects.create(
            run=utr_run,
            source=utr_source,
            supplier=utr_supplier,
            external_sku="OSR7511",
            article="7511",
            normalized_article="7511",
            brand_name="POLMO",
            normalized_brand="POLMO",
            product_name="Глушник POLMO Volvo FH12 алюмінізована сталь (75.11)",
            currency="UAH",
            price="29.01",
            stock_qty=81,
            matched_product=mixed_product,
            is_valid=True,
            raw_payload={"article": "7511", "brand": "POLMO"},
        )

        list_response = self.client.get(reverse("catalog_api:product-list"), {"q": "POLMO"})
        detail_response = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "polmo-75-11"}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        row = next(item for item in list_response.data["results"] if item["slug"] == "polmo-75-11")
        self.assertEqual(row["sku"], "1S5V0O4M9273")
        self.assertEqual(detail_response.data["sku"], "1S5V0O4M9273")
        self.assertEqual(row["selected_offer_supplier_code"], "utr")
        self.assertEqual(row["selected_offer_supplier_sku"], "OSR7511")
        self.assertEqual(detail_response.data["selected_offer_supplier_code"], "utr")
        self.assertEqual(detail_response.data["selected_offer_supplier_sku"], "OSR7511")
