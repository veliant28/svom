from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Category


class SeedManualOilFluidCategoriesCommandTests(TestCase):
    def setUp(self):
        call_command("seed_root_categories")

    def test_seed_is_idempotent(self):
        dry_out = StringIO()
        call_command("seed_manual_oil_fluid_categories", "--dry-run", stdout=dry_out)
        dry_text = dry_out.getvalue()
        self.assertIn("- created: 6", dry_text)
        self.assertEqual(Category.objects.filter(slug__in=self._target_slugs()).count(), 0)

        out = StringIO()
        call_command("seed_manual_oil_fluid_categories", stdout=out)
        text = out.getvalue()
        self.assertIn("- created: 6", text)
        self.assertIn("- duplicate slugs: 0", text)
        self.assertIn("- duplicate names: 0", text)
        self.assertIn("- root categories created: 0", text)

        created = list(Category.objects.filter(slug__in=self._target_slugs()).select_related("parent").order_by("slug"))
        self.assertEqual(len(created), 6)
        self.assertTrue(all(item.parent and item.parent.slug == "to-i-raskhodniki" for item in created))
        self.assertTrue(all(item.source == Category.SOURCE_MANUAL for item in created))
        self.assertTrue(all(item.show_in_header is False for item in created))
        self.assertTrue(all(item.is_active is True for item in created))

        repeat_out = StringIO()
        call_command("seed_manual_oil_fluid_categories", stdout=repeat_out)
        repeat_text = repeat_out.getvalue()
        self.assertIn("- created: 0", repeat_text)
        self.assertIn("- updated: 0", repeat_text)
        self.assertIn("- unchanged: 6", repeat_text)

    def _target_slugs(self) -> tuple[str, ...]:
        return (
            "motornye-masla",
            "transmissionnye-masla",
            "gidravlicheskie-masla",
            "tekhnicheskie-zhidkosti",
            "antifrizy-i-okhlazhdaiushchie-zhidkosti",
            "tormoznye-zhidkosti",
        )
