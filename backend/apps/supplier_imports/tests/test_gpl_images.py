from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.services.gpl_images import GplProductImageService


class GplProductImageServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.category = Category.objects.create(name="Category", slug="category", is_active=True)
        self.product = Product.objects.create(
            sku="IMG-1",
            slug="img-1",
            name="Image product",
            article="A-1",
            brand=self.brand,
            category=self.category,
            is_active=True,
            available_stock_qty_cached=7,
        )
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="/tmp/gpl.json",
            is_active=True,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test")

    def _offer(self, payload: dict, external_sku: str = "SKU-1") -> SupplierRawOffer:
        return SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku=external_sku,
            article="A-1",
            normalized_article="A1",
            brand_name="Brand",
            normalized_brand="brand",
            product_name="Image product",
            matched_product=self.product,
            raw_payload=payload,
        )

    def test_gpl_image_creates_product_image(self):
        self._offer({"Зображення товару": "https://cdn.example.com/a.jpg"})

        result = GplProductImageService().sync_product_images(product=self.product, dry_run=False)

        image = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_GPL_PRICE)
        self.assertTrue(result.has_candidates)
        self.assertEqual(result.created, 1)
        self.assertEqual(image.remote_url, "https://cdn.example.com/a.jpg")

    def test_gpl_image_becomes_primary_if_no_manual_primary(self):
        self._offer({"image_url": "https://cdn.example.com/a.jpg"})

        GplProductImageService().sync_product_images(product=self.product, dry_run=False)

        image = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_GPL_PRICE)
        self.assertTrue(image.is_primary)

    def test_manual_primary_not_overwritten(self):
        ProductImage.objects.create(
            product=self.product,
            image=None,
            remote_url="https://manual.example.com/main.jpg",
            source=ProductImage.SOURCE_MANUAL,
            is_primary=True,
            sort_order=0,
        )
        self._offer({"image_url": "https://cdn.example.com/a.jpg"})

        result = GplProductImageService().sync_product_images(product=self.product, dry_run=False)

        manual = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_MANUAL)
        gpl = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_GPL_PRICE)
        self.assertTrue(result.skipped_manual_primary)
        self.assertTrue(manual.is_primary)
        self.assertFalse(gpl.is_primary)

    def test_gpl_primary_overrides_non_manual_primary(self):
        ProductImage.objects.create(
            product=self.product,
            image=None,
            remote_url="https://legacy.example.com/main.jpg",
            source=ProductImage.SOURCE_IMPORTED,
            is_primary=True,
            sort_order=0,
        )
        self._offer({"image_url": "https://cdn.example.com/a.jpg"})

        GplProductImageService().sync_product_images(product=self.product, dry_run=False)

        legacy = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_IMPORTED)
        gpl = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_GPL_PRICE)
        self.assertFalse(legacy.is_primary)
        self.assertTrue(gpl.is_primary)

    def test_repeated_run_no_duplicates(self):
        self._offer({"images": ["https://cdn.example.com/a.jpg", "https://cdn.example.com/a.jpg"]})
        service = GplProductImageService()

        first = service.sync_product_images(product=self.product, dry_run=False)
        second = service.sync_product_images(product=self.product, dry_run=False)

        self.assertEqual(first.created, 1)
        self.assertEqual(second.created, 0)
        self.assertEqual(ProductImage.objects.filter(product=self.product, source=ProductImage.SOURCE_GPL_PRICE).count(), 1)

    def test_missing_latest_image_marks_stale_without_delete(self):
        self._offer({"image_url": "https://cdn.example.com/a.jpg"}, external_sku="SKU-1")
        service = GplProductImageService()
        service.sync_product_images(product=self.product, dry_run=False)

        self._offer({"image_url": "https://cdn.example.com/b.jpg"}, external_sku="SKU-2")
        result = service.sync_product_images(product=self.product, dry_run=False)

        stale = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_GPL_PRICE, remote_url="https://cdn.example.com/a.jpg")
        active = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_GPL_PRICE, remote_url="https://cdn.example.com/b.jpg")
        self.assertEqual(result.stale_marked, 1)
        self.assertTrue(stale.is_stale)
        self.assertEqual(stale.stale_reason, "missing_from_latest_import")
        self.assertFalse(active.is_stale)

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_utr_not_called_and_price_stock_unchanged(self, utr_cls):
        self._offer({"image_url": "https://cdn.example.com/a.jpg"})
        before_stock = self.product.available_stock_qty_cached

        GplProductImageService().sync_product_images(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(self.product.available_stock_qty_cached, before_stock)
        utr_cls.assert_not_called()
