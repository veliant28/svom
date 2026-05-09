from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product


class AutoDbCategoryRepairCommandsTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="VW", slug="vw", is_active=True)
        self.manual_root = Category.objects.create(
            name="Тормозная система",
            slug="manual-brakes",
            source=Category.SOURCE_MANUAL,
            show_in_header=False,
            is_active=True,
        )
        self.autodb_a = Category.objects.create(
            name="Амортизатор",
            slug="autodb-prd-100-a",
            source=Category.SOURCE_AUTODB_PRO,
            autodb_prd_id=None,
            show_in_header=True,
            is_active=True,
        )
        self.autodb_b = Category.objects.create(
            name="  амортизатор  ",
            slug="autodb-prd-100-b",
            source=Category.SOURCE_AUTODB_PRO,
            autodb_prd_id=None,
            show_in_header=True,
            is_active=True,
        )
        self.product = Product.objects.create(
            sku="SKU-1",
            article="ART-1",
            name="Product",
            slug="product-1",
            brand=self.brand,
            category=self.autodb_b,
            is_active=True,
        )
        Product.objects.create(
            sku="SKU-2",
            article="ART-2",
            name="Product 2",
            slug="product-2",
            brand=self.brand,
            category=self.autodb_a,
            is_active=True,
        )

    def test_diagnose_command_outputs_summary_and_csv(self):
        with TemporaryDirectory() as tmp_dir:
            export_path = Path(tmp_dir) / "diagnose.csv"
            out = StringIO()

            call_command("diagnose_categories_autodb_duplicates", "--export-csv", str(export_path), stdout=out)

            content = out.getvalue()
            self.assertIn("total_count", content)
            self.assertIn("autodb_pro_count", content)
            self.assertIn("UTR calls: 0", content)
            self.assertTrue(export_path.exists())
            self.assertGreater(export_path.stat().st_size, 0)

    def test_repair_command_dry_run_keeps_data_unchanged(self):
        out = StringIO()
        call_command("repair_autodb_categories", "--dry-run", stdout=out)

        self.product.refresh_from_db()
        self.autodb_b.refresh_from_db()
        self.assertEqual(self.product.category_id, self.autodb_b.id)
        self.assertTrue(self.autodb_b.is_active)
        self.assertTrue(self.autodb_b.show_in_header)
        self.assertIn("dry_run: 1", out.getvalue())

    def test_repair_command_merges_duplicates_and_hides_autodb_nav(self):
        out = StringIO()
        call_command("repair_autodb_categories", stdout=out)

        self.product.refresh_from_db()
        self.autodb_a.refresh_from_db()
        self.autodb_b.refresh_from_db()
        self.manual_root.refresh_from_db()

        self.assertEqual(self.product.category_id, self.autodb_a.id)
        self.assertFalse(self.autodb_b.is_active)
        self.assertFalse(self.autodb_b.show_in_header)
        self.assertFalse(Category.objects.filter(source=Category.SOURCE_AUTODB_PRO, show_in_header=True).exists())
        self.assertTrue(self.manual_root.show_in_header)

        summary = out.getvalue()
        self.assertIn("categories_merged", summary)
        self.assertIn("products_reassigned: 1", summary)
        self.assertIn("deleted: 0", summary)
        self.assertIn("UTR calls: 0", summary)
