from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category, CategoryNavigationCollection, CategoryNavigationItem
from apps.catalog.services.taxonomy_v2 import TO_COLLECTION_SPEC, count_duplicate_category_names_same_parent


class SeedCatalogTaxonomyV2CommandTests(TestCase):
    def test_dry_run_is_read_only(self):
        out = StringIO()

        call_command("seed_catalog_taxonomy_v2", "--dry-run", stdout=out)

        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(CategoryNavigationCollection.objects.count(), 0)
        self.assertIn("dry_run=True", out.getvalue())
        self.assertIn("UTR calls: 0", out.getvalue())

    def test_seed_is_idempotent_and_sets_assignability(self):
        first = StringIO()
        call_command("seed_catalog_taxonomy_v2", stdout=first)

        roots = Category.objects.filter(parent__isnull=True, show_in_header=True).order_by("sort_order")
        self.assertEqual(roots.count(), 10)
        self.assertEqual(roots.filter(is_assignable=False).count(), 10)
        self.assertFalse(Category.objects.filter(parent__isnull=False, children__isnull=False, is_assignable=True).exists())
        self.assertTrue(Category.objects.filter(is_assignable=True, name="Амортизаторы").exists())
        self.assertTrue(Category.objects.filter(is_assignable=True, name="Аккумуляторы").exists())
        self.assertTrue(Category.objects.filter(parent__isnull=True, slug="kolesa-i-shiny", is_assignable=False, show_in_header=True).exists())
        self.assertTrue(Category.objects.filter(slug="zimnie-shiny", is_assignable=True, is_active=True).exists())
        self.assertTrue(Category.objects.filter(slug="letnie-shiny", is_assignable=True, is_active=True).exists())
        self.assertFalse(Category.objects.filter(slug="kolesa-i-shiny-shiny", is_assignable=True).exists())
        self.assertEqual(count_duplicate_category_names_same_parent(), 0)

        repeat = StringIO()
        call_command("seed_catalog_taxonomy_v2", stdout=repeat)
        output = repeat.getvalue()

        self.assertIn("roots_created: 0", output)
        self.assertIn("menu_groups_created: 0", output)
        self.assertIn("leaf_categories_created: 0", output)
        self.assertIn("navigation_links_created: 0", output)
        self.assertIn("duplicate_names: 0", output)
        self.assertIn("duplicate_slugs: 0", output)
        self.assertIn("invalid_assignable_parents: 0", output)

    def test_to_collection_references_existing_leaf_categories_only(self):
        call_command("seed_catalog_taxonomy_v2", stdout=StringIO())

        collection = CategoryNavigationCollection.objects.get(slug=TO_COLLECTION_SPEC.slug)
        self.assertEqual(collection.root_category.slug, "zapchasti-dlia-to")
        self.assertFalse(collection.root_category.is_assignable)
        self.assertFalse(Category.objects.filter(parent=collection.root_category).exists())

        items = CategoryNavigationItem.objects.select_related("category", "group").filter(group__collection=collection)
        self.assertGreater(items.count(), 0)
        self.assertFalse(items.filter(category__is_assignable=False).exists())
        self.assertFalse(items.filter(category__parent=collection.root_category).exists())


class HeaderNavigationApiTests(APITestCase):
    def test_header_navigation_uses_to_collection_without_duplicate_category_tree(self):
        call_command("seed_catalog_taxonomy_v2", stdout=StringIO())

        response = self.client.get(reverse("catalog_api:header-navigation"), {"locale": "ru"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)
        roots = {item["slug"]: item for item in response.data}
        self.assertIn("zapchasti-dlia-to", roots)
        self.assertIn("kolesa-i-shiny", roots)
        to_root = roots["zapchasti-dlia-to"]
        self.assertGreater(len(to_root["sections"]), 0)
        first_section = to_root["sections"][0]
        self.assertEqual(first_section["title"], "Электрика")
        self.assertTrue(all(item.get("is_assignable") is True for item in first_section["items"]))

        zapchasti_root = Category.objects.get(slug="zapchasti-dlia-to")
        self.assertFalse(Category.objects.filter(parent=zapchasti_root).exists())
