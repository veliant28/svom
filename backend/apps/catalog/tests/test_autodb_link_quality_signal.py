from django.test import TestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Product


class AutoDbLinkQualitySignalTests(TestCase):
    def setUp(self) -> None:
        self.brand = Brand.objects.create(name="SignalBrand", slug="signal-brand")

    def test_creates_trusted_quality_when_product_has_autodb_link(self):
        product = Product.objects.create(
            sku="SIG-LINK-1",
            name="Signal Product",
            slug="signal-product-1",
            brand=self.brand,
            autodb_supplier_id=324,
            autodb_article_number="WP9225",
            autodb_article_key="324:WP9225",
        )

        quality = AutoDbProductLinkQuality.objects.get(product=product, autodb_article_key="324:WP9225")
        self.assertEqual(quality.status, AutoDbProductLinkQuality.STATUS_TRUSTED)
        self.assertEqual(quality.autodb_supplier_id, 324)
        self.assertEqual(quality.autodb_article_number, "WP9225")

    def test_does_not_override_existing_quality_for_same_key(self):
        product = Product.objects.create(
            sku="SIG-LINK-2",
            name="Signal Product 2",
            slug="signal-product-2",
            brand=self.brand,
            autodb_supplier_id=324,
            autodb_article_number="WP9226",
            autodb_article_key="324:WP9226",
        )

        quality = AutoDbProductLinkQuality.objects.get(product=product, autodb_article_key="324:WP9226")
        quality.status = AutoDbProductLinkQuality.STATUS_SUSPICIOUS
        quality.reason = "manual_marked_suspicious"
        quality.save(update_fields=("status", "reason", "updated_at"))

        product.name = "Signal Product 2 updated"
        product.save(update_fields=("name", "updated_at"))

        rows = list(AutoDbProductLinkQuality.objects.filter(product=product, autodb_article_key="324:WP9226"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, AutoDbProductLinkQuality.STATUS_SUSPICIOUS)
