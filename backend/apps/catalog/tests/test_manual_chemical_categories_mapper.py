from __future__ import annotations

from django.test import SimpleTestCase

from apps.catalog.services.manual_chemical_categories import (
    STATUS_NEEDS_REVIEW,
    STATUS_SAFE,
    decide_manual_chemical_category,
    extract_manual_chemical_payload_fields,
)


class ManualChemicalCategoriesMapperTests(SimpleTestCase):
    def test_k2_euroblue_maps_to_adblue_category(self):
        payload = extract_manual_chemical_payload_fields(
            {
                "Категорія": "Технічні рідини",
                "Група ТД": "AdBlue",
                "Найменування": "Розчин сечовини K2 EuroBlue 5 л",
                "Опис": "DEF urea technical fluid",
            }
        )
        decision = decide_manual_chemical_category(
            product_name="Розчин сечовини K2 EuroBlue 5 л",
            brand="K2",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_SAFE)
        self.assertEqual(decision.proposed_slug, "adblue-i-tekhnicheskie-zhidkosti")

    def test_mitka_abrasive_circle_does_not_map_to_paint(self):
        payload = extract_manual_chemical_payload_fields(
            {
                "Категорія": "MITKA",
                "Група ТД": "MITKA",
                "Найменування": "Круг наждачний MITKA P320",
                "Опис": "абразивний круг для шліфування",
            }
        )
        decision = decide_manual_chemical_category(
            product_name="Круг наждачний MITKA P320",
            brand="MITKA",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_NEEDS_REVIEW)
        self.assertEqual(decision.proposed_slug, "")

    def test_cssystem_paper_sponge_workwear_does_not_map_to_paint(self):
        payload = extract_manual_chemical_payload_fields(
            {
                "Категорія": "CS SYSTEM",
                "Група ТД": "CS SYSTEM",
                "Найменування": "Комбінезон, губка та папір шліфувальний",
                "Опис": "захисні окуляри та робочий одяг",
            }
        )
        decision = decide_manual_chemical_category(
            product_name="Комбінезон CS SYSTEM",
            brand="CS SYSTEM",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_NEEDS_REVIEW)
        self.assertEqual(decision.proposed_slug, "")

    def test_mitka_explicit_paint_maps_correctly(self):
        payload = extract_manual_chemical_payload_fields(
            {
                "Категорія": "MITKA",
                "Група ТД": "MITKA",
                "Найменування": "Емаль автомобільна MITKA 118 аерозоль",
                "Опис": "фарба аерозольна",
            }
        )
        decision = decide_manual_chemical_category(
            product_name="Емаль автомобільна MITKA 118",
            brand="MITKA",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_SAFE)
        self.assertEqual(decision.proposed_slug, "aerozolnye-kraski")

    def test_negative_keywords_override_brand_when_mixed(self):
        payload = extract_manual_chemical_payload_fields(
            {
                "Категорія": "MITKA",
                "Група ТД": "MITKA",
                "Найменування": "Фарба MITKA + шліфувальний папір",
                "Опис": "комплект",
            }
        )
        decision = decide_manual_chemical_category(
            product_name="Фарба MITKA + шліфувальний папір",
            brand="MITKA",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_NEEDS_REVIEW)
