from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Category
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS


class SeedRootCategoriesCommandTests(TestCase):
    def test_seed_creates_expected_roots(self):
        out = StringIO()
        call_command("seed_root_categories", stdout=out)

        roots = list(Category.objects.filter(parent__isnull=True).order_by("sort_order", "name", "id"))
        self.assertEqual(len(roots), len(MANUAL_ROOT_CATEGORY_SPECS))
        self.assertEqual([item.slug for item in roots], [spec.slug for spec in MANUAL_ROOT_CATEGORY_SPECS])
        self.assertTrue(all(item.source == Category.SOURCE_MANUAL for item in roots))
        self.assertTrue(all(item.show_in_header for item in roots))
        self.assertTrue(all(item.is_active for item in roots))

    def test_seed_is_idempotent(self):
        call_command("seed_root_categories")
        before_count = Category.objects.count()
        out = StringIO()
        call_command("seed_root_categories", stdout=out)
        after_count = Category.objects.count()
        self.assertEqual(before_count, after_count)
        self.assertIn("created: 0", out.getvalue())

    def test_dry_run_does_not_write(self):
        before_count = Category.objects.count()
        out = StringIO()
        call_command("seed_root_categories", "--dry-run", stdout=out)
        after_count = Category.objects.count()
        self.assertEqual(before_count, after_count)
        self.assertIn("simulated_only: 1", out.getvalue())
