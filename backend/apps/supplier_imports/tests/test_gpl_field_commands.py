from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article


class GplFieldCommandsTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="manual")
        self.offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            row_number=1,
            external_sku="0000000001",
            article="324966",
            normalized_article=normalize_article("324966"),
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            product_name="Oil filter",
            price="100.00",
            stock_qty=7,
            raw_payload={
                "Артикул": "324966",
                "Артикул ТД": "WP6873",
                "Код": "0000000001",
                "Найменування": "Oil filter",
            },
        )

    def test_backfill_dry_run_does_not_write(self):
        out = StringIO()
        call_command("gpl_backfill_article_fields", "--limit", "1", "--dry-run", stdout=out)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.article, "324966")
        self.assertEqual(self.offer.stock_qty, 7)
        self.assertEqual(str(self.offer.price), "100.00")

    def test_backfill_updates_article_from_manufacturer_field(self):
        out = StringIO()
        call_command("gpl_backfill_article_fields", "--limit", "1", stdout=out)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.article, "WP6873")
        self.assertEqual(self.offer.normalized_article, normalize_article("WP6873"))
        self.assertEqual(self.offer.external_sku, "0000000001")
        self.assertIn("gpl_article_resolution", self.offer.raw_payload)

    def test_diagnose_command_prints_candidate_fields(self):
        out = StringIO()
        call_command("gpl_diagnose_raw_offer_fields", "--limit", "1", stdout=out)
        output = out.getvalue()
        self.assertIn("manufacturer_article", output)
        self.assertIn("Артикул ТД", output)
