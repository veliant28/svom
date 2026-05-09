from __future__ import annotations

from django.test import TestCase

from apps.autodb.services.prd_root_category_mapper import AutoDbPrdRootCategoryMapper
from apps.catalog.models import Category
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS


class AutoDbPrdRootCategoryMapperTests(TestCase):
    def setUp(self):
        for spec in MANUAL_ROOT_CATEGORY_SPECS:
            Category.objects.create(
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
        self.mapper = AutoDbPrdRootCategoryMapper()

    def test_maps_brake_keywords(self):
        result = self.mapper.resolve(
            prd_description="Гальмівні колодки",
            prd_normalized_description="",
            prd_assembly_group_description="",
            product_display_name="",
            autodb_article_title="",
        )
        self.assertEqual(result.status, AutoDbPrdRootCategoryMapper.STATUS_MAPPED)
        self.assertEqual(result.root_slug, "tormoznaia-sistema")
        self.assertIsNotNone(self.mapper.resolve_root_category(root_slug=result.root_slug))

    def test_suspension_keywords_map_to_suspension_root(self):
        result = self.mapper.resolve(
            prd_description="Амортизатор",
            prd_normalized_description="",
            prd_assembly_group_description="",
            product_display_name="",
            autodb_article_title="",
        )
        self.assertEqual(result.status, AutoDbPrdRootCategoryMapper.STATUS_MAPPED)
        self.assertEqual(result.root_slug, "podveska-i-rulevoe")

    def test_ignition_spark_plug_maps_to_electrics_root(self):
        result = self.mapper.resolve(
            prd_description="Свеча зажигания",
            prd_normalized_description="Spark plug",
            prd_assembly_group_description="Система зажигания / накаливания",
            prd_usage_description="",
            product_display_name="",
            autodb_article_title="",
        )
        self.assertEqual(result.status, AutoDbPrdRootCategoryMapper.STATUS_MAPPED)
        self.assertEqual(result.root_slug, "elektrika-i-osveshchenie")

    def test_ignition_coil_maps_to_electrics_root(self):
        result = self.mapper.resolve(
            prd_description="Катушка зажигания",
            prd_normalized_description="Ignition coil",
            prd_assembly_group_description="Система зажигания / накаливания",
            prd_usage_description="",
            product_display_name="",
            autodb_article_title="",
        )
        self.assertEqual(result.status, AutoDbPrdRootCategoryMapper.STATUS_MAPPED)
        self.assertEqual(result.root_slug, "elektrika-i-osveshchenie")

    def test_components_unclear_skipped(self):
        result = self.mapper.resolve(
            prd_description="Комплектующие для узла",
            prd_normalized_description="",
            prd_assembly_group_description="Комплектующие",
            prd_usage_description="",
            product_display_name="",
            autodb_article_title="",
        )
        self.assertEqual(result.status, AutoDbPrdRootCategoryMapper.STATUS_NEEDS_ROOT_CATEGORY_MAPPING)
        self.assertEqual(result.root_slug, "")
