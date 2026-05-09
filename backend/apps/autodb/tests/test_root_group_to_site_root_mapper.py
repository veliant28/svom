from django.test import SimpleTestCase

from apps.autodb.services import AutoDbRootGroupToSiteRootMapper


class AutoDbRootGroupToSiteRootMapperTests(SimpleTestCase):
    def setUp(self):
        self.mapper = AutoDbRootGroupToSiteRootMapper()

    def test_known_group_map(self):
        result = self.mapper.map_group(root_group="тормозная система")
        self.assertEqual(result.status, self.mapper.STATUS_MAPPED)
        self.assertEqual(result.site_root_slug, "tormoznaia-sistema")

    def test_keyword_fallback(self):
        result = self.mapper.map_group(root_group="Неизвестная группа", sample_text="Комплект ремня ГРМ")
        self.assertEqual(result.status, self.mapper.STATUS_MAPPED)
        self.assertEqual(result.site_root_slug, "to-i-raskhodniki")

    def test_skipped_no_root_mapping_when_no_match(self):
        result = self.mapper.map_group(root_group="Комплектующие")
        self.assertEqual(result.status, self.mapper.STATUS_NEEDS_REVIEW)
        self.assertEqual(result.site_root_slug, "")

    def test_ignition_group_spark_plug_to_maintenance(self):
        result = self.mapper.map_prd(
            root_group="Система зажигания / накаливания",
            prd_description="Свеча зажигания",
            prd_normalized_description="Spark plug",
            prd_assembly_group_description="Система зажигания / накаливания",
            prd_usage_description="",
        )
        self.assertEqual(result.status, self.mapper.STATUS_MAPPED)
        self.assertEqual(result.site_root_slug, "to-i-raskhodniki")

    def test_ignition_group_coil_to_electrics(self):
        result = self.mapper.map_prd(
            root_group="Система зажигания / накаливания",
            prd_description="Катушка зажигания",
            prd_normalized_description="Ignition coil",
            prd_assembly_group_description="Система зажигания / накаливания",
            prd_usage_description="",
        )
        self.assertEqual(result.status, self.mapper.STATUS_MAPPED)
        self.assertEqual(result.site_root_slug, "elektrika-i-osveshchenie")

    def test_components_group_unclear_needs_review(self):
        result = self.mapper.map_prd(
            root_group="Комплектующие",
            prd_description="Комплектующие для узла",
            prd_normalized_description="",
            prd_assembly_group_description="Комплектующие",
            prd_usage_description="",
        )
        self.assertEqual(result.status, self.mapper.STATUS_NEEDS_REVIEW)
        self.assertEqual(result.site_root_slug, "")

    def test_empty_group_skipped_no_root_mapping(self):
        result = self.mapper.map_prd(
            root_group="",
            prd_description="",
            prd_normalized_description="",
            prd_assembly_group_description="",
            prd_usage_description="",
        )
        self.assertEqual(result.status, self.mapper.STATUS_SKIPPED_NO_ROOT_MAPPING)
