from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.manual_chemical_categories import MANUAL_CHEMICAL_ROOT_SLUG
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class ManualChemicalCategoriesCommandsTests(TestCase):
    def setUp(self):
        call_command("seed_root_categories")
        call_command("seed_manual_chemical_categories")

        self.brand = Brand.objects.create(name="MITKA", slug="mitka", is_active=True)
        self.blocked_brand = Brand.objects.create(name="DAINTON", slug="dainton", is_active=True)
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

        self.chemical = Product.objects.create(
            sku="GPL-CHEM-1",
            article="MI0118",
            name="Емаль автомобільна MITKA 118",
            slug="mitka-118",
            brand=self.brand,
            category=None,
            normalized_brand="MITKA",
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        self._raw_offer(
            self.chemical,
            brand_name="MITKA",
            payload={
                "Категорія": "Автомобільні емалі",
                "Група ТД": "MITKA",
                "Найменування": "Емаль автомобільна MITKA 118 аерозоль",
                "Опис": "фарба аерозоль 400 мл",
            },
        )

        self.blocked = Product.objects.create(
            sku="GPL-BLOCK-1",
            article="D181007",
            name="DAINTON D181007",
            slug="dainton-181007",
            brand=self.blocked_brand,
            category=None,
            normalized_brand="DAINTON",
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        self._raw_offer(
            self.blocked,
            brand_name="DAINTON",
            payload={
                "Категорія": "Запчастини",
                "Група ТД": "DAINTON",
                "Найменування": "DAINTON D181007",
                "Опис": "деталь",
            },
        )

        self.autodb_category = Category.objects.create(
            name="Амортизатор",
            slug="autodb-shock-child-test",
            source=Category.SOURCE_AUTODB_PRO,
            parent=Category.objects.get(slug=MANUAL_CHEMICAL_ROOT_SLUG),
            show_in_header=False,
            is_active=True,
            autodb_prd_id=999999,
        )

        self.k2_brand = Brand.objects.create(name="K2", slug="k2", is_active=True)
        self.k2_product = Product.objects.create(
            sku="GPL-K2-1",
            article="EB5",
            name="Розчин сечовини K2 EuroBlue 5 л (EB5)",
            slug="k2-eb5",
            brand=self.k2_brand,
            category=Category.objects.get(slug="ochistiteli-i-avtokhimiia"),
            normalized_brand="K2",
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        self._raw_offer(
            self.k2_product,
            brand_name="K2",
            payload={
                "Категорія": "Технічні рідини",
                "Група ТД": "AdBlue",
                "Найменування": "Розчин сечовини K2 EuroBlue 5 л (EB5)",
                "Опис": "AdBlue technical fluid",
            },
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

    def test_audit_candidates_reports_safe_and_skip(self):
        out = StringIO()
        call_command(
            "audit_manual_chemical_category_candidates",
            "--supplier",
            "GPL",
            "--limit",
            "10",
            stdout=out,
        )
        text = out.getvalue()
        self.assertIn("- safe_manual_category_candidate: 2", text)
        self.assertIn("- skip: 1", text)
        self.assertIn("- UTR calls=0", text)

    def test_assign_dry_run_does_not_write_and_keeps_autodb_categories(self):
        autodb_count_before = Category.objects.filter(source=Category.SOURCE_AUTODB_PRO).count()

        out = StringIO()
        call_command(
            "assign_manual_chemical_categories",
            "--supplier",
            "GPL",
            "--limit",
            "10",
            "--dry-run",
            stdout=out,
        )
        text = out.getvalue()

        self.chemical.refresh_from_db()
        self.blocked.refresh_from_db()
        self.assertIsNone(self.chemical.category_id)
        self.assertIsNone(self.blocked.category_id)
        self.assertEqual(autodb_count_before, Category.objects.filter(source=Category.SOURCE_AUTODB_PRO).count())
        self.assertIn("- would_assign: 2", text)
        self.assertIn("- skipped_not_chemical: 1", text)
        self.assertIn("- UTR calls=0", text)
        self.assertIn("- price/stock changed=0", text)

    def test_k2_euroblue_remaps_to_adblue_category(self):
        out = StringIO()
        call_command(
            "assign_manual_chemical_categories",
            "--supplier",
            "GPL",
            "--limit",
            "20",
            "--dry-run",
            stdout=out,
        )
        self.assertIn("AdBlue и технические жидкости", out.getvalue())

        call_command(
            "assign_manual_chemical_categories",
            "--supplier",
            "GPL",
            "--limit",
            "20",
        )
        self.k2_product.refresh_from_db()
        self.assertEqual(self.k2_product.category.slug, "adblue-i-tekhnicheskie-zhidkosti")
