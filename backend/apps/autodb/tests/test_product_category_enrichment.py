from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import TestCase

from apps.autodb.services.product_category_enrichment import AutoDbProductCategoryEnrichmentService
from apps.catalog.models import Brand, Category, Product


class AutoDbProductCategoryEnrichmentServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand", is_active=True)
        self.initial_category = Category.objects.create(name="Legacy", slug="legacy", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-1",
            slug="product-1",
            name="Product 1",
            brand=self.brand,
            category=self.initial_category,
            article="A1",
            autodb_supplier_id=15,
            autodb_article_number="0127",
            autodb_article_key="15:0127",
            is_active=True,
        )

    def _service(self) -> AutoDbProductCategoryEnrichmentService:
        service = AutoDbProductCategoryEnrichmentService()
        service._find_article_row = Mock(return_value={})
        return service

    def test_category_from_article_prd_product_id(self):
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"supplierid": 15, "datasupplierarticlenumber": "0127", "productid": 101}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(
                service,
                "_find_prd_rows",
                return_value=[{"id": 101, "description": "Свічки запалювання", "parentid": None}],
            ),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertEqual(result.chosen_source, "article_prd")
        self.assertEqual(self.product.category.autodb_prd_id, 101)
        self.assertEqual(self.product.category.source, Category.SOURCE_AUTODB_PRO)

    def test_category_from_article_links_product_id(self):
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[]),
            patch.object(service, "_find_article_links_rows", return_value=[{"supplierid": 15, "datasupplierarticlenumber": "0127", "productid": 202}]),
            patch.object(
                service,
                "_find_prd_rows",
                return_value=[{"id": 202, "description": "Фільтри", "parentid": None}],
            ),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertEqual(result.chosen_source, "article_links")
        self.assertEqual(self.product.category.autodb_prd_id, 202)

    def test_product_without_autodb_link_skipped(self):
        service = self._service()
        self.product.autodb_supplier_id = None
        self.product.autodb_article_number = ""
        self.product.save(update_fields=("autodb_supplier_id", "autodb_article_number", "updated_at"))

        result = service.enrich_product(product=self.product, dry_run=False)

        self.assertEqual(result.status, "skipped_no_autodb_link")

    def test_no_rows_skips_and_keeps_category(self):
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[]),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "skipped_no_autodb_category")
        self.assertEqual(self.product.category_id, self.initial_category.id)

    def test_manual_lock_not_overwritten(self):
        service = self._service()
        self.product.category_manually_locked = True
        self.product.save(update_fields=("category_manually_locked", "updated_at"))

        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 303}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 303, "description": "Запалювання"}]),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "skipped_manual_locked")
        self.assertEqual(self.product.category_id, self.initial_category.id)

    def test_category_reused_by_autodb_prd_id(self):
        existing = Category.objects.create(
            name="Existing",
            name_uk="Existing",
            name_ru="Existing",
            name_en="Existing",
            slug="existing-404",
            autodb_prd_id=404,
            source=Category.SOURCE_AUTODB_PRO,
            is_active=True,
        )
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 404}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 404, "description": "Інструменти"}]),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertTrue(result.reused_category)
        self.assertEqual(self.product.category_id, existing.id)

    def test_category_created_with_i18n_names(self):
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 505}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 505, "description": "Свічки запалювання"}]),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        cat = self.product.category
        self.assertEqual(result.status, "updated")
        self.assertTrue(result.created_category)
        self.assertEqual(cat.name_uk, "Свічки запалювання")
        self.assertTrue(bool(cat.name_ru))
        self.assertTrue(bool(cat.name_en))

    def test_category_update_does_not_change_product_names(self):
        service = self._service()
        self.product.name = "Підшипник маточини"
        self.product.name_uk = "Підшипник маточини"
        self.product.name_ru = "Подшипник ступицы"
        self.product.name_en = "Hub bearing"
        self.product.save(update_fields=("name", "name_uk", "name_ru", "name_en", "updated_at"))
        before = (self.product.name, self.product.name_uk, self.product.name_ru, self.product.name_en)

        with (
            patch.object(service, "_find_article_row", return_value={"NormalizedDescription": "Шарнирный комплект"}),
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 505}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 505, "description": "Шарнирный комплект"}]),
            patch.object(service, "_detect_suspicious_link", return_value=(False, "")),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        after = (self.product.name, self.product.name_uk, self.product.name_ru, self.product.name_en)
        self.assertEqual(result.status, "updated")
        self.assertEqual(before, after)

    def test_suspicious_link_is_skipped(self):
        service = self._service()
        self.product.name = "Підшипник маточини"
        self.product.name_uk = "Підшипник маточини"
        self.product.save(update_fields=("name", "name_uk", "updated_at"))

        with (
            patch.object(service, "_find_article_row", return_value={"NormalizedDescription": "Шарнирный комплект"}),
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 505}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 505, "description": "Шарнирный комплект"}]),
            patch.object(service, "_detect_suspicious_link", return_value=(True, "conflict")),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "skipped_suspicious_link")
        self.assertEqual(self.product.category_id, self.initial_category.id)

    def test_category_model_has_no_cross_db_fk(self):
        field = Category._meta.get_field("autodb_prd_id")
        self.assertEqual(field.get_internal_type(), "BigIntegerField")

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_utr_not_called_and_price_stock_unchanged(self, utr_cls):
        service = self._service()
        before_stock = self.product.available_stock_qty_cached

        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 606}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 606, "description": "Фільтр салону"}]),
        ):
            service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(self.product.available_stock_qty_cached, before_stock)
        utr_cls.assert_not_called()
