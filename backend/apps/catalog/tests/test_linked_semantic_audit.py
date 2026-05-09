from __future__ import annotations

from django.test import SimpleTestCase

from apps.catalog.services.linked_semantic_audit import detect_semantic_conflicts


class LinkedSemanticAuditTests(SimpleTestCase):
    def test_exhaust_raw_link_to_shock_autodb_is_blocked(self):
        conflicts = detect_semantic_conflicts(
            raw_brand="POLMO",
            raw_text="Глушник середній POLMO",
            product_text="",
            category_text="",
            autodb_title_text="Амортизатор",
        )

        self.assertIn("exhaust_vs_shock", {item.conflict_type for item in conflicts})

    def test_paint_raw_link_to_mechanical_part_is_blocked(self):
        conflicts = detect_semantic_conflicts(
            raw_brand="MITKA",
            raw_text="Автоемаль аерозольна фарба",
            product_text="",
            category_text="",
            autodb_title_text="Рычаг подвески",
        )

        self.assertIn("paint_chemical_vs_mechanical", {item.conflict_type for item in conflicts})

    def test_battery_raw_link_to_non_battery_is_blocked(self):
        conflicts = detect_semantic_conflicts(
            raw_brand="HAGENBATTERIE",
            raw_text="Акумулятор автомобільний",
            product_text="",
            category_text="",
            autodb_title_text="Тормозные колодки",
        )

        self.assertIn("battery_vs_non_battery", {item.conflict_type for item in conflicts})

    def test_battery_raw_link_to_battery_autodb_is_allowed(self):
        conflicts = detect_semantic_conflicts(
            raw_brand="HAGENBATTERIE",
            raw_text="Акумулятор автомобільний",
            product_text="",
            category_text="",
            autodb_title_text="Аккумуляторная батарея",
        )

        self.assertEqual(conflicts, [])

    def test_filter_raw_link_to_filter_autodb_is_allowed(self):
        conflicts = detect_semantic_conflicts(
            raw_brand="WIX FILTERS",
            raw_text="Фільтр оливи",
            product_text="",
            category_text="",
            autodb_title_text="Масляный фильтр",
        )

        self.assertEqual(conflicts, [])

    def test_exact_brand_article_still_blocks_semantic_conflict(self):
        conflicts = detect_semantic_conflicts(
            raw_brand="WIX FILTERS",
            raw_text="Фільтр повітряний article exact-match",
            product_text="",
            category_text="",
            autodb_title_text="Амортизатор article exact-match",
        )

        self.assertIn("filter_vs_non_filter", {item.conflict_type for item in conflicts})

    def test_primera_model_name_does_not_trigger_primer_paint_conflict(self):
        conflicts = detect_semantic_conflicts(
            raw_brand="BOSAL",
            raw_text="Глушник BOSAL Nissan Primera 02-08",
            product_text="",
            category_text="Глушитель",
            autodb_title_text="Exhaust",
        )

        self.assertNotIn("paint_chemical_vs_mechanical", {item.conflict_type for item in conflicts})

    def test_primer_and_paint_keywords_still_trigger_paint_chemical_conflict(self):
        for raw_text in (
            "Primer acrylic for body panel",
            "Грунт автомобільний аерозоль",
            "Шпаклівка для кузова",
            "Paint enamel spray",
        ):
            conflicts = detect_semantic_conflicts(
                raw_brand="TEST",
                raw_text=raw_text,
                product_text="",
                category_text="",
                autodb_title_text="Амортизатор",
            )
            self.assertIn("paint_chemical_vs_mechanical", {item.conflict_type for item in conflicts})
