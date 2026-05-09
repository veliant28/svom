from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class SafetyAuditsAndCleanupCommandsTests(TestCase):
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

        shock_parent = Category.objects.get(slug="podveska-i-rulevoe")
        self.shock_category = Category.objects.create(
            name="Амортизаторы",
            slug="amortizatory-test-safety",
            parent=shock_parent,
            source=Category.SOURCE_AUTODB_PRO,
            is_active=True,
            show_in_header=False,
        )

        paint_category = Category.objects.get(slug="avtoemali-i-kraski")

        brand_polmo = Brand.objects.create(name="POLMO", slug="polmo-test", is_active=True)
        self.linked_suspicious = Product.objects.create(
            sku="GPL-LINK-1",
            article="POLMO-001",
            name="Амортизатор POLMO",
            slug="amortizator-polmo-001",
            brand=brand_polmo,
            category=self.shock_category,
            autodb_article_key="123:POLMO-001",
            autodb_supplier_id=123,
            autodb_supplier_name="POLMO",
            name_source=Product.NAME_SOURCE_AUTODB_PRO,
            name_source_text="Shock absorber",
            brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
            is_active=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=1,
            external_sku="GPL-LINK-1-EXT",
            article="POLMO-001",
            normalized_article="POLMO-001",
            brand_name="POLMO",
            normalized_brand="POLMO",
            product_name="Глушник POLMO задній",
            price="100.00",
            stock_qty=5,
            lead_time_days=1,
            matched_product=self.linked_suspicious,
            is_valid=True,
            raw_payload={
                "Категорія": "Глушники",
                "Група ТД": "POLMO",
                "Найменування": "Глушник POLMO задній",
                "Опис": "вихлопна система muffler",
                "Зображення товару": "http://example.com/polmo.jpg",
            },
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.linked_suspicious,
            autodb_article_key="123:POLMO-001",
            autodb_supplier_id=123,
            autodb_article_number="POLMO-001",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="baseline",
            evidence={"autodb_article_title": "Shock absorber"},
        )

        brand_mitka = Brand.objects.create(name="MITKA", slug="mitka-test-safety", is_active=True)
        self.paint_safe = Product.objects.create(
            sku="GPL-PAINT-1",
            article="M-PAINT-1",
            name="Емаль автомобільна MITKA",
            slug="mitka-paint-1",
            brand=brand_mitka,
            category=paint_category,
            autodb_article_key="",
            is_active=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=2,
            external_sku="GPL-PAINT-1-EXT",
            article="M-PAINT-1",
            normalized_article="M-PAINT-1",
            brand_name="MITKA",
            normalized_brand="MITKA",
            product_name="Емаль автомобільна MITKA",
            price="100.00",
            stock_qty=5,
            lead_time_days=1,
            matched_product=self.paint_safe,
            is_valid=True,
            raw_payload={
                "Категорія": "Автоемалі",
                "Група ТД": "MITKA",
                "Найменування": "Емаль автомобільна MITKA",
                "Опис": "фарба",
            },
        )

        brand_css = Brand.objects.create(name="CS SYSTEM", slug="css-test-safety", is_active=True)
        self.paint_bad = Product.objects.create(
            sku="GPL-PAINT-2",
            article="M-BAD-1",
            name="Круг наждачний CS SYSTEM",
            slug="css-abrasive-1",
            brand=brand_css,
            category=paint_category,
            autodb_article_key="",
            is_active=True,
        )
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=3,
            external_sku="GPL-PAINT-2-EXT",
            article="M-BAD-1",
            normalized_article="M-BAD-1",
            brand_name="CS SYSTEM",
            normalized_brand="CS SYSTEM",
            product_name="Круг наждачний CS SYSTEM",
            price="100.00",
            stock_qty=5,
            lead_time_days=1,
            matched_product=self.paint_bad,
            is_valid=True,
            raw_payload={
                "Категорія": "Автоемалі",
                "Група ТД": "CS SYSTEM",
                "Найменування": "Круг наждачний",
                "Опис": "абразив",
            },
        )

    def test_suspicious_link_audit_and_rollback_dry_run_no_writes(self):
        before = Product.objects.get(pk=self.linked_suspicious.pk)

        audit_out = StringIO()
        call_command(
            "audit_suspicious_autodb_links",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            stdout=audit_out,
        )
        audit_text = audit_out.getvalue()
        self.assertIn("- suspicious_exhaust_as_shock: 1", audit_text)
        self.assertIn("- suspicious_by_brand_polmo: 1", audit_text)

        dry_out = StringIO()
        call_command(
            "rollback_suspicious_autodb_product_enrichment",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            "--reason",
            "exhaust_as_shock",
            "--dry-run",
            stdout=dry_out,
        )
        dry_text = dry_out.getvalue()
        self.assertIn("- candidates: 1", dry_text)
        self.assertIn("- would_mark_suspicious: 1", dry_text)

        after = Product.objects.get(pk=self.linked_suspicious.pk)
        self.assertEqual(before.autodb_article_key, after.autodb_article_key)
        self.assertEqual(before.category_id, after.category_id)
        self.assertEqual(before.name, after.name)

    def test_manual_category_contamination_audit_and_cleanup_dry_run_no_writes(self):
        before_bad = Product.objects.get(pk=self.paint_bad.pk)

        audit_out = StringIO()
        call_command(
            "audit_manual_category_contamination",
            "--category",
            "Автоэмали и краски",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            stdout=audit_out,
        )
        text = audit_out.getvalue()
        self.assertIn("- total_in_category: 2", text)
        self.assertIn("- contaminated_count: 1", text)
        self.assertIn("should_move_to_abrasives", text)

        cleanup_out = StringIO()
        call_command(
            "cleanup_manual_category_assignments",
            "--source-category",
            "Автоэмали и краски",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            "--dry-run",
            stdout=cleanup_out,
        )
        cleanup_text = cleanup_out.getvalue()
        self.assertIn("- processed: 2", cleanup_text)
        self.assertIn("- would_keep: 1", cleanup_text)
        self.assertIn("- would_clear: 1", cleanup_text)

        after_bad = Product.objects.get(pk=self.paint_bad.pk)
        self.assertEqual(before_bad.category_id, after_bad.category_id)
