from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.services.article_variant_diagnostics import (
    ArticleVariantDiagnosticsReport,
    ArticleVariantDiagnosticsRow,
    BrandVariantDiagnostics,
    RemoteDiagnosticsSummary,
)
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbDiagnoseArticleVariantsCommandTests(TestCase):
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

    def _create_offer(self) -> SupplierRawOffer:
        return SupplierRawOffer.objects.create(
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

    def _stub_report(self, offer: SupplierRawOffer) -> ArticleVariantDiagnosticsReport:
        row = ArticleVariantDiagnosticsRow(
            supplier="gpl",
            raw_brand="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            supplier_id=324,
            raw_article="325193",
            normalized_article="325193",
            raw_product_name="Фільтр оливи WIX FILTERS BMW (WL7042)",
            external_sku="325193",
            article_variants=("325193", "WL7042"),
            raw_name_alt_tokens=("WL7042",),
            raw_name_contains_alt_article=True,
            external_sku_looks_like_manufacturer_article=False,
            matched_product_ids=(),
            corrected_article_candidate="WL7042",
            corrected_article_source="raw_name",
            autodb_title="Oil Filter WL7042",
            lookup_articles=True,
            lookup_article_numbers=True,
            lookup_article_m=False,
            lookup_article_nn=False,
            lookup_article_oe=False,
            lookup_article_cross=False,
            lookup_article_ean=False,
            recommendation="article_in_raw_name",
            reason="article_in_raw_name_high_confidence",
            confidence=0.95,
            sample_offer_id=str(offer.id),
        )
        brand = BrandVariantDiagnostics(
            raw_brand="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            supplier_id=324,
            total_pairs=10,
            linked_pairs=1,
            not_found_pairs=9,
            top_article_patterns=("numeric_only",),
            raw_name_alt_article_count=1,
            variant_lookup_would_find_count=1,
            needs_manual_mapping_count=0,
        )
        remote = RemoteDiagnosticsSummary(
            batch_size=1000,
            estimated_remote_queries=1,
            unresolved_pairs=9,
            remote_examples=(("WIX FILTERS", "325193", 324),),
            remote_not_checked_reason="local_diagnostics_only",
        )
        return ArticleVariantDiagnosticsReport(
            supplier="gpl",
            total_raw_offers=1,
            total_pairs=1,
            linked_pairs=0,
            unresolved_pairs=1,
            unresolved_supplier_resolved_pairs=1,
            diagnostics_rows=(row,),
            brand_breakdown=(brand,),
            remote_summary=remote,
        )

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    def test_command_is_read_only_and_does_not_call_utr(self, utr_client):
        offer = self._create_offer()
        before_price = offer.price
        before_stock = offer.stock_qty

        out = StringIO()
        report = self._stub_report(offer)
        with patch(
            "apps.autodb.management.commands.autodb_diagnose_article_variants.AutoDbArticleVariantDiagnosticsService.diagnose",
            return_value=report,
        ):
            call_command(
                "autodb_diagnose_article_variants",
                "--supplier",
                "GPL",
                "--limit",
                "100",
                stdout=out,
            )

        offer.refresh_from_db()
        self.assertEqual(offer.price, before_price)
        self.assertEqual(offer.stock_qty, before_stock)
        output = out.getvalue()
        self.assertIn("article_in_raw_name", output)
        self.assertIn("- report_mode: diagnostics-only/read-only", output)
        self.assertIn("- UTR calls: 0", output)
        self.assertIn("- price/stock changed: 0", output)
        utr_client.assert_not_called()
