from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS
from apps.pricing.models import PricingPolicy


class ResetCategoriesToManualRootsCommandTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand", is_active=True)
        self.manual_root = Category.objects.create(
            name="Old Root",
            slug="old-root",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
        )
        self.autodb_root = Category.objects.create(
            name="Амортизатор",
            slug="autodb-prd-854",
            source=Category.SOURCE_AUTODB_PRO,
            autodb_prd_id=854,
            show_in_header=False,
            is_active=True,
        )
        self.product = Product.objects.create(
            sku="SKU-1",
            article="ART-1",
            name="Product 1",
            slug="product-1",
            brand=self.brand,
            category=self.autodb_root,
            is_active=True,
        )
        PricingPolicy.objects.create(
            name="Category Policy",
            scope=PricingPolicy.SCOPE_CATEGORY,
            category=self.manual_root,
            percent_markup="10.00",
        )

    def test_dry_run_does_not_change_data(self):
        before_categories = Category.objects.count()
        before_product_category_id = self.product.category_id
        out = StringIO()

        with TemporaryDirectory() as tmp_dir:
            categories_csv = str(Path(tmp_dir) / "categories_before_reset.csv")
            assignments_csv = str(Path(tmp_dir) / "product_category_assignments_before_reset.csv")
            call_command(
                "reset_categories_to_manual_roots",
                "--dry-run",
                "--categories-backup",
                categories_csv,
                "--product-assignments-backup",
                assignments_csv,
                stdout=out,
            )
            self.assertTrue(Path(categories_csv).exists())
            self.assertTrue(Path(assignments_csv).exists())

        self.product.refresh_from_db()
        self.assertEqual(Category.objects.count(), before_categories)
        self.assertEqual(self.product.category_id, before_product_category_id)
        self.assertIn("dry_run: 1", out.getvalue())

    def test_real_reset_recreates_only_manual_roots_and_unassigns_products(self):
        out = StringIO()
        with TemporaryDirectory() as tmp_dir:
            categories_csv = str(Path(tmp_dir) / "categories_before_reset.csv")
            assignments_csv = str(Path(tmp_dir) / "product_category_assignments_before_reset.csv")
            call_command(
                "reset_categories_to_manual_roots",
                "--categories-backup",
                categories_csv,
                "--product-assignments-backup",
                assignments_csv,
                stdout=out,
            )

            self.assertTrue(Path(categories_csv).exists())
            self.assertTrue(Path(assignments_csv).exists())

        self.product.refresh_from_db()
        self.assertIsNone(self.product.category_id)
        roots = list(Category.objects.filter(parent__isnull=True).order_by("slug"))
        self.assertEqual(len(roots), len(MANUAL_ROOT_CATEGORY_SPECS))
        self.assertEqual({item.slug for item in roots}, {item.slug for item in MANUAL_ROOT_CATEGORY_SPECS})
        self.assertTrue(all(item.source == Category.SOURCE_MANUAL for item in roots))
        self.assertTrue(all(item.show_in_header for item in roots))
        self.assertFalse(Category.objects.filter(source=Category.SOURCE_AUTODB_PRO).exists())
        self.assertEqual(Product.objects.exclude(category__isnull=True).count(), 0)
        self.assertIn("UTR calls=0", out.getvalue())

