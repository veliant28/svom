from __future__ import annotations

from django.test import TestCase

from apps.catalog.models import Brand, Product
from apps.catalog.services.product_sku import (
    get_product_display_sku,
    get_product_internal_import_key,
    get_product_manufacturer_article,
    is_multi_offer_product,
)
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class ProductSkuDisplayTests(TestCase):
    def setUp(self) -> None:
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.gpl_supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.gpl_source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.gpl_supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="/tmp/gpl.xlsx",
            is_active=True,
        )
        self.gpl_run = ImportRun.objects.create(
            source=self.gpl_source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            dry_run=False,
        )

    def test_gpl_display_sku_uses_raw_payload_code(self):
        product = Product.objects.create(
            sku="GPL-000000004363234",
            article="V208",
            name="K2 Product",
            slug="k2-product",
            brand=self.brand,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl_supplier,
            product=product,
            supplier_sku="000000004363234",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )
        SupplierRawOffer.objects.create(
            run=self.gpl_run,
            source=self.gpl_source,
            supplier=self.gpl_supplier,
            external_sku="000000004363234",
            article="K20849",
            normalized_article="K20849",
            brand_name="K2",
            normalized_brand="K2",
            product_name="K2 Product",
            currency="UAH",
            price="10.00",
            stock_qty=1,
            matched_product=product,
            raw_payload={"Код": "000000004363234", "Артикул": "K20849", "Артикул ТД": "V208"},
            is_valid=True,
        )

        self.assertEqual(get_product_display_sku(product), "000000004363234")
        self.assertEqual(get_product_internal_import_key(product), "GPL-000000004363234")

    def test_gpl_display_sku_falls_back_to_supplier_offer_sku(self):
        product = Product.objects.create(
            sku="GPL-001",
            article="ART-001",
            name="Fallback Product",
            slug="fallback-product",
            brand=self.brand,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl_supplier,
            product=product,
            supplier_sku="00112233",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )

        self.assertEqual(get_product_display_sku(product), "00112233")

    def test_non_gpl_product_keeps_model_sku(self):
        supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        product = Product.objects.create(
            sku="UTR-0001",
            article="UTR-0001",
            name="UTR Product",
            slug="utr-product",
            brand=self.brand,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=supplier,
            product=product,
            supplier_sku="UTR-SUP-0001",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )

        self.assertEqual(get_product_display_sku(product), "UTR-0001")

    def test_gpl_only_product_prefers_svom_sku_when_present(self):
        product = Product.objects.create(
            sku="GPL-00042",
            article="A42",
            name="GPL Product",
            slug="gpl-product",
            brand=self.brand,
            svom_sku="4S0V9O5M0534",
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl_supplier,
            product=product,
            supplier_sku="00042",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )

        self.assertEqual(get_product_display_sku(product), "4S0V9O5M0534")

    def test_utr_only_product_prefers_svom_sku_when_present(self):
        supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        product = Product.objects.create(
            sku="UTR-1001",
            article="UTR-1001",
            name="UTR Product",
            slug="utr-product-svom",
            brand=self.brand,
            svom_sku="7S2V8O1M0346",
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=supplier,
            product=product,
            supplier_sku="UTR-SUP-1001",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )

        self.assertEqual(get_product_display_sku(product), "7S2V8O1M0346")

    def test_multi_supplier_product_prefers_svom_sku_for_display(self):
        utr_supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        product = Product.objects.create(
            sku="000000000296825",
            svom_sku="1S5V0O4M9273",
            article="75.11",
            name="POLMO Product",
            slug="polmo-product",
            brand=self.brand,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.gpl_supplier,
            product=product,
            supplier_sku="000000000296825",
            purchase_price="6312.00",
            stock_qty=5,
            is_available=True,
        )
        SupplierOffer.objects.create(
            supplier=utr_supplier,
            product=product,
            supplier_sku="OSR7511",
            purchase_price="29.01",
            stock_qty=81,
            is_available=True,
        )
        SupplierRawOffer.objects.create(
            run=self.gpl_run,
            source=self.gpl_source,
            supplier=self.gpl_supplier,
            external_sku="000000000296825",
            article="858715",
            normalized_article="858715",
            brand_name="POLMO",
            normalized_brand="POLMO",
            product_name="POLMO Product",
            currency="UAH",
            price="6312.00",
            stock_qty=5,
            matched_product=product,
            raw_payload={"Код": "000000000296825", "Артикул": "858715", "Артикул ТД": "75.11"},
            is_valid=True,
        )

        self.assertTrue(is_multi_offer_product(product))
        self.assertEqual(get_product_display_sku(product), "1S5V0O4M9273")
        self.assertEqual(get_product_manufacturer_article(product), "75.11")

    def test_gpl_manufacturer_article_prefers_td_article_and_skips_duplicate_with_sku(self):
        product = Product.objects.create(
            sku="GPL-000000000024868",
            article="1462",
            name="BRISK Product",
            slug="brisk-product",
            brand=self.brand,
            is_active=True,
            autodb_supplier_id=494,
            autodb_article_number="1462",
            autodb_article_key="494:1462",
        )
        SupplierOffer.objects.create(
            supplier=self.gpl_supplier,
            product=product,
            supplier_sku="000000000024868",
            purchase_price="10.00",
            stock_qty=1,
            is_available=True,
        )
        SupplierRawOffer.objects.create(
            run=self.gpl_run,
            source=self.gpl_source,
            supplier=self.gpl_supplier,
            external_sku="000000000024868",
            article="A14",
            normalized_article="A14",
            brand_name="BRISK",
            normalized_brand="BRISK",
            product_name="BRISK Product",
            currency="UAH",
            price="10.00",
            stock_qty=1,
            matched_product=product,
            raw_payload={"Код": "000000000024868", "Артикул": "A14", "Артикул ТД": "1462"},
            is_valid=True,
        )

        self.assertEqual(get_product_display_sku(product), "000000000024868")
        self.assertEqual(get_product_manufacturer_article(product), "1462")
