from __future__ import annotations

from django.test import SimpleTestCase

from apps.catalog.services.autodb_link_compatibility import evaluate_category_compatibility


class AutoDbLinkCompatibilityTests(SimpleTestCase):
    def test_filter_exact_equivalence_is_promoted(self):
        score, rule = evaluate_category_compatibility(
            raw_category="Повітряні фільтри",
            raw_group="WIX FILTERS",
            mapped_site_category="Воздушный фильтр",
            candidate_group="",
            candidate_title="",
        )
        self.assertGreaterEqual(score, 0.99)
        self.assertIn("explicit_equivalence", rule)

    def test_generic_sensor_does_not_get_safe_equivalence(self):
        score, rule = evaluate_category_compatibility(
            raw_category="Датчики",
            raw_group="AUTOMEGA",
            mapped_site_category="",
            candidate_group="",
            candidate_title="",
        )
        self.assertLess(score, 0.7)
        self.assertNotIn("explicit_equivalence", rule)

    def test_generic_gasket_is_not_safely_promoted(self):
        score, rule = evaluate_category_compatibility(
            raw_category="Прокладки",
            raw_group="AT",
            mapped_site_category="Прокладка ГБЦ",
            candidate_group="",
            candidate_title="",
        )
        self.assertLess(score, 0.7)
        self.assertNotIn("explicit_equivalence", rule)

    def test_brake_repair_kit_equivalence_is_promoted(self):
        score, rule = evaluate_category_compatibility(
            raw_category="Ремкомплекти гальмівної системи",
            raw_group="ERT",
            mapped_site_category="Ремкомплект суппорта",
            candidate_group="",
            candidate_title="",
        )
        self.assertGreaterEqual(score, 0.99)
        self.assertIn("explicit_equivalence", rule)

    def test_ignition_wires_equivalence_is_promoted(self):
        score, rule = evaluate_category_compatibility(
            raw_category="Дроти запалювання",
            raw_group="TESLA",
            mapped_site_category="Провода высоковольтные",
            candidate_group="",
            candidate_title="",
        )
        self.assertGreaterEqual(score, 0.99)
        self.assertIn("explicit_equivalence", rule)

    def test_generic_sensors_still_not_promoted(self):
        score, rule = evaluate_category_compatibility(
            raw_category="Датчики",
            raw_group="AUTOMEGA",
            mapped_site_category="Датчик ABS",
            candidate_group="",
            candidate_title="",
        )
        self.assertLess(score, 0.7)
        self.assertNotIn("explicit_equivalence", rule)
