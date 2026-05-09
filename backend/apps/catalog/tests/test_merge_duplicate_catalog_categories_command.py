from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import AutoDbPrdCategoryMap, Brand, Category, Product


class MergeDuplicateCatalogCategoriesCommandTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="EXIDE", slug="exide", is_active=True)

        self.root_electric = Category.objects.create(
            name="Электрика и освещение",
            slug="elektrika-i-osveshchenie",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
        )
        self.root_suspension = Category.objects.create(
            name="Подвеска и рулевое",
            slug="podveska-i-rulevoe",
            source=Category.SOURCE_MANUAL,
            show_in_header=True,
            is_active=True,
        )

        self.canonical_battery = Category.objects.create(
            name="Аккумуляторы",
            name_uk="Акумулятори",
            name_ru="Аккумуляторы",
            name_en="Batteries",
            slug="akkumuliatory",
            source=Category.SOURCE_MANUAL,
            parent=self.root_electric,
            show_in_header=False,
            is_active=True,
        )
        self.duplicate_battery = Category.objects.create(
            name="Аккумулятор",
            name_uk="Акумулятор",
            name_ru="Аккумулятор",
            name_en="Accumulator",
            slug="autodb-prd-1",
            source=Category.SOURCE_AUTODB_PRO,
            autodb_prd_id=1,
            parent=self.root_electric,
            show_in_header=False,
            is_active=True,
        )

        self.canonical_shock = Category.objects.create(
            name="Амортизаторы",
            name_uk="Амортизатори",
            name_ru="Амортизаторы",
            name_en="Shock absorbers",
            slug="amortizatory",
            source=Category.SOURCE_MANUAL,
            parent=self.root_suspension,
            show_in_header=False,
            is_active=True,
        )
        self.duplicate_shock = Category.objects.create(
            name="Амортизатор",
            name_uk="Амортизатор",
            name_ru="Амортизатор",
            name_en="Shock absorber",
            slug="autodb-prd-854",
            source=Category.SOURCE_AUTODB_PRO,
            autodb_prd_id=854,
            parent=self.root_suspension,
            show_in_header=False,
            is_active=True,
        )

        self.product_battery = Product.objects.create(
            sku="SKU-BAT-1",
            article="BAT-1",
            name="EXIDE EB620",
            slug="exide-eb620",
            brand=self.brand,
            category=self.duplicate_battery,
            is_active=True,
        )
        self.product_shock = Product.objects.create(
            sku="SKU-SHOCK-1",
            article="SHOCK-1",
            name="AUTOMEGA SHOCK",
            slug="automega-shock",
            brand=self.brand,
            category=self.duplicate_shock,
            is_active=True,
        )

        AutoDbPrdCategoryMap.objects.create(prd_id=1, prd_name="Аккумулятор", category=self.duplicate_battery)
        AutoDbPrdCategoryMap.objects.create(prd_id=854, prd_name="Амортизатор", category=self.duplicate_shock)

    def test_merge_dry_run_is_read_only(self):
        out = StringIO()
        call_command(
            "merge_duplicate_catalog_categories",
            "--pairs",
            "Аккумулятор=>Аккумуляторы,Амортизатор=>Амортизаторы",
            "--dry-run",
            stdout=out,
        )

        self.product_battery.refresh_from_db()
        self.product_shock.refresh_from_db()
        self.duplicate_battery.refresh_from_db()
        self.duplicate_shock.refresh_from_db()
        self.canonical_battery.refresh_from_db()
        self.canonical_shock.refresh_from_db()

        self.assertEqual(self.product_battery.category_id, self.duplicate_battery.id)
        self.assertEqual(self.product_shock.category_id, self.duplicate_shock.id)
        self.assertEqual(self.duplicate_battery.autodb_prd_id, 1)
        self.assertEqual(self.duplicate_shock.autodb_prd_id, 854)
        self.assertEqual(self.canonical_battery.autodb_prd_id, None)
        self.assertEqual(self.canonical_shock.autodb_prd_id, None)

        text = out.getvalue()
        self.assertIn("- dry_run: 1", text)
        self.assertIn("- UTR calls=0", text)
        self.assertIn("- price/stock changed=0", text)

    def test_merge_real_moves_products_and_preserves_autodb_ids(self):
        out = StringIO()
        call_command(
            "merge_duplicate_catalog_categories",
            "--pairs",
            "Аккумулятор=>Аккумуляторы,Амортизатор=>Амортизаторы",
            stdout=out,
        )

        self.product_battery.refresh_from_db()
        self.product_shock.refresh_from_db()
        self.duplicate_battery.refresh_from_db()
        self.duplicate_shock.refresh_from_db()
        self.canonical_battery.refresh_from_db()
        self.canonical_shock.refresh_from_db()

        self.assertEqual(self.product_battery.category_id, self.canonical_battery.id)
        self.assertEqual(self.product_shock.category_id, self.canonical_shock.id)
        self.assertEqual(self.canonical_battery.autodb_prd_id, 1)
        self.assertEqual(self.canonical_shock.autodb_prd_id, 854)
        self.assertIsNone(self.duplicate_battery.autodb_prd_id)
        self.assertIsNone(self.duplicate_shock.autodb_prd_id)
        self.assertFalse(self.duplicate_battery.is_active)
        self.assertFalse(self.duplicate_shock.is_active)
        self.assertNotEqual(self.duplicate_battery.slug, "autodb-prd-1")
        self.assertNotEqual(self.duplicate_shock.slug, "autodb-prd-854")

        self.assertEqual(
            AutoDbPrdCategoryMap.objects.get(prd_id=1).category_id,
            self.canonical_battery.id,
        )
        self.assertEqual(
            AutoDbPrdCategoryMap.objects.get(prd_id=854).category_id,
            self.canonical_shock.id,
        )

        text = out.getvalue()
        self.assertIn("- products_moved: 2", text)
        self.assertIn("- maps_repointed: 2", text)
        self.assertIn("- duplicates_remaining: 0", text)

        repeat = StringIO()
        call_command(
            "merge_duplicate_catalog_categories",
            "--pairs",
            "Аккумулятор=>Аккумуляторы,Амортизатор=>Амортизаторы",
            "--dry-run",
            stdout=repeat,
        )
        self.assertIn("- products_to_move: 0", repeat.getvalue())
        self.assertIn("- duplicates_remaining: 0", repeat.getvalue())
