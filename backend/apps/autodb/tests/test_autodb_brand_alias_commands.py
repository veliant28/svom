from __future__ import annotations

import csv
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.models import AutoDbSupplier, AutoDbSupplierBrandAlias
from apps.autodb.services import SupplierBrandMatcher
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierBrandAlias, SupplierRawOffer


class AutoDbBrandAliasCommandsTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
        )
        self.run = ImportRun.objects.create(source=self.source)

        AutoDbSupplier.objects.create(id=324, name="WIX FILTERS", matchcode="WIXFILTERS", normalized_name="WIXFILTERS", normalized_matchcode="WIXFILTERS")
        AutoDbSupplier.objects.create(id=4, name="MANN-FILTER", matchcode="MANNFILTER", normalized_name="MANNFILTER", normalized_matchcode="MANNFILTER")
        AutoDbSupplier.objects.create(id=15, name="AT-A", matchcode="AT", normalized_name="AT", normalized_matchcode="AT")
        AutoDbSupplier.objects.create(id=16, name="AT-B", matchcode="AT", normalized_name="AT", normalized_matchcode="AT")

    def _offer(self, *, brand: str, article: str = "A1", external_sku: str = "SKU1", price: str = "100.00", stock: int = 7):
        return SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku=external_sku,
            article=article,
            normalized_article=article,
            brand_name=brand,
            normalized_brand="",
            product_name=f"{brand} Product",
            price=Decimal(price),
            stock_qty=stock,
            raw_payload={},
        )

    def test_dry_run_writes_nothing_and_invalid_brand_skipped(self):
        self._offer(brand="WIX FILTERS", article="325193")
        self._offer(brand="Без бренду", article="001")
        out = StringIO()
        before_count = AutoDbSupplierBrandAlias.objects.count()
        call_command(
            "autodb_create_brand_aliases",
            "--supplier",
            "GPL",
            "--limit",
            "5000",
            "--only-high-confidence",
            "--min-confidence",
            "0.9",
            "--dry-run",
            stdout=out,
        )
        after_count = AutoDbSupplierBrandAlias.objects.count()
        output = out.getvalue()
        self.assertEqual(before_count, after_count)
        self.assertIn("- mode: dry-run (no alias writes)", output)
        self.assertIn("- UTR calls: 0", output)
        self.assertIn("- price/stock changed: 0", output)

    def test_real_create_alias_and_matcher_uses_it(self):
        with patch("apps.autodb.management.commands.autodb_create_brand_aliases.AutoDbBrandAliasDiagnosticsService.collect_brand_stats", return_value=[]):
            with patch(
                "apps.autodb.management.commands.autodb_create_brand_aliases.AutoDbBrandAliasDiagnosticsService.diagnose",
                return_value=[
                    SimpleNamespace(
                        raw_brand="WIX FILTERS",
                        normalized_brand="WIXFILTERS",
                        offers=10,
                        unique_articles=8,
                        exact_supplier_match=True,
                        relaxed_candidates=0,
                        current_alias=False,
                        current_alias_supplier_id=None,
                        recommended_supplier_id=324,
                        recommended_supplier_name="WIX FILTERS",
                        confidence=1.0,
                        recommendation="create_alias",
                        reason="matchcode_exact",
                        candidates="324:1.00:matchcode_exact",
                        sample_articles="325193",
                    )
                ],
            ):
                out = StringIO()
                call_command(
                    "autodb_create_brand_aliases",
                    "--supplier",
                    "GPL",
                    "--brand",
                    "WIX FILTERS",
                    "--limit",
                    "5000",
                    "--min-confidence",
                    "0.9",
                    stdout=out,
                )
        alias = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand="WIXFILTERS").first()
        self.assertIsNotNone(alias)
        matcher = SupplierBrandMatcher()
        with patch.object(
            matcher,
            "_load_suppliers",
            return_value=[{"id": 324, "description": "WIX FILTERS", "matchcode": "WIXFILTERS", "fulldescription": "WIX FILTERS"}],
        ):
            result = matcher.resolve_many(["WIX FILTERS"])
        self.assertEqual(result["WIXFILTERS"].matched_supplier_id, 324)

    def test_mann_and_mann_filter_resolve_to_mann_filter(self):
        SupplierBrandAlias.objects.create(
            source=self.source,
            supplier=self.supplier,
            canonical_brand_name="MANN FILTER",
            supplier_brand_alias="MANN",
            is_active=True,
            priority=500,
        )
        matcher = SupplierBrandMatcher()
        with patch.object(
            matcher,
            "_load_suppliers",
            return_value=[{"id": 4, "description": "MANN-FILTER", "matchcode": "MANNFILTER", "fulldescription": "MANN FILTER"}],
        ):
            result = matcher.resolve_many(["MANN", "MANN FILTER"], source_id=str(self.source.id), supplier_id=str(self.supplier.id))
        self.assertEqual(result["MANN"].matched_supplier_id, 4)
        self.assertEqual(result["MANNFILTER"].matched_supplier_id, 4)

    def test_ambiguous_brand_not_auto_confirmed(self):
        self._offer(brand="AT", article="X1")
        out = StringIO()
        call_command(
            "autodb_create_brand_aliases",
            "--supplier",
            "GPL",
            "--brand",
            "AT",
            "--limit",
            "5000",
            "--dry-run",
            stdout=out,
        )
        self.assertFalse(AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand="AT").exists())

    def test_create_aliases_from_csv_only_auto_confirm_and_skip_unsafe(self):
        with TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "alias_opps.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "raw_brand",
                        "product_count",
                        "exact_local_supplier_name_candidates",
                        "fuzzy_supplier_candidates",
                        "supplier_detail_candidates",
                        "confidence",
                        "can_auto_confirm",
                        "reason",
                        "recommended_action",
                        "proposed_supplier_id",
                        "proposed_supplier_name",
                        "examples",
                        "possible_supplier_matches",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "raw_brand": "WIX FILTERS",
                        "product_count": "10",
                        "exact_local_supplier_name_candidates": "1",
                        "fuzzy_supplier_candidates": "0",
                        "supplier_detail_candidates": "1",
                        "confidence": "0.95",
                        "can_auto_confirm": "1",
                        "reason": "matchcode_exact",
                        "recommended_action": "create_alias",
                        "proposed_supplier_id": "324",
                        "proposed_supplier_name": "WIX FILTERS",
                        "examples": "WL7283",
                        "possible_supplier_matches": "324:1.00:matchcode_exact",
                    }
                )
                writer.writerow(
                    {
                        "raw_brand": "AT",
                        "product_count": "12",
                        "exact_local_supplier_name_candidates": "1",
                        "fuzzy_supplier_candidates": "1",
                        "supplier_detail_candidates": "2",
                        "confidence": "0.95",
                        "can_auto_confirm": "1",
                        "reason": "matchcode_exact",
                        "recommended_action": "create_alias",
                        "proposed_supplier_id": "15",
                        "proposed_supplier_name": "AT-A",
                        "examples": "AT100",
                        "possible_supplier_matches": "15:0.95:matchcode_exact;16:0.95:matchcode_exact",
                    }
                )
                writer.writerow(
                    {
                        "raw_brand": "MITKA",
                        "product_count": "5",
                        "exact_local_supplier_name_candidates": "0",
                        "fuzzy_supplier_candidates": "0",
                        "supplier_detail_candidates": "0",
                        "confidence": "0.00",
                        "can_auto_confirm": "0",
                        "reason": "brand_not_found",
                        "recommended_action": "manual_review",
                        "proposed_supplier_id": "",
                        "proposed_supplier_name": "",
                        "examples": "",
                        "possible_supplier_matches": "",
                    }
                )

            out = StringIO()
            call_command(
                "autodb_create_brand_aliases",
                "--supplier",
                "GPL",
                "--from-csv",
                str(csv_path),
                "--only-auto-confirm",
                "--dry-run",
                stdout=out,
            )

            text = out.getvalue()
            self.assertIn("- candidates: 1", text)
            self.assertIn("- skipped_manual_review: 1", text)
            self.assertIn("- skipped_unsafe_ambiguous: 1", text)
            self.assertFalse(AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand="AT").exists())
            self.assertFalse(AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand="MITKA").exists())

    def test_create_aliases_from_csv_apply_is_idempotent(self):
        with TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "alias_apply.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "raw_brand",
                        "product_count",
                        "confidence",
                        "can_auto_confirm",
                        "reason",
                        "recommended_action",
                        "proposed_supplier_id",
                        "proposed_supplier_name",
                        "examples",
                        "possible_supplier_matches",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "raw_brand": "WIX FILTERS",
                        "product_count": "10",
                        "confidence": "0.95",
                        "can_auto_confirm": "1",
                        "reason": "matchcode_exact",
                        "recommended_action": "create_alias",
                        "proposed_supplier_id": "324",
                        "proposed_supplier_name": "WIX FILTERS",
                        "examples": "WL7283",
                        "possible_supplier_matches": "324:1.00:matchcode_exact",
                    }
                )

            call_command(
                "autodb_create_brand_aliases",
                "--supplier",
                "GPL",
                "--from-csv",
                str(csv_path),
                "--only-auto-confirm",
                "--apply",
                stdout=StringIO(),
            )
            alias_count = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand="WIXFILTERS", is_active=True).count()
            self.assertEqual(alias_count, 1)

            repeat_out = StringIO()
            call_command(
                "autodb_create_brand_aliases",
                "--supplier",
                "GPL",
                "--from-csv",
                str(csv_path),
                "--only-auto-confirm",
                "--dry-run",
                stdout=repeat_out,
            )
            self.assertIn("- would_create: 0", repeat_out.getvalue())

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_price_stock_unchanged_and_utr_not_called(self, utr_client):
        offer = self._offer(brand="WIX FILTERS", article="325193", external_sku="325193", price="123.45", stock=9)
        before_price = offer.price
        before_stock = offer.stock_qty

        out = StringIO()
        call_command(
            "autodb_create_brand_aliases",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--limit",
            "5000",
            "--dry-run",
            stdout=out,
        )
        offer.refresh_from_db()
        self.assertEqual(offer.price, before_price)
        self.assertEqual(offer.stock_qty, before_stock)
        utr_client.assert_not_called()
