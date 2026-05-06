from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment


class AutoDbConfirmProductLinkCommandTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="Brand", slug="brand-confirm-link", is_active=True)
        category = Category.objects.create(name="Category", slug="category-confirm-link", is_active=True)
        self.product = Product.objects.create(
            sku="ADB-CMD-1",
            article="ADB-CMD-1",
            slug="adb-cmd-1",
            name="Пильовик амортизатора",
            brand=brand,
            category=category,
            autodb_supplier_id=4674,
            autodb_article_number="TSHB-ACA2F",
            autodb_article_key="4674:TSHB-ACA2F",
            is_active=True,
        )
        ProductFitment.objects.create(
            product=self.product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=9001,
            linkage_type="PassengerCar",
            autodb_article_key="4674:TSHB-ACA2F",
            supplier_id=4674,
            article_number="TSHB-ACA2F",
        )

    def test_command_persists_manual_suspicious_status(self):
        out = StringIO()
        call_command(
            "autodb_confirm_product_link",
            "--product-id",
            str(self.product.id),
            "--status",
            "suspicious",
            "--reason",
            "suspicious_link",
            "--autodb-title",
            "Защитный колпак / пыльник",
            "--note",
            "wrong POLMO link",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("- status: suspicious", output)
        self.assertIn("- autodb_article_key: 4674:TSHB-ACA2F", output)
        self.assertIn("- manually_confirmed: True", output)
        self.assertIn("- excluded_from_public_filtering: True", output)
        quality = AutoDbProductLinkQuality.objects.get(product=self.product, autodb_article_key="4674:TSHB-ACA2F")
        self.assertEqual(quality.status, AutoDbProductLinkQuality.STATUS_SUSPICIOUS)
        self.assertTrue(quality.manually_confirmed)
        self.assertEqual(quality.reason, "suspicious_link")
        self.assertEqual(quality.evidence["autodb_title"], "Защитный колпак / пыльник")
        fitment = ProductFitment.objects.get(product=self.product, autodb_article_key="4674:TSHB-ACA2F")
        self.assertEqual(fitment.quality_reason, "suspicious_link")
        self.assertTrue(fitment.excluded_from_public_filtering)
