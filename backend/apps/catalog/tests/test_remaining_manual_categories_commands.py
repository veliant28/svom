from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS
from apps.catalog.services.manual_remaining_categories import REMAINING_MANUAL_CATEGORY_SPECS
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class RemainingManualCategoriesCommandsTests(TestCase):
    def setUp(self):
        call_command("seed_root_categories")
        call_command("seed_manual_chemical_categories")

        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test")

        self.brand_dainton = Brand.objects.create(name="DAINTON", slug="dainton", is_active=True)
        self.brand_hagen = Brand.objects.create(name="HAGEN BATTERIE", slug="hagen-batterie", is_active=True)
        self.brand_misc = Brand.objects.create(name="MISC", slug="misc", is_active=True)

        self.p_shock = Product.objects.create(
            sku="GPL-R-1",
            article="D181007",
            name="Амортизатор DAINTON D181007",
            slug="dainton-d181007",
            brand=self.brand_dainton,
            category=None,
            normalized_brand="DAINTON",
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        self._raw_offer(
            self.p_shock,
            brand_name="DAINTON",
            payload={"Найменування": "Амортизатор DAINTON D181007", "Опис": "стойка"},
        )

        self.p_battery = Product.objects.create(
            sku="GPL-R-2",
            article="HB74",
            name="Акумулятор HAGEN BATTERIE 74Ah",
            slug="hagen-batterie-74",
            brand=self.brand_hagen,
            category=None,
            normalized_brand="HAGENBATTERIE",
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        self._raw_offer(
            self.p_battery,
            brand_name="HAGEN BATTERIE",
            payload={"Найменування": "Акумулятор 74Ah", "Опис": "battery"},
        )

        self.p_unclear = Product.objects.create(
            sku="GPL-R-3",
            article="MX01",
            name="Набір MIX",
            slug="mix-01",
            brand=self.brand_misc,
            category=None,
            normalized_brand="MISC",
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        self._raw_offer(
            self.p_unclear,
            brand_name="MISC",
            payload={"Найменування": "Набір MIX", "Опис": "misc"},
        )

    def _raw_offer(self, product: Product, *, brand_name: str, payload: dict):
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=1,
            external_sku=f"{product.sku}-EXT",
            article=product.article,
            normalized_article=product.article,
            brand_name=brand_name,
            normalized_brand=brand_name,
            product_name=product.name,
            price="100.00",
            stock_qty=5,
            lead_time_days=1,
            matched_product=product,
            is_valid=True,
            raw_payload=payload,
        )

    def test_seed_remaining_manual_categories_is_idempotent(self):
        root_count_before = Category.objects.filter(parent__isnull=True).count()
        self.assertEqual(root_count_before, len(MANUAL_ROOT_CATEGORY_SPECS))

        dry_out = StringIO()
        call_command("seed_remaining_manual_categories", "--dry-run", stdout=dry_out)
        self.assertIn("- dry_run: 1", dry_out.getvalue())

        out = StringIO()
        call_command("seed_remaining_manual_categories", stdout=out)
        self.assertIn("- UTR calls=0", out.getvalue())

        repeat = StringIO()
        call_command("seed_remaining_manual_categories", stdout=repeat)
        self.assertIn("- created: 0", repeat.getvalue())

        roots_after = Category.objects.filter(parent__isnull=True).count()
        self.assertEqual(roots_after, len(MANUAL_ROOT_CATEGORY_SPECS))

        slugs = [item.slug for item in REMAINING_MANUAL_CATEGORY_SPECS]
        self.assertEqual(Category.objects.filter(slug__in=slugs, source=Category.SOURCE_MANUAL).count(), len(slugs))

    def test_seed_remaining_reuses_semantic_existing_singular_category(self):
        root = Category.objects.get(slug="elektrika-i-osveshchenie", parent__isnull=True)
        existing = Category.objects.create(
            parent=root,
            name="Аккумулятор",
            name_uk="Акумулятор",
            name_ru="Аккумулятор",
            name_en="Accumulator",
            slug="autodb-prd-1",
            source=Category.SOURCE_AUTODB_PRO,
            autodb_prd_id=1,
            is_active=True,
            show_in_header=False,
        )

        call_command("seed_remaining_manual_categories")

        existing.refresh_from_db()
        self.assertEqual(existing.slug, "akkumuliatory")
        self.assertEqual(existing.name_ru, "Аккумуляторы")
        self.assertEqual(existing.parent.slug, "elektrika-i-osveshchenie")
        self.assertEqual(
            Category.objects.filter(parent=root, name__in=["Аккумулятор", "Аккумуляторы"]).count(),
            1,
        )

    def test_assign_remaining_dry_run_real_repeat(self):
        call_command("seed_remaining_manual_categories")

        dry_out = StringIO()
        call_command(
            "assign_remaining_manual_categories",
            "--supplier",
            "GPL",
            "--limit",
            "10",
            "--dry-run",
            stdout=dry_out,
        )
        dry_text = dry_out.getvalue()
        self.assertIn("- would_assign: 2", dry_text)
        self.assertIn("- skipped_unclear: 1", dry_text)

        self.p_shock.refresh_from_db()
        self.assertIsNone(self.p_shock.category_id)

        real_out = StringIO()
        call_command(
            "assign_remaining_manual_categories",
            "--supplier",
            "GPL",
            "--limit",
            "10",
            stdout=real_out,
        )
        real_text = real_out.getvalue()
        self.assertIn("- would_assign: 2", real_text)
        self.assertIn("- failed: 0", real_text)

        self.p_shock.refresh_from_db()
        self.p_battery.refresh_from_db()
        self.assertEqual(self.p_shock.category.slug, "amortizatory")
        self.assertEqual(self.p_battery.category.slug, "akkumuliatory")

        repeat_out = StringIO()
        call_command(
            "assign_remaining_manual_categories",
            "--supplier",
            "GPL",
            "--limit",
            "10",
            "--dry-run",
            stdout=repeat_out,
        )
        self.assertIn("- would_assign: 0", repeat_out.getvalue())

    def test_audit_remaining_outputs_summary(self):
        call_command("seed_remaining_manual_categories")
        out = StringIO()
        call_command(
            "audit_remaining_uncategorized_products",
            "--supplier",
            "GPL",
            "--limit",
            "10",
            stdout=out,
        )
        text = out.getvalue()
        self.assertIn("- total_uncategorized: 3", text)
        self.assertIn("- safe_candidates: 2", text)
        self.assertIn("- UTR calls=0", text)
