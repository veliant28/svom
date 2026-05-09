from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class UnlinkedSupplierCategoriesCommandsTests(TestCase):
    def setUp(self):
        call_command("seed_root_categories")

        self.brand = Brand.objects.create(name="MITKA", slug="mitka", is_active=True)
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

        self.unlinked = Product.objects.create(
            sku="GPL-1",
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
        self._raw_offer(self.unlinked, brand_name="MITKA", product_name="Емаль автомобільна MITKA 118", payload={"Категорія": "MITKA", "Найменування": "Емаль аерозоль"})

        self.unclear = Product.objects.create(
            sku="GPL-2",
            article="XQ17",
            name="Набір XQ-17",
            slug="xq-17",
            brand=self.brand,
            category=None,
            normalized_brand="UNKNOWN",
            autodb_article_key="",
            autodb_supplier_id=None,
            is_active=True,
        )
        self._raw_offer(self.unclear, brand_name="UNKNOWN", product_name="Набір XQ-17", payload={"Категорія": "MISC"})

    def _raw_offer(self, product: Product, *, brand_name: str, product_name: str, payload: dict):
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
            product_name=product_name,
            price="100.00",
            stock_qty=5,
            lead_time_days=1,
            matched_product=product,
            is_valid=True,
            raw_payload=payload,
        )

    def test_diagnose_outputs_summary(self):
        out = StringIO()
        call_command("diagnose_unlinked_supplier_categories", "--supplier", "GPL", "--limit", "10", stdout=out)
        text = out.getvalue()
        self.assertIn("- total_unlinked: 2", text)
        self.assertIn("- mapped_", text)
        self.assertIn("- UTR calls=0", text)

    def test_update_dry_run_does_not_write_product_category_and_does_not_create_roots(self):
        roots_before = Category.objects.filter(parent__isnull=True).count()
        self.assertEqual(roots_before, len(MANUAL_ROOT_CATEGORY_SPECS))

        out = StringIO()
        call_command("update_unlinked_supplier_categories", "--supplier", "GPL", "--limit", "10", "--dry-run", stdout=out)

        self.unlinked.refresh_from_db()
        self.unclear.refresh_from_db()
        self.assertIsNone(self.unlinked.category_id)
        self.assertIsNone(self.unclear.category_id)

        roots_after = Category.objects.filter(parent__isnull=True).count()
        self.assertEqual(roots_after, len(MANUAL_ROOT_CATEGORY_SPECS))
        self.assertIn("- would_update:", out.getvalue())
        self.assertIn("- UTR calls=0", out.getvalue())
        self.assertIn("- price/stock changed=0", out.getvalue())
