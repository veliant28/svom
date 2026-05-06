from __future__ import annotations

from django.test import TestCase

from apps.autodb.services.fitment_quality import AutoDbProductLinkQualityService, can_use_autodb_fitments_for_public_filtering
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment


class AutoDbProductLinkQualityServiceTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand-link-quality", is_active=True)
        self.category = Category.objects.create(name="Category", slug="category-link-quality", is_active=True)
        self.product = Product.objects.create(
            sku="ADB-LINK-1",
            article="ADB-LINK-1",
            slug="adb-link-1",
            name="Амортизатор передній",
            name_uk="Амортизатор передній",
            name_ru="Амортизатор передний",
            name_en="Front shock absorber",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=324,
            autodb_article_number="92131E",
            autodb_article_key="324:92131E",
            is_active=True,
        )
        ProductFitment.objects.create(
            product=self.product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=4001,
            linkage_type="PassengerCar",
            autodb_article_key="324:92131E",
            supplier_id=324,
            article_number="92131E",
            is_stale=False,
        )
        self.service = AutoDbProductLinkQualityService()

    def test_trusted_product_remains_usable_in_helper(self):
        self.service.persist_audit_result(
            product=self.product,
            suspicious_flags=(),
            suspicious_reason="",
            evidence={"suspicious_flags": []},
        )

        self.assertTrue(can_use_autodb_fitments_for_public_filtering(product=self.product))
        fitment = ProductFitment.objects.get(product=self.product)
        self.assertEqual(fitment.quality_status, ProductFitment.QUALITY_STATUS_TRUSTED)
        self.assertFalse(fitment.excluded_from_public_filtering)

    def test_manual_suspicious_always_excludes_product(self):
        self.service.confirm_manual_status(
            product=self.product,
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            note="wrong POLMO link",
        )

        self.assertFalse(can_use_autodb_fitments_for_public_filtering(product=self.product))
        fitment = ProductFitment.objects.get(product=self.product)
        self.assertEqual(fitment.quality_status, ProductFitment.QUALITY_STATUS_SUSPICIOUS)
        self.assertTrue(fitment.excluded_from_public_filtering)

    def test_manual_trusted_preserves_priority_over_later_auto_suspicious(self):
        self.service.confirm_manual_status(
            product=self.product,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            note="checked manually",
        )
        self.service.persist_audit_result(
            product=self.product,
            suspicious_flags=("suspicious_link",),
            suspicious_reason="product_name_vs_autodb_conflict",
            evidence={"suspicious_flags": ["suspicious_link"]},
        )

        quality = AutoDbProductLinkQuality.objects.get(product=self.product, autodb_article_key="324:92131E")
        self.assertEqual(quality.status, AutoDbProductLinkQuality.STATUS_TRUSTED)
        self.assertTrue(quality.manually_confirmed)
        self.assertTrue(can_use_autodb_fitments_for_public_filtering(product=self.product))
        fitment = ProductFitment.objects.get(product=self.product)
        self.assertEqual(fitment.quality_status, ProductFitment.QUALITY_STATUS_TRUSTED)
        self.assertFalse(fitment.excluded_from_public_filtering)
