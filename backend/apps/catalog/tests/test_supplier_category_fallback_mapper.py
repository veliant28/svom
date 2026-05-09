from __future__ import annotations

from django.test import SimpleTestCase

from apps.catalog.services.supplier_category_fallback import SupplierCategoryFallbackInput, SupplierCategoryToSiteRootMapper


class SupplierCategoryToSiteRootMapperTests(SimpleTestCase):
    def setUp(self):
        self.mapper = SupplierCategoryToSiteRootMapper()

    def test_mitka_paint_maps_to_auto_chemistry(self):
        decision = self.mapper.map(
            SupplierCategoryFallbackInput(
                product_name="Емаль автомобільна MITKA 871167 аерозоль",
                supplier_product_name="",
                raw_category="MITKA",
                raw_group="",
                raw_name="",
                raw_description="",
                raw_article_td="",
                raw_code="",
                display_brand="MITKA",
            )
        )
        self.assertEqual(decision.status, SupplierCategoryToSiteRootMapper.STATUS_MAPPED_CHILD_CATEGORY)
        self.assertEqual(decision.proposed_root_slug, "avtohimiia-i-aksessuary")

    def test_amortizer_maps_to_suspension(self):
        decision = self.mapper.map(
            SupplierCategoryFallbackInput(
                product_name="Амортизатор передній",
                supplier_product_name="",
                raw_category="",
                raw_group="",
                raw_name="",
                raw_description="",
                raw_article_td="",
                raw_code="",
                display_brand="DAINTON",
            )
        )
        self.assertEqual(decision.proposed_root_slug, "podveska-i-rulevoe")
        self.assertIn(decision.status, {
            SupplierCategoryToSiteRootMapper.STATUS_MAPPED_ROOT_ONLY,
            SupplierCategoryToSiteRootMapper.STATUS_MAPPED_CHILD_CATEGORY,
        })

    def test_unknown_signal_returns_unclear(self):
        decision = self.mapper.map(
            SupplierCategoryFallbackInput(
                product_name="Набор XQ-17",
                supplier_product_name="",
                raw_category="",
                raw_group="",
                raw_name="",
                raw_description="",
                raw_article_td="",
                raw_code="",
                display_brand="UNKNOWN",
            )
        )
        self.assertEqual(decision.status, SupplierCategoryToSiteRootMapper.STATUS_SKIPPED_UNCLEAR)
