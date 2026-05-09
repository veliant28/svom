from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class SupplierCategoryMappingV2CommandsTests(TestCase):
    def setUp(self):
        call_command("seed_root_categories")
        call_command("seed_manual_chemical_categories")
        call_command("seed_manual_oil_fluid_categories")

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

        self.products: dict[str, Product] = {}
        self.products["engine"] = self._mk("GPL-OIL-ENG", "E001", "ARAL motor oil 5W-30", "ARAL", "ARAL", "ARAL")
        self.products["trans"] = self._mk("GPL-OIL-TRN", "T001", "SHELL ATF Dexron III", "SHELL", "SHELL", "SHELL")
        self.products["hyd"] = self._mk("GPL-OIL-HYD", "H001", "TOTAL Hydraulic Oil HLP 46", "TOTAL", "TOTAL", "TOTAL")
        self.products["adblue"] = self._mk("GPL-FLD-ADB", "A001", "VIRA AdBlue DEF Urea", "VIRA", "VIRA", "VIRA")
        self.products["brake"] = self._mk("GPL-FLD-BRK", "B001", "Brake fluid DOT 4", "REPSOL", "REPSOL", "REPSOL")
        self.products["coolant"] = self._mk("GPL-FLD-COL", "C001", "Coolant Antifreeze G12", "BMW", "BMW", "BMW")
        self.products["tech"] = self._mk("GPL-FLD-TEC", "F001", "Service technical fluid", "HICO", "HICO", "HICO")
        self.products["review"] = self._mk("GPL-REVIEW-1", "R001", "ARAL premium product", "ARAL", "ARAL", "ARAL")
        self.products["cooling_sensor"] = self._mk(
            "GPL-COOL-SNS",
            "S001",
            "Датчик температури охолоджуючої рідини AT",
            "AT",
            "Датчики",
            "AT",
        )
        self.products["cooling_fan"] = self._mk(
            "GPL-COOL-FAN",
            "F002",
            "Вентилятор охолодження двигуна AT",
            "AT",
            "Вентилятори",
            "AT",
        )

    def _mk(self, sku: str, article: str, name: str, brand_name: str, raw_category: str, raw_group: str) -> Product:
        brand, _ = Brand.objects.get_or_create(
            name=brand_name,
            defaults={"slug": f"{brand_name.lower()}-{article.lower()}", "is_active": True},
        )
        product = Product.objects.create(
            sku=sku,
            article=article,
            name=name,
            slug=f"{sku.lower()}-{article.lower()}",
            brand=brand,
            category=None,
            normalized_brand=brand_name,
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=1,
            external_sku=f"{sku}-EXT",
            article=article,
            normalized_article=article,
            brand_name=brand_name,
            normalized_brand=brand_name,
            product_name=name,
            price="100.00",
            stock_qty=5,
            lead_time_days=1,
            matched_product=product,
            is_valid=True,
            raw_payload={
                "Категорія": raw_category,
                "Група ТД": raw_group,
                "Найменування": name,
                "Опис": name,
            },
        )
        return product

    def test_audit_and_assign_v2(self):
        roots_before = Category.objects.filter(parent__isnull=True).count()

        audit_out = StringIO()
        call_command(
            "audit_supplier_category_mapping",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            "--only-uncategorized",
            stdout=audit_out,
        )
        audit_text = audit_out.getvalue()
        self.assertIn("- safe_new_manual_category_candidate: 7", audit_text)
        self.assertIn("- needs_review: 1", audit_text)
        self.assertIn("- ignore: 2", audit_text)

        dry_out = StringIO()
        call_command(
            "assign_supplier_mapped_categories",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            "--only-uncategorized",
            "--dry-run",
            stdout=dry_out,
        )
        dry_text = dry_out.getvalue()
        self.assertIn("- would_assign: 7", dry_text)
        self.assertIn("- skipped_review_mapping: 1", dry_text)
        self.assertIn("- skipped_no_mapping: 2", dry_text)
        self.assertIn("- failed: 0", dry_text)

        call_command(
            "assign_supplier_mapped_categories",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            "--only-uncategorized",
        )

        expected = {
            "engine": "motornye-masla",
            "trans": "transmissionnye-masla",
            "hyd": "gidravlicheskie-masla",
            "adblue": "adblue-i-tekhnicheskie-zhidkosti",
            "brake": "tormoznye-zhidkosti",
            "coolant": "antifrizy-i-okhlazhdaiushchie-zhidkosti",
            "tech": "tekhnicheskie-zhidkosti",
        }

        for key, slug in expected.items():
            self.products[key].refresh_from_db()
            self.assertIsNotNone(self.products[key].category)
            self.assertEqual(self.products[key].category.slug, slug)

        self.products["review"].refresh_from_db()
        self.assertIsNone(self.products["review"].category_id)
        self.products["cooling_sensor"].refresh_from_db()
        self.assertIsNone(self.products["cooling_sensor"].category_id)
        self.products["cooling_fan"].refresh_from_db()
        self.assertIsNone(self.products["cooling_fan"].category_id)

        repeat_out = StringIO()
        call_command(
            "assign_supplier_mapped_categories",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            "--only-uncategorized",
            "--dry-run",
            stdout=repeat_out,
        )
        repeat_text = repeat_out.getvalue()
        self.assertIn("- would_assign: 0", repeat_text)

        self.assertEqual(roots_before, Category.objects.filter(parent__isnull=True).count())
