from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.services.product_category_enrichment import AutoDbProductCategoryEnrichmentService
from apps.autodb.services.prd_root_category_mapper import AutoDbPrdRootCategoryMapper
from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS


class AutoDbProductCategoryEnrichmentServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand", is_active=True)
        self.manual_roots: dict[str, Category] = {}
        for spec in MANUAL_ROOT_CATEGORY_SPECS:
            self.manual_roots[spec.slug] = Category.objects.create(
                name=spec.name,
                name_uk=spec.name_uk,
                name_ru=spec.name_ru,
                name_en=spec.name_en,
                slug=spec.slug,
                source=Category.SOURCE_MANUAL,
                show_in_header=True,
                is_assignable=False,
                is_active=True,
            )
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
        self.assertIsNotNone(self.product.category.parent_id)
        self.assertEqual(self.product.category.parent.source, Category.SOURCE_MANUAL)
        self.assertEqual(self.product.category.parent.slug, "elektrika-i-osveshchenie")

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
        self.assertIsNotNone(self.product.category.parent_id)
        self.assertEqual(self.product.category.parent.slug, "dvigatel-i-vykhlop")

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
        existing.refresh_from_db()
        self.assertIsNotNone(existing.parent_id)

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
        self.assertEqual(cat.slug, "autodb-prd-505")
        self.assertFalse(cat.show_in_header)
        self.assertIsNotNone(cat.parent_id)

    def test_category_reused_by_normalized_name_when_autodb_prd_missing(self):
        root = self.manual_roots["elektrika-i-osveshchenie"]
        existing = Category.objects.create(
            name="  Датчик тиску  ",
            name_uk="Датчик тиску",
            slug="autodb-old-sensor",
            autodb_prd_id=None,
            source=Category.SOURCE_AUTODB_PRO,
            parent=root,
            show_in_header=True,
            is_active=True,
        )
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 909}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 909, "description": "датчик  тиску"}]),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertEqual(self.product.category_id, existing.id)
        self.assertEqual(existing.autodb_prd_id, 909)
        self.assertFalse(existing.show_in_header)

    def test_autodb_singular_battery_reuses_manual_plural_canonical_category(self):
        root = self.manual_roots["elektrika-i-osveshchenie"]
        canonical = Category.objects.create(
            name="Аккумуляторы",
            name_uk="Акумулятори",
            name_ru="Аккумуляторы",
            name_en="Batteries",
            slug="akkumuliatory",
            autodb_prd_id=None,
            source=Category.SOURCE_MANUAL,
            parent=root,
            show_in_header=False,
            is_active=True,
        )
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 1}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 1, "description": "Аккумулятор"}]),
            patch.object(
                service.root_mapper,
                "resolve",
                return_value=SimpleNamespace(
                    status=AutoDbPrdRootCategoryMapper.STATUS_MAPPED,
                    root_slug="elektrika-i-osveshchenie",
                    root_name="Электрика и освещение",
                    confidence=0.99,
                    reason="test",
                ),
            ),
            patch.object(service.root_mapper, "resolve_root_category", return_value=root),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        canonical.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertEqual(self.product.category_id, canonical.id)
        self.assertEqual(canonical.autodb_prd_id, 1)
        self.assertEqual(canonical.slug, "akkumuliatory")
        self.assertEqual(canonical.name_ru, "Аккумуляторы")

    def test_autodb_singular_shock_reuses_manual_plural_canonical_category(self):
        root = self.manual_roots["podveska-i-rulevoe"]
        canonical = Category.objects.create(
            name="Амортизаторы",
            name_uk="Амортизатори",
            name_ru="Амортизаторы",
            name_en="Shock absorbers",
            slug="amortizatory",
            autodb_prd_id=None,
            source=Category.SOURCE_MANUAL,
            parent=root,
            show_in_header=False,
            is_active=True,
        )
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 854}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 854, "description": "Амортизатор"}]),
            patch.object(
                service.root_mapper,
                "resolve",
                return_value=SimpleNamespace(
                    status=AutoDbPrdRootCategoryMapper.STATUS_MAPPED,
                    root_slug="podveska-i-rulevoe",
                    root_name="Подвеска и рулевое",
                    confidence=0.99,
                    reason="test",
                ),
            ),
            patch.object(service.root_mapper, "resolve_root_category", return_value=root),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        canonical.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertEqual(self.product.category_id, canonical.id)
        self.assertEqual(canonical.autodb_prd_id, 854)
        self.assertEqual(canonical.slug, "amortizatory")
        self.assertEqual(canonical.name_ru, "Амортизаторы")

    def test_autodb_reuses_seeded_assignable_leaf_below_menu_group(self):
        call_command("seed_catalog_taxonomy_v2", stdout=StringIO())
        root = Category.objects.get(slug="podveska-i-rulevoe")
        seeded_leaf = Category.objects.get(slug="amortizatory")
        self.assertTrue(seeded_leaf.is_assignable)
        self.assertEqual(seeded_leaf.parent.parent_id, root.id)

        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 854}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 854, "description": "Амортизатор"}]),
            patch.object(
                service.root_mapper,
                "resolve",
                return_value=SimpleNamespace(
                    status=AutoDbPrdRootCategoryMapper.STATUS_MAPPED,
                    root_slug="podveska-i-rulevoe",
                    root_name="Подвеска и рулевое",
                    confidence=0.99,
                    reason="test",
                ),
            ),
            patch.object(service.root_mapper, "resolve_root_category", return_value=root),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        seeded_leaf.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertEqual(self.product.category_id, seeded_leaf.id)
        self.assertEqual(seeded_leaf.autodb_prd_id, 854)

    def test_unknown_root_mapping_is_skipped(self):
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 707}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 707, "description": "Нестандартная деталь XYZ"}]),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "skipped_no_root_mapping")
        self.assertEqual(self.product.category_id, self.initial_category.id)
        self.assertFalse(Category.objects.filter(autodb_prd_id=707).exists())

    def test_ignition_coil_maps_to_electrics_root(self):
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 808}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(
                service,
                "_find_prd_rows",
                return_value=[
                    {
                        "id": 808,
                        "description": "Катушка зажигания",
                        "assemblygroupdescription": "Система зажигания / накаливания",
                    }
                ],
            ),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "updated")
        self.assertEqual(self.product.category.parent.slug, "elektrika-i-osveshchenie")

    def test_components_unclear_skips_no_root_mapping(self):
        service = self._service()
        with (
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 909}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(
                service,
                "_find_prd_rows",
                return_value=[
                    {
                        "id": 909,
                        "description": "Комплектующие для узла",
                        "assemblygroupdescription": "Комплектующие",
                    }
                ],
            ),
        ):
            result = service.enrich_product(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(result.status, "skipped_no_root_mapping")
        self.assertEqual(self.product.category_id, self.initial_category.id)
        self.assertFalse(Category.objects.filter(autodb_prd_id=909).exists())

    def test_category_update_does_not_change_product_names(self):
        service = self._service()
        self.product.name = "Підшипник маточини"
        self.product.name_uk = "Підшипник маточини"
        self.product.name_ru = "Подшипник ступицы"
        self.product.name_en = "Hub bearing"
        self.product.save(update_fields=("name", "name_uk", "name_ru", "name_en", "updated_at"))
        before = (self.product.name, self.product.name_uk, self.product.name_ru, self.product.name_en)

        with (
            patch.object(service, "_find_article_row", return_value={"NormalizedDescription": "Свеча зажигания"}),
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 505}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 505, "description": "Свеча зажигания"}]),
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
            patch.object(service, "_find_article_row", return_value={"NormalizedDescription": "Свеча зажигания"}),
            patch.object(service, "_find_article_prd_rows", return_value=[{"productid": 505}]),
            patch.object(service, "_find_article_links_rows", return_value=[]),
            patch.object(service, "_find_prd_rows", return_value=[{"id": 505, "description": "Свеча зажигания"}]),
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
