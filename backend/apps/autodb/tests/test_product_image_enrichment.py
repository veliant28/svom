from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.autodb.services.product_image_enrichment import AutoDbProductImageEnrichmentService
from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbProductImageEnrichmentServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.category = Category.objects.create(name="Category", slug="category", is_active=True)
        self.product = Product.objects.create(
            sku="IMG-AUTO-1",
            slug="img-auto-1",
            name="Auto image product",
            article="A-1",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=300,
            autodb_article_number="820099",
            autodb_article_key="300:820099",
            available_stock_qty_cached=9,
            is_active=True,
        )

    def _service(self) -> AutoDbProductImageEnrichmentService:
        return AutoDbProductImageEnrichmentService()

    def test_autodb_image_created_for_linked_non_gpl(self):
        service = self._service()
        rows = [{"supplierId": 300, "DataSupplierArticleNumber": "820099", "TecdocHyperlinkName": "https://autodb.example.com/a.jpg"}]
        with patch.object(service, "_find_article_images_rows", return_value=rows):
            result = service.sync_product_images(product=self.product, dry_run=False)

        image = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_AUTODB_PRO)
        self.assertTrue(result.has_candidates)
        self.assertEqual(result.created, 1)
        self.assertEqual(image.remote_url, "https://autodb.example.com/a.jpg")
        self.assertTrue(image.is_primary)

    def test_autodb_used_as_gpl_fallback_when_no_gpl_images(self):
        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="/tmp/gpl.json",
            is_active=True,
        )
        run = ImportRun.objects.create(source=source, status=ImportRun.STATUS_SUCCESS, trigger="test")
        SupplierRawOffer.objects.create(
            run=run,
            source=source,
            supplier=supplier,
            external_sku="SKU-1",
            article="A-1",
            normalized_article="A1",
            brand_name="Brand",
            normalized_brand="brand",
            product_name="Auto image product",
            matched_product=self.product,
            raw_payload={"name": "x"},
        )

        service = self._service()
        rows = [{"supplierId": 300, "DataSupplierArticleNumber": "820099", "TecdocHyperlinkName": "https://autodb.example.com/a.jpg"}]
        with patch.object(service, "_find_article_images_rows", return_value=rows):
            service.sync_product_images(product=self.product, dry_run=False, prefer_gpl=True)

        image = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_AUTODB_PRO)
        self.assertTrue(image.is_primary)

    def test_autodb_does_not_override_gpl_primary(self):
        ProductImage.objects.create(
            product=self.product,
            image=None,
            remote_url="https://gpl.example.com/a.jpg",
            source=ProductImage.SOURCE_GPL_PRICE,
            is_primary=True,
            sort_order=0,
        )
        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="/tmp/gpl.json",
            is_active=True,
        )
        run = ImportRun.objects.create(source=source, status=ImportRun.STATUS_SUCCESS, trigger="test")
        SupplierRawOffer.objects.create(
            run=run,
            source=source,
            supplier=supplier,
            external_sku="SKU-1",
            article="A-1",
            normalized_article="A1",
            brand_name="Brand",
            normalized_brand="brand",
            product_name="Auto image product",
            matched_product=self.product,
            raw_payload={"image_url": "https://gpl.example.com/a.jpg"},
        )

        service = self._service()
        rows = [{"supplierId": 300, "DataSupplierArticleNumber": "820099", "TecdocHyperlinkName": "https://autodb.example.com/a.jpg"}]
        with patch.object(service, "_find_article_images_rows", return_value=rows):
            result = service.sync_product_images(product=self.product, dry_run=False, prefer_gpl=True)

        gpl = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_GPL_PRICE)
        autodb = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_AUTODB_PRO)
        self.assertTrue(result.skipped_manual_primary)
        self.assertTrue(gpl.is_primary)
        self.assertFalse(autodb.is_primary)

    def test_autodb_primary_overrides_non_manual_primary(self):
        ProductImage.objects.create(
            product=self.product,
            image=None,
            remote_url="https://legacy.example.com/main.jpg",
            source=ProductImage.SOURCE_IMPORTED,
            is_primary=True,
            sort_order=0,
        )

        service = self._service()
        rows = [{"supplierId": 300, "DataSupplierArticleNumber": "820099", "TecdocHyperlinkName": "https://autodb.example.com/a.jpg"}]
        with patch.object(service, "_find_article_images_rows", return_value=rows):
            service.sync_product_images(product=self.product, dry_run=False, prefer_gpl=True)

        imported = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_IMPORTED)
        autodb = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_AUTODB_PRO)
        self.assertFalse(imported.is_primary)
        self.assertTrue(autodb.is_primary)

    @override_settings(AUTODB_PRO_IMAGE_BASE_URL="", AUTODB_IMAGE_BASE_URL="")
    def test_pending_reference_saved_when_url_not_resolved(self):
        service = self._service()
        rows = [{"supplierId": 300, "DataSupplierArticleNumber": "820099", "FileName": "images/a.jpg"}]
        with patch.object(service, "_find_article_images_rows", return_value=rows):
            service.sync_product_images(product=self.product, dry_run=False)

        image = ProductImage.objects.get(product=self.product, source=ProductImage.SOURCE_AUTODB_PRO)
        self.assertEqual(image.remote_url, "")
        self.assertTrue(bool(image.source_payload.get("pending_url_resolution")))

    def test_repeated_run_no_duplicates(self):
        service = self._service()
        rows = [{"supplierId": 300, "DataSupplierArticleNumber": "820099", "TecdocHyperlinkName": "https://autodb.example.com/a.jpg"}]
        with patch.object(service, "_find_article_images_rows", return_value=rows):
            first = service.sync_product_images(product=self.product, dry_run=False)
            second = service.sync_product_images(product=self.product, dry_run=False)

        self.assertEqual(first.created, 1)
        self.assertEqual(second.created, 0)
        self.assertEqual(ProductImage.objects.filter(product=self.product, source=ProductImage.SOURCE_AUTODB_PRO).count(), 1)

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_utr_not_called_and_price_stock_unchanged(self, utr_cls):
        service = self._service()
        before_stock = self.product.available_stock_qty_cached
        rows = [{"supplierId": 300, "DataSupplierArticleNumber": "820099", "TecdocHyperlinkName": "https://autodb.example.com/a.jpg"}]
        with patch.object(service, "_find_article_images_rows", return_value=rows):
            service.sync_product_images(product=self.product, dry_run=False)

        self.product.refresh_from_db()
        self.assertEqual(self.product.available_stock_qty_cached, before_stock)
        utr_cls.assert_not_called()
