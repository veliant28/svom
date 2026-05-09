from __future__ import annotations

from django.test import SimpleTestCase

from apps.catalog.services.manual_remaining_categories import (
    STATUS_NEEDS_REVIEW,
    STATUS_SAFE,
    STATUS_SKIP,
    decide_remaining_manual_category,
    extract_remaining_payload_fields,
)


class RemainingManualCategoriesMapperTests(SimpleTestCase):
    def test_dainton_requires_shock_signal(self):
        payload = extract_remaining_payload_fields({"Найменування": "DAINTON D181007"})
        decision = decide_remaining_manual_category(
            product_name="DAINTON D181007",
            supplier_product_name="",
            brand="DAINTON",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_NEEDS_REVIEW)

    def test_dainton_shock_maps_to_amortizatory(self):
        payload = extract_remaining_payload_fields({"Найменування": "Амортизатор DAINTON D181007"})
        decision = decide_remaining_manual_category(
            product_name="Амортизатор DAINTON D181007",
            supplier_product_name="",
            brand="DAINTON",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_SAFE)
        self.assertEqual(decision.proposed_slug, "amortizatory")

    def test_hagen_battery_maps_to_akkumuliatory(self):
        payload = extract_remaining_payload_fields({"Опис": "Battery 74Ah"})
        decision = decide_remaining_manual_category(
            product_name="Акумулятор HAGEN BATTERIE 74Ah",
            supplier_product_name="",
            brand="HAGEN BATTERIE",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_SAFE)
        self.assertEqual(decision.proposed_slug, "akkumuliatory")

    def test_unknown_without_signal_skips(self):
        payload = extract_remaining_payload_fields({"Найменування": "Набір XQ17"})
        decision = decide_remaining_manual_category(
            product_name="Набір XQ17",
            supplier_product_name="",
            brand="UNKNOWN",
            payload=payload,
        )
        self.assertEqual(decision.status, STATUS_SKIP)
