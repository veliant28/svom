from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Category
from apps.catalog.services.manual_chemical_categories import (
    MANUAL_CHEMICAL_CATEGORY_SPECS,
    MANUAL_CHEMICAL_ROOT_SLUG,
)
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS


class SeedManualChemicalCategoriesCommandTests(TestCase):
    def setUp(self):
        call_command("seed_root_categories")

    def test_seed_dry_run_and_real_and_repeat_are_idempotent(self):
        root_count_before = Category.objects.filter(parent__isnull=True).count()
        self.assertEqual(root_count_before, len(MANUAL_ROOT_CATEGORY_SPECS))

        dry_out = StringIO()
        call_command("seed_manual_chemical_categories", "--dry-run", stdout=dry_out)
        self.assertIn("- dry_run: 1", dry_out.getvalue())

        out = StringIO()
        call_command("seed_manual_chemical_categories", stdout=out)
        text = out.getvalue()
        self.assertIn("- parent category found: 1", text)
        self.assertIn("- UTR calls=0", text)

        parent = Category.objects.get(slug=MANUAL_CHEMICAL_ROOT_SLUG, parent__isnull=True)
        children = list(Category.objects.filter(parent=parent).order_by("sort_order", "name", "id"))
        self.assertEqual(len(children), len(MANUAL_CHEMICAL_CATEGORY_SPECS))
        self.assertEqual([item.slug for item in children], [spec.slug for spec in MANUAL_CHEMICAL_CATEGORY_SPECS])
        self.assertTrue(all(item.source == Category.SOURCE_MANUAL for item in children))
        self.assertTrue(all(item.show_in_header is False for item in children))
        self.assertTrue(all(item.is_active for item in children))

        repeat_out = StringIO()
        call_command("seed_manual_chemical_categories", stdout=repeat_out)
        self.assertIn("- created: 0", repeat_out.getvalue())

        root_count_after = Category.objects.filter(parent__isnull=True).count()
        self.assertEqual(root_count_after, len(MANUAL_ROOT_CATEGORY_SPECS))
        self.assertEqual(Category.objects.filter(parent__isnull=True, source=Category.SOURCE_AUTODB_PRO).count(), 0)
