from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category
from apps.catalog.selectors import get_active_categories_queryset
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS


class CategoryNavigationScopeTests(APITestCase):
    def test_header_scope_includes_active_descendants_of_visible_root(self):
        root = Category.objects.create(
            name="Тормозная система",
            slug="curated-brakes",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
            sort_order=10,
        )
        child = Category.objects.create(
            name="Колодки",
            slug="brake-pads",
            source=Category.SOURCE_MANUAL,
            parent=root,
            show_in_header=False,
            is_active=True,
            sort_order=20,
        )
        Category.objects.create(
            name="Передние",
            slug="brake-pads-front",
            source=Category.SOURCE_MANUAL,
            parent=child,
            show_in_header=False,
            is_active=True,
            sort_order=30,
        )
        Category.objects.create(
            name="Амортизатор",
            slug="autodb-shock-child",
            source=Category.SOURCE_AUTODB_PRO,
            parent=root,
            show_in_header=False,
            is_active=True,
            sort_order=25,
        )

        response = self.client.get(reverse("catalog_api:category-list"), {"scope": "header"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        labels = [item["name"] for item in response.data]
        self.assertIn("Тормозная система", labels)
        self.assertIn("Колодки", labels)
        self.assertIn("Передние", labels)
        self.assertIn("Амортизатор", labels)

    def test_header_scope_returns_curated_roots_in_order(self):
        for spec in MANUAL_ROOT_CATEGORY_SPECS:
            Category.objects.create(
                name=spec.name,
                name_uk=spec.name_uk,
                name_ru=spec.name_ru,
                name_en=spec.name_en,
                slug=spec.slug,
                source=Category.SOURCE_MANUAL,
                show_in_header=True,
                is_active=True,
                sort_order=spec.sort_order,
            )
        # Should never leak to header even if active+show_in_header.
        Category.objects.create(
            name="Амортизатор",
            slug="autodb-shock",
            source=Category.SOURCE_AUTODB_PRO,
            show_in_header=True,
            is_active=True,
            sort_order=1,
        )

        response = self.client.get(reverse("catalog_api:category-list"), {"scope": "header"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(MANUAL_ROOT_CATEGORY_SPECS))
        self.assertEqual([row["slug"] for row in response.data], [item.slug for item in MANUAL_ROOT_CATEGORY_SPECS])

    def test_header_scope_shows_only_manual_roots(self):
        curated = Category.objects.create(
            name="Тормозная система",
            slug="curated-brakes",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
            sort_order=30,
        )
        Category.objects.create(
            name="Амортизатор",
            slug="autodb-shock",
            source=Category.SOURCE_AUTODB_PRO,
            show_in_header=True,
            is_active=True,
            sort_order=1,
        )
        Category.objects.create(
            name="Газовая пружина",
            slug="autodb-gas",
            source=Category.SOURCE_AUTODB_PRO,
            show_in_header=True,
            is_active=True,
            sort_order=2,
        )

        response = self.client.get(reverse("catalog_api:category-list"), {"scope": "header"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data]
        self.assertIn(curated.name, names)
        self.assertNotIn("Амортизатор", names)
        self.assertNotIn("Газовая пружина", names)

    def test_header_scope_limits_and_deduplicates_roots(self):
        # Create more than the hard cap and duplicate labels to verify dedupe + limit.
        for index in range(1, 15):
            Category.objects.create(
                name=f"Категория {index}",
                slug=f"manual-root-{index}",
                source=Category.SOURCE_MANUAL,
                show_in_header=True,
                is_active=True,
                sort_order=index,
            )
        Category.objects.create(
            name="Амортизатор",
            slug="manual-shock-a",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
            sort_order=100,
        )
        Category.objects.create(
            name="  Амортизатор  ",
            slug="manual-shock-b",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
            sort_order=101,
        )

        queryset = get_active_categories_queryset(scope="header")
        roots = [item for item in queryset if item.parent_id is None]
        normalized = {" ".join(item.name.split()).casefold() for item in roots}

        self.assertLessEqual(len(roots), 10)
        self.assertEqual(len(roots), len(normalized))
