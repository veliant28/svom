from __future__ import annotations

from django.test import TestCase

from apps.catalog.models import Category
from apps.catalog.services import find_semantic_category_under_parent, resolve_canonical_spec_for_name


class CategoryCanonicalizationTests(TestCase):
    def test_resolve_canonical_spec_for_aliases(self):
        battery = resolve_canonical_spec_for_name("Аккумулятор")
        self.assertIsNotNone(battery)
        assert battery is not None
        self.assertEqual(battery.canonical_slug, "akkumuliatory")

        shock = resolve_canonical_spec_for_name("shock absorber")
        self.assertIsNotNone(shock)
        assert shock is not None
        self.assertEqual(shock.canonical_slug, "amortizatory")

        aliases = {
            "Масло моторное": "motornoe-maslo",
            "Фильтр воздушный": "vozdushnyi-filtr",
            "Фильтр масляный": "maslianyi-filtr",
            "Фильтр топливный": "toplivnyi-filtr",
            "Салонный фильтр": "filtr-salona",
            "Глушники": "glushitel",
            "Гальмівні колодки": "tormoznye-kolodki",
        }
        for raw_name, slug in aliases.items():
            with self.subTest(raw_name=raw_name):
                resolved = resolve_canonical_spec_for_name(raw_name)
                self.assertIsNotNone(resolved)
                assert resolved is not None
                self.assertEqual(resolved.canonical_slug, slug)

    def test_find_semantic_category_under_parent_reuses_plural_for_singular_alias(self):
        parent = Category.objects.create(
            name="Электрика и освещение",
            slug="elektrika-i-osveshchenie",
            source=Category.SOURCE_MANUAL,
            is_active=True,
        )
        canonical = Category.objects.create(
            parent=parent,
            name="Аккумуляторы",
            name_uk="Акумулятори",
            name_ru="Аккумуляторы",
            name_en="Batteries",
            slug="akkumuliatory",
            source=Category.SOURCE_MANUAL,
            is_active=True,
        )

        resolved = find_semantic_category_under_parent(parent=parent, name="Аккумулятор", include_inactive=True)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.id, canonical.id)
