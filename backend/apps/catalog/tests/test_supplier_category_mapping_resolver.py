from django.test import SimpleTestCase

from apps.catalog.services.supplier_category_mapping import STATUS_ACTIVE, SupplierCategoryMappingResolver


class SupplierCategoryMappingResolverTests(SimpleTestCase):
    def setUp(self):
        self.resolver = SupplierCategoryMappingResolver()

    def test_maps_winter_washer_fluid_to_technical_fluids(self):
        resolution = self.resolver.resolve_with_evidence(
            supplier_code="gpl",
            raw_category="Зимові омивачі скла",
            raw_group="ORGANIC PRINK",
            raw_name='Омивач скла зимовий ORGANIC PRINK -20 °С "Морський бриз" 4,2 л',
            raw_description="Омивач скла зимовий",
            product_name='Омивач скла зимовий ORGANIC PRINK -20 °С',
            supplier_product_name='Омивач скла зимовий ORGANIC PRINK -20 °С',
            raw_brand="ORGANIC PRINK",
        )

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.status, STATUS_ACTIVE)
        self.assertEqual(resolution.target_category_slug, "tekhnicheskie-zhidkosti")
        self.assertEqual(resolution.reason, "washer_fluid_signal")

    def test_maps_summer_washer_fluid_to_technical_fluids(self):
        resolution = self.resolver.resolve_with_evidence(
            supplier_code="gpl",
            raw_category="Літні омивачі скла",
            raw_group="VIRA",
            raw_name='Омивач скла літній VIRA "Мохіто" антимошка 4 л',
            raw_description="screenwash concentrate",
            product_name='Омивач скла літній VIRA "Мохіто" 4 л',
            supplier_product_name='Омивач скла літній VIRA "Мохіто" 4 л',
            raw_brand="VIRA",
        )

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.status, STATUS_ACTIVE)
        self.assertEqual(resolution.target_category_slug, "tekhnicheskie-zhidkosti")
        self.assertEqual(resolution.reason, "washer_fluid_signal")

    def test_does_not_map_washer_parts_as_fluids(self):
        resolution = self.resolver.resolve_with_evidence(
            supplier_code="gpl",
            raw_category="Омивачі скла",
            raw_group="AT",
            raw_name="Форсунка омивача скла AT",
            raw_description="Форсунка склоомивача",
            product_name="Форсунка омивача скла AT",
            supplier_product_name="Форсунка омивача скла AT",
            raw_brand="AT",
        )

        self.assertIsNone(resolution)

