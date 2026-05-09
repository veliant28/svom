from django.test import TestCase

from apps.catalog.models import Category
from apps.catalog.services.category_vehicle_filter_policy import (
    SHOW_ALL_WITH_BADGES,
    STRICT_FITMENT,
    get_vehicle_filter_policy,
    is_vehicle_filter_exempt_category,
)


class CategoryVehicleFilterPolicyTests(TestCase):
    def test_wheels_and_chemistry_roots_are_exempt_with_descendants(self):
        wheels = Category.objects.create(name="Колёса и шины", slug="kolesa-i-shiny", is_active=True)
        wheels_child = Category.objects.create(name="Шины", slug="policy-tires", parent=wheels, is_active=True)
        chemistry = Category.objects.create(name="Автохимия и аксессуары", slug="avtohimiia-i-aksessuary", is_active=True)
        chemistry_child = Category.objects.create(name="Масла", slug="policy-oils", parent=chemistry, is_active=True)

        self.assertTrue(is_vehicle_filter_exempt_category(wheels))
        self.assertTrue(is_vehicle_filter_exempt_category(wheels_child))
        self.assertEqual(get_vehicle_filter_policy(chemistry), SHOW_ALL_WITH_BADGES)
        self.assertEqual(get_vehicle_filter_policy(chemistry_child), SHOW_ALL_WITH_BADGES)

    def test_other_categories_stay_strict(self):
        strict = Category.objects.create(name="Запчасти для ТО", slug="zapchasti-dlia-to", is_active=True)

        self.assertFalse(is_vehicle_filter_exempt_category(strict))
        self.assertEqual(get_vehicle_filter_policy(strict), STRICT_FITMENT)
