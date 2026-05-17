from __future__ import annotations

from django.test import TestCase

from apps.autodb.services.matching.backoffice_tecdoc_batch import BackofficeTecdocBatchSelector
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product


class BackofficeTecdocBatchSelectorTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="TecBrand", slug="tecbrand", is_active=True)
        self.category = Category.objects.create(name="Filters", slug="filters", is_active=True)

    def _make_product(self, *, sku: str, supplier_id: int, article: str, article_key: str) -> Product:
        return Product.objects.create(
            sku=sku,
            article=article,
            name=f"Product {sku}",
            slug=f"product-{sku.lower()}",
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_supplier_id=supplier_id,
            autodb_article_number=article,
            autodb_article_key=article_key,
            autodb_supplier_name="TecBrand",
            display_brand_name="TecBrand",
        )

    def test_select_candidates_skips_trusted_link_quality(self):
        trusted = self._make_product(sku="WIX-TRUSTED", supplier_id=10, article="WA6342", article_key="10:WA6342")
        untrusted = self._make_product(sku="WIX-UNTRUSTED", supplier_id=10, article="WA9999", article_key="10:WA9999")

        AutoDbProductLinkQuality.objects.update_or_create(
            product=trusted,
            autodb_article_key="10:WA6342",
            defaults={
                "autodb_supplier_id": 10,
                "autodb_article_number": "WA6342",
                "status": AutoDbProductLinkQuality.STATUS_TRUSTED,
                "reason": "test",
            },
        )
        AutoDbProductLinkQuality.objects.filter(
            product=untrusted,
            autodb_article_key="10:WA9999",
        ).update(
            status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
            reason="test_untrusted",
        )

        selected = BackofficeTecdocBatchSelector().select_candidates(limit=20)
        selected_ids = {item.product_id for item in selected}

        self.assertNotIn(str(trusted.id), selected_ids)
        self.assertIn(str(untrusted.id), selected_ids)

    def test_select_candidates_product_ids_mode_respects_requested_set(self):
        trusted = self._make_product(sku="WIX-ID-TRUSTED", supplier_id=10, article="WA1111", article_key="10:WA1111")
        untrusted = self._make_product(sku="WIX-ID-UNTRUSTED", supplier_id=10, article="WA2222", article_key="10:WA2222")

        AutoDbProductLinkQuality.objects.update_or_create(
            product=trusted,
            autodb_article_key="10:WA1111",
            defaults={
                "autodb_supplier_id": 10,
                "autodb_article_number": "WA1111",
                "status": AutoDbProductLinkQuality.STATUS_TRUSTED,
                "reason": "test",
            },
        )
        AutoDbProductLinkQuality.objects.filter(
            product=untrusted,
            autodb_article_key="10:WA2222",
        ).update(
            status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
            reason="test_untrusted",
        )

        selected = BackofficeTecdocBatchSelector().select_candidates(
            limit=20,
            product_ids=[str(trusted.id), str(untrusted.id)],
        )
        selected_ids = {item.product_id for item in selected}

        self.assertNotIn(str(trusted.id), selected_ids)
        self.assertIn(str(untrusted.id), selected_ids)
