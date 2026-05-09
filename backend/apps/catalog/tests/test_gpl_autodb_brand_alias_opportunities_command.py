from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.services.brand_alias_diagnostics import BrandAliasDiagnosticRow, BrandAliasStat


class GplAutoDbBrandAliasOpportunitiesCommandTests(TestCase):
    def test_command_exports_opportunities(self):
        stats = [BrandAliasStat(raw_brand="WIX FILTERS", normalized_brand="WIXFILTERS", offers=10)]
        rows = [
            BrandAliasDiagnosticRow(
                raw_brand="WIX FILTERS",
                normalized_brand="WIXFILTERS",
                offers=10,
                unique_articles=10,
                exact_supplier_match=True,
                relaxed_candidates=0,
                current_alias=False,
                current_alias_supplier_id=None,
                recommended_supplier_id=324,
                recommended_supplier_name="WIX FILTERS",
                confidence=0.95,
                recommendation="create_alias",
                reason="matchcode_exact",
                candidates="324:1.00:matchcode_exact",
                sample_articles="WL7283",
            )
        ]

        with TemporaryDirectory() as tmp_dir:
            out_csv = Path(tmp_dir) / "alias.csv"
            with (
                patch(
                    "apps.catalog.management.commands.diagnose_gpl_autodb_brand_alias_opportunities.AutoDbBrandAliasDiagnosticsService.collect_brand_stats",
                    return_value=stats,
                ),
                patch(
                    "apps.catalog.management.commands.diagnose_gpl_autodb_brand_alias_opportunities.AutoDbBrandAliasDiagnosticsService.diagnose",
                    return_value=rows,
                ),
            ):
                out = StringIO()
                call_command(
                    "diagnose_gpl_autodb_brand_alias_opportunities",
                    "--supplier",
                    "GPL",
                    "--limit",
                    "100",
                    "--export-csv",
                    str(out_csv),
                    stdout=out,
                )

            self.assertTrue(out_csv.exists())
            data = list(csv.DictReader(out_csv.open(encoding="utf-8")))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["raw_brand"], "WIX FILTERS")
            self.assertEqual(data[0]["can_auto_confirm"], "1")
            self.assertEqual(data[0]["proposed_supplier_id"], "324")
            self.assertIn("UTR calls=0", out.getvalue())
            self.assertIn("writes=0", out.getvalue())
