from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.utr_product_enrichment import (
    enrich_utr_catalog_products,
    enrich_utr_product,
    enrich_visible_utr_applicability,
)
from apps.catalog.tasks.utr_product_enrichment import (
    enrich_utr_product_task,
    enrich_visible_utr_applicability_task,
)


@override_settings(UTR_CATALOG_ENRICHMENT_ENABLED=False)
class UtrCatalogKillSwitchTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand UTR", slug="brand-utr", is_active=True)
        self.category = Category.objects.create(name="Category UTR", slug="category-utr", is_active=True)
        self.product = Product.objects.create(
            sku="UTR-DISABLED-001",
            article="UTR-DISABLED-001",
            name="UTR Disabled Product",
            slug="utr-disabled-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

    @patch("apps.catalog.services.utr_product_enrichment.UtrClient")
    def test_enrich_utr_product_is_skipped_without_network(self, client_cls):
        result = enrich_utr_product(product_id=str(self.product.id), mode="detail")
        self.assertEqual(result["status"], "disabled")
        client_cls.assert_not_called()

    @patch("apps.catalog.services.utr_product_enrichment.UtrClient")
    def test_enrich_catalog_batch_is_skipped_without_network(self, client_cls):
        result = enrich_utr_catalog_products(product_ids=[str(self.product.id)])
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["skipped_disabled"], 1)
        client_cls.assert_not_called()

    @patch("apps.catalog.services.utr_product_enrichment.UtrClient")
    def test_enrich_applicability_is_skipped_without_network(self, client_cls):
        result = enrich_visible_utr_applicability(detail_ids=["12345"])
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["skipped_disabled"], 1)
        client_cls.assert_not_called()

    @patch("apps.catalog.tasks.utr_product_enrichment.enrich_utr_product")
    def test_task_is_skipped_by_kill_switch(self, enrich_mock):
        result = enrich_utr_product_task(product_id=str(self.product.id), mode="detail")
        self.assertEqual(result["status"], "disabled")
        enrich_mock.assert_not_called()

    @patch("apps.catalog.tasks.utr_product_enrichment.enrich_visible_utr_applicability")
    def test_applicability_task_is_skipped_by_kill_switch(self, enrich_mock):
        result = enrich_visible_utr_applicability_task(detail_ids=["123"])
        self.assertEqual(result["skipped_disabled"], 1)
        enrich_mock.assert_not_called()
