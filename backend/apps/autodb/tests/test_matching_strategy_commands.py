from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class AutoDbMatchingStrategyCommandsTests(SimpleTestCase):
    def test_gpl_alias_report_command_is_report_only_and_no_db_writes(self):
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "aliases.csv"
            md_path = Path(tmpdir) / "aliases.md"
            fake_candidate = SimpleNamespace(
                supplier_id=324,
                supplier_description="WIX FILTERS",
                supplier_matchcode="WIXFILTERS",
                confidence=0.99,
                reason="matchcode_exact",
            )
            fake_result = SimpleNamespace(candidates=[fake_candidate])
            fake_matcher = SimpleNamespace(resolve_many=lambda *args, **kwargs: {"WIXFILTERS": fake_result, "BOSAL": fake_result, "SPIDAN": fake_result, "POLMO": fake_result, "ALCA": fake_result, "ALPHAFILTER": fake_result})
            with patch(
                "apps.autodb.management.commands.autodb_matching_gpl_alias_report.SupplierBrandMatcher",
                return_value=fake_matcher,
            ):
                call_command(
                    "autodb_matching_gpl_alias_report",
                    export_csv=str(csv_path),
                    export_md=str(md_path),
                )
            self.assertTrue(csv_path.exists())
            self.assertTrue(md_path.exists())

    def test_utr_micro_smoke_reports_passed_but_gate_stops_small_probe(self):
        with TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "micro_smoke.md"
            fake_lookup = SimpleNamespace(
                found=True,
                matched_source="A_supplier_norm:remote:article_numbers.DataSupplierArticleNumber",
                matched_table="article_numbers",
                supplier_id=101,
                remote_hits=1,
                local_hits=0,
                remote_queries=2,
                error="",
            )
            with patch(
                "apps.autodb.management.commands.autodb_matching_utr_micro_smoke.AutoDbLookupV3ReadOnlyService.lookup",
                return_value=fake_lookup,
            ):
                call_command(
                    "autodb_matching_utr_micro_smoke",
                    export_md=str(md_path),
                    min_probe_n=20,
                    min_hit_rate=20.0,
                )
            self.assertTrue(md_path.exists())
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("micro_smoke_passed: `True`", content)
            self.assertIn("pilot_reason: `insufficient_probe_n`", content)
