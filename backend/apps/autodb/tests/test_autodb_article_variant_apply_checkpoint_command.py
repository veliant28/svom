from __future__ import annotations

from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.services.article_variant_checkpoint import (
    ArticleVariantCheckpointBrandSummary,
    ArticleVariantCheckpointRecommendation,
    ArticleVariantCheckpointReport,
    ArticleVariantCheckpointRow,
    PolmoReviewSummary,
)
from apps.autodb.services.article_variant_diagnostics import (
    ArticleVariantDiagnosticsReport,
    BrandVariantDiagnostics,
    RemoteDiagnosticsSummary,
)
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbArticleVariantApplyCheckpointCommandTests(TestCase):
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
        self.offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="325193",
            article="325193",
            normalized_article="325193",
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            product_name="Фільтр оливи WIX FILTERS BMW (WL7042)",
            price=Decimal("123.45"),
            stock_qty=9,
            raw_payload={},
        )

    def _stub_report(self) -> ArticleVariantCheckpointReport:
        diagnostics = ArticleVariantDiagnosticsReport(
            supplier="gpl",
            total_raw_offers=1,
            total_pairs=1,
            linked_pairs=0,
            unresolved_pairs=1,
            unresolved_supplier_resolved_pairs=1,
            diagnostics_rows=(),
            brand_breakdown=(
                BrandVariantDiagnostics(
                    raw_brand="WIX FILTERS",
                    normalized_brand="WIXFILTERS",
                    supplier_id=324,
                    total_pairs=10,
                    linked_pairs=1,
                    not_found_pairs=9,
                    top_article_patterns=("numeric_only",),
                    raw_name_alt_article_count=1,
                    variant_lookup_would_find_count=3,
                    needs_manual_mapping_count=0,
                ),
            ),
            remote_summary=RemoteDiagnosticsSummary(
                batch_size=1000,
                estimated_remote_queries=0,
                unresolved_pairs=1,
                remote_examples=(),
                remote_not_checked_reason="local_diagnostics_only",
            ),
        )
        row = ArticleVariantCheckpointRow(
            supplier="gpl",
            raw_brand="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            resolved_supplier_id=324,
            raw_article="325193",
            normalized_article="325193",
            corrected_article_candidate="WL7042",
            product_id="p1",
            current_autodb_article_key="",
            proposed_autodb_article_key="324:WL7042",
            status="safe_to_apply",
            confidence=0.95,
            reason="variant_matches_supplier_article",
            raw_product_name="Фільтр оливи WIX FILTERS BMW (WL7042)",
            autodb_title="Oil Filter WL7042",
            autodb_category="Filters",
            recommendation="try_variant",
            current_quality_status="",
            recommended_action="candidate_for_next_real_apply",
            sample_offer_id=str(self.offer.id),
            related_to_known_suspicious_product=False,
        )
        brand_summary = ArticleVariantCheckpointBrandSummary(
            raw_brand="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            resolved_supplier_id=324,
            total_pairs=10,
            linked_before_or_current=1,
            variant_would_find_total=3,
            already_linked_same_key=0,
            already_linked_conflicting_key=0,
            remaining_safe_to_apply=1,
            needs_manual_review=0,
            suspicious=0,
            semantic_conflict=0,
            exact_not_found=0,
            skipped_low_confidence=0,
            non_auto_ignore=0,
            recommended_next_action="ready_for_next_batch",
        )
        recommendation = ArticleVariantCheckpointRecommendation(
            recommended_next_brand="WIX FILTERS",
            recommended_limit=1,
            expected_safe_candidates=1,
            command_to_run_next_dry_run='python manage.py autodb_apply_article_variant_links --supplier GPL --brand "WIX FILTERS" --limit 1 --min-confidence 0.9 --dry-run',
            command_to_run_next_real='python manage.py autodb_apply_article_variant_links --supplier GPL --brand "WIX FILTERS" --limit 1 --min-confidence 0.9',
        )
        polmo_summary = PolmoReviewSummary(
            safe_to_apply=0,
            suspicious=0,
            semantic_conflict=0,
            already_linked_same_key=0,
            already_linked_conflicting_key=0,
            related_to_known_suspicious_products=0,
            exhaust_to_shock_risk=0,
            recommended_next_action="review_only",
            examples=(),
        )
        return ArticleVariantCheckpointReport(
            supplier="gpl",
            limit=5000,
            min_confidence=0.9,
            diagnostics_report=diagnostics,
            checkpoint_rows=(row,),
            brand_summaries=(brand_summary,),
            recommended_next=recommendation,
            polmo_summary=polmo_summary,
        )

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_command_exports_csv_and_stays_read_only(self, utr_client):
        before_price = self.offer.price
        before_stock = self.offer.stock_qty
        out = StringIO()
        export_path = Path("/tmp/gpl_variant_checkpoint_test.csv")
        if export_path.exists():
            export_path.unlink()

        report = self._stub_report()
        with patch(
            "apps.autodb.management.commands.autodb_article_variant_apply_checkpoint.AutoDbArticleVariantApplyCheckpointService.build_report",
            return_value=report,
        ):
            call_command(
                "autodb_article_variant_apply_checkpoint",
                "--supplier",
                "GPL",
                "--limit",
                "100",
                "--export-csv",
                str(export_path),
                stdout=out,
            )

        self.offer.refresh_from_db()
        self.assertEqual(self.offer.price, before_price)
        self.assertEqual(self.offer.stock_qty, before_stock)
        self.assertTrue(export_path.exists())
        csv_text = export_path.read_text(encoding="utf-8")
        self.assertIn("recommended_action", csv_text)
        self.assertIn("324:WL7042", csv_text)
        output = out.getvalue()
        self.assertIn("remaining_safe_to_apply", output)
        self.assertIn("recommended_next_brand: WIX FILTERS", output)
        self.assertIn("- report_mode: checkpoint/read-only", output)
        self.assertIn("- UTR calls: 0", output)
        self.assertIn("- price/stock changed: 0", output)
        self.assertIn("- compatibility filtering: disabled/no-op unchanged", output)
        utr_client.assert_not_called()

