from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.backoffice.api.serializers import BackofficeCatalogProductSerializer
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class BackofficeCatalogProductSerializerDisplayNameTests(TestCase):
    def setUp(self):
        self.request_factory = APIRequestFactory()
        self.brand = Brand.objects.create(name="BOSCH", slug="bosch", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)
        self.product = Product.objects.create(
            sku="BOS-001",
            article="BOS-001",
            name="CS0100",
            name_uk="Масляний фільтр",
            name_ru="Масляный фильтр",
            name_en="Oil Filter",
            slug="bosch-oil-filter",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        supplier = Supplier.objects.create(name="UTR Supplier", code="utr")
        source = ImportSource.objects.create(
            code="utr",
            name="UTR Test",
            supplier=supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        run = ImportRun.objects.create(source=source, status=ImportRun.STATUS_SUCCESS, trigger="test", dry_run=False)
        SupplierRawOffer.objects.create(
            run=run,
            source=source,
            supplier=supplier,
            row_number=1,
            external_sku="BOS-001",
            article="BOS-001",
            normalized_article="BOS001",
            brand_name="BOSCH",
            normalized_brand="BOSCH",
            product_name="Bosch Oil Filter Raw",
            price="120.00",
            stock_qty=1,
            lead_time_days=0,
            matched_product=self.product,
            is_valid=True,
            raw_payload={},
        )

    def _serialize(self, *, locale: str) -> dict:
        request = self.request_factory.get("/api/backoffice/products/", {"locale": locale})
        serializer = BackofficeCatalogProductSerializer(
            instance=self.product,
            context={"request": request},
        )
        return serializer.data

    def test_serializer_uses_localized_display_name_by_locale(self):
        payload = self._serialize(locale="ru")
        self.assertEqual(payload["display_name"], "Масляный фильтр")
        self.assertEqual(payload["display_name_source"], "name_ru")
        self.assertEqual(payload["name"], "Масляный фильтр")

    def test_serializer_exposes_i18n_source_fields(self):
        payload = self._serialize(locale="uk")
        self.assertEqual(payload["name_uk"], "Масляний фільтр")
        self.assertEqual(payload["name_ru"], "Масляный фильтр")
        self.assertEqual(payload["name_en"], "Oil Filter")
        self.assertIn("catalog_source", payload)
        self.assertIn("autodb_article_key", payload)

    def test_raw_supplier_name_is_not_main_title(self):
        payload = self._serialize(locale="uk")
        self.assertEqual(payload["raw_supplier_name"], "Bosch Oil Filter Raw")
        self.assertNotEqual(payload["name"], payload["raw_supplier_name"])

    def test_code_like_name_uses_admin_fallback_label(self):
        self.product.name = "CS0100"
        self.product.name_uk = "CS0100"
        self.product.name_ru = "CS0100"
        self.product.name_en = "CS0100"
        self.product.save(update_fields=["name", "name_uk", "name_ru", "name_en", "updated_at"])

        payload = self._serialize(locale="uk")
        self.assertEqual(payload["display_name"], "Товар без названия BOSCH BOS-001")
        self.assertEqual(payload["display_name_source"], "fallback")

    def test_manual_locked_name_is_respected(self):
        self.product.name_manually_locked = True
        self.product.name_uk = "Ручна назва товару"
        self.product.save(update_fields=["name_manually_locked", "name_uk", "updated_at"])

        payload = self._serialize(locale="uk")
        self.assertTrue(payload["name_manually_locked"])
        self.assertEqual(payload["display_name"], "Ручна назва товару")

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_serializer_does_not_call_utr(self, utr_client_cls):
        _ = self._serialize(locale="uk")
        utr_client_cls.assert_not_called()
