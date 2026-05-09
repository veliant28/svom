from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Product


class GplAutoDbArticleNotFoundDiagnosticsCommandTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="Brand", slug="brand", is_active=True)
        self.product = Product.objects.create(
            sku="GPL-000000004363234",
            article="V208",
            name="Test product",
            slug="test-product",
            brand=brand,
            is_active=True,
        )

    def test_command_exports_breakdown_without_writes(self):
        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            out_csv = Path(tmp_dir) / "breakdown.csv"
            summary_csv = Path(tmp_dir) / "summary.csv"
            with candidates.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "product_id",
                        "raw_brand_source_field",
                        "raw_brand",
                        "article_source_field",
                        "lookup_article",
                        "raw_article",
                        "gpl_code",
                        "gpl_article",
                        "gpl_td_article",
                        "raw_name",
                        "raw_category",
                        "raw_group",
                        "mapped_site_category",
                        "decision",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "product_id": str(self.product.id),
                        "raw_brand_source_field": "raw_payload.Група ТД",
                        "raw_brand": "MITKA",
                        "article_source_field": "raw_payload.Артикул ТД",
                        "lookup_article": "A-100",
                        "raw_article": "A-100",
                        "gpl_code": "000000004363234",
                        "gpl_article": "SUP-1",
                        "gpl_td_article": "A-100",
                        "raw_name": "Емаль MITKA",
                        "raw_category": "Автомобільні емалі",
                        "raw_group": "MITKA",
                        "mapped_site_category": "Аэрозольные краски",
                        "decision": "article_not_found",
                    }
                )

            with patch(
                "apps.catalog.management.commands.diagnose_gpl_autodb_article_not_found.SupplierBrandMatcher.resolve_many",
                return_value={},
            ), patch(
                "apps.catalog.management.commands.diagnose_gpl_autodb_article_not_found.AutoDbRawCloneStorage.get_local_columns",
                return_value=set(),
            ):
                out = StringIO()
                call_command(
                    "diagnose_gpl_autodb_article_not_found",
                    "--supplier",
                    "GPL",
                    "--limit",
                    "100",
                    "--candidates-csv",
                    str(candidates),
                    "--export-csv",
                    str(out_csv),
                    "--summary-csv",
                    str(summary_csv),
                    stdout=out,
                )

            self.assertTrue(out_csv.exists())
            self.assertTrue(summary_csv.exists())
            rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["display_sku"], "000000004363234")
            self.assertEqual(rows[0]["internal_import_key"], "GPL-000000004363234")
            self.assertEqual(rows[0]["brand_resolution_status"], "unresolved")
            self.assertEqual(rows[0]["recommended_next_action"], "non_tecdoc_ignore")
            self.assertIn("UTR calls=0", out.getvalue())
            self.assertIn("writes=0", out.getvalue())
