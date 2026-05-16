from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.autodb.services.product_attribute_enrichment import AutoDbProductAttributeEnrichmentService
from apps.catalog.models import Attribute, AttributeValue, Brand, Category, Product, ProductAttribute


class AutoDbProductAttributeEnrichmentServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand", is_active=True)
        self.category = Category.objects.create(name="Legacy", slug="legacy", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-ATTR-1",
            slug="product-attr-1",
            name="Product Attr",
            brand=self.brand,
            category=self.category,
            article="A1",
            autodb_supplier_id=300,
            autodb_article_number="820099",
            autodb_article_key="300:820099",
            available_stock_qty_cached=5,
            is_active=True,
        )

    def _service(self) -> AutoDbProductAttributeEnrichmentService:
        return AutoDbProductAttributeEnrichmentService()

    def test_attributes_created_from_article_attributes(self):
        service = self._service()
        rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 1701,
                "displaytitle": "Диаметр",
                "displayvalue": "25 мм",
            },
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 1702,
                "displaytitle": "Длина",
                "displayvalue": "100 мм",
            },
        ]
        with patch.object(service, "_find_article_attribute_rows", return_value=rows):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.status, "updated")
        self.assertEqual(ProductAttribute.objects.filter(product=self.product).count(), 2)
        self.assertEqual(Attribute.objects.count(), 2)
        self.assertEqual(AttributeValue.objects.count(), 2)

    def test_displaytitle_or_description_becomes_attribute_name(self):
        service = self._service()
        rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 1801,
                "description": "Материал",
                "displayvalue": "Сталь",
            }
        ]
        with patch.object(service, "_find_article_attribute_rows", return_value=rows):
            service.enrich_product(product=self.product, dry_run=False)

        attr = Attribute.objects.get()
        self.assertEqual(attr.name, "Материал")

    def test_displayvalue_becomes_value(self):
        service = self._service()
        rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 1802,
                "displaytitle": "Резьба",
                "displayvalue": "M12x1.5",
            }
        ]
        with patch.object(service, "_find_article_attribute_rows", return_value=rows):
            service.enrich_product(product=self.product, dry_run=False)

        p_attr = ProductAttribute.objects.select_related("attribute_value").get(product=self.product)
        self.assertEqual(p_attr.attribute_value.value, "M12x1.5")

    def test_repeated_run_does_not_duplicate(self):
        service = self._service()
        rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 1901,
                "displaytitle": "Диаметр",
                "displayvalue": "25 мм",
            }
        ]
        with patch.object(service, "_find_article_attribute_rows", return_value=rows):
            first = service.enrich_product(product=self.product, dry_run=False)
            second = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(first.status, "updated")
        self.assertIn(second.status, {"skipped_hash_unchanged", "updated"})
        self.assertEqual(Attribute.objects.count(), 1)
        self.assertEqual(AttributeValue.objects.count(), 1)
        self.assertEqual(ProductAttribute.objects.filter(product=self.product).count(), 1)

    def test_reuses_attribute_by_autodb_id_even_if_name_changes_language(self):
        attr = Attribute.objects.create(
            name="висота",
            slug="vysota-uk-only",
            name_uk="висота",
            name_ru="",
            name_en="",
            source=Attribute.SOURCE_AUTODB_PRO,
            autodb_attribute_id=5001,
        )
        value = AttributeValue.objects.create(
            attribute=attr,
            value="82.15 мм",
            source=AttributeValue.SOURCE_AUTODB_PRO,
            autodb_attribute_id=5001,
        )
        ProductAttribute.objects.create(
            product=self.product,
            attribute=attr,
            attribute_value=value,
            source=ProductAttribute.SOURCE_AUTODB_PRO,
            autodb_attribute_id=5001,
        )

        service = self._service()
        rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 5001,
                "displaytitle": "высота",
                "displayvalue": "82.15 мм",
            }
        ]
        with patch.object(service, "_find_article_attribute_rows", return_value=rows):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertIn(result.status, {"updated", "skipped_hash_unchanged"})
        self.assertEqual(Attribute.objects.count(), 1)
        attr.refresh_from_db()
        self.assertEqual(attr.autodb_attribute_id, 5001)
        self.assertEqual(attr.name, "высота")
        self.assertEqual(ProductAttribute.objects.filter(product=self.product).count(), 1)

    def test_product_without_autodb_link_skipped(self):
        service = self._service()
        self.product.autodb_supplier_id = None
        self.product.autodb_article_number = ""
        self.product.save(update_fields=("autodb_supplier_id", "autodb_article_number", "updated_at"))

        result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.status, "skipped_no_autodb_link")

    def test_no_article_attributes_skipped(self):
        service = self._service()
        with patch.object(service, "_find_article_attribute_rows", return_value=[]):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.status, "skipped_no_article_attributes")

    def test_manual_product_attribute_not_overwritten(self):
        manual_attr = Attribute.objects.create(
            name="Материал",
            slug="material",
            name_uk="Матеріал",
            name_ru="Материал",
            name_en="Material",
            source=Attribute.SOURCE_MANUAL,
        )
        manual_value = AttributeValue.objects.create(
            attribute=manual_attr,
            value="Алюминий",
            value_uk="Алюміній",
            value_ru="Алюминий",
            value_en="Aluminium",
            source=AttributeValue.SOURCE_MANUAL,
        )
        ProductAttribute.objects.create(
            product=self.product,
            attribute=manual_attr,
            attribute_value=manual_value,
            raw_value="Алюминий",
            source=ProductAttribute.SOURCE_MANUAL,
            manual_locked=True,
        )

        service = self._service()
        rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 2001,
                "displaytitle": "Материал",
                "displayvalue": "Сталь",
            }
        ]
        with patch.object(service, "_find_article_attribute_rows", return_value=rows):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.status, "skipped_manual_locked")
        p_attr = ProductAttribute.objects.select_related("attribute_value").get(product=self.product, attribute=manual_attr)
        self.assertEqual(p_attr.attribute_value.value, "Алюминий")
        self.assertEqual(p_attr.source, ProductAttribute.SOURCE_MANUAL)

    def test_no_destructive_delete_when_rows_become_smaller(self):
        service = self._service()
        first_rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 2101,
                "displaytitle": "Диаметр",
                "displayvalue": "25 мм",
            },
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 2102,
                "displaytitle": "Длина",
                "displayvalue": "100 мм",
            },
        ]
        second_rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 2101,
                "displaytitle": "Диаметр",
                "displayvalue": "25 мм",
            }
        ]

        with patch.object(service, "_find_article_attribute_rows", return_value=first_rows):
            service.enrich_product(product=self.product, dry_run=False)
        with patch.object(service, "_find_article_attribute_rows", return_value=second_rows):
            service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(ProductAttribute.objects.filter(product=self.product).count(), 2)

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_utr_not_called_and_price_stock_unchanged(self, utr_cls):
        service = self._service()
        before_stock = self.product.available_stock_qty_cached
        rows = [
            {
                "supplierid": 300,
                "datasupplierarticlenumber": "820099",
                "id": 2201,
                "displaytitle": "Резьба",
                "displayvalue": "M12x1.5",
            }
        ]
        with patch.object(service, "_find_article_attribute_rows", return_value=rows):
            service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(self.product.available_stock_qty_cached, before_stock)
        utr_cls.assert_not_called()
