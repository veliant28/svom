from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.services.article_variant_diagnostics import (
    ArticleVariantDiagnosticsReport,
    ArticleVariantDiagnosticsRow,
    AutoDbArticleVariantDiagnosticsService,
    BrandVariantDiagnostics,
    RemoteDiagnosticsSummary,
)
from apps.autodb.services.article_variant_checkpoint import AutoDbArticleVariantApplyCheckpointService
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbApplyArticleVariantLinksCommandTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="variant-cmd-brand", is_active=True)
        self.category = Category.objects.create(name="Category", slug="variant-cmd-category", is_active=True)
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

        self.product_same = self._product(sku="SAME-1", key="324:WIX001")
        self.product_safe = self._product(sku="SAFE-1")
        self.product_conflict = self._product(sku="CONFLICT-1", key="324:OLD999")
        self.product_suspicious = self._product(sku="SUSP-1")
        AutoDbProductLinkQuality.objects.create(
            product=self.product_suspicious,
            autodb_article_key="",
            autodb_supplier_id=None,
            autodb_article_number="",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="suspicious_link",
        )

    def _product(self, *, sku: str, key: str = "") -> Product:
        return Product.objects.create(
            sku=sku,
            article=sku,
            slug=f"{sku.lower()}-slug",
            name=f"Product {sku}",
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_article_key=key,
            autodb_article_number=key.split(":", 1)[1] if ":" in key else "",
            autodb_supplier_id=int(key.split(":", 1)[0]) if ":" in key else None,
            catalog_source=Product.CATALOG_SOURCE_LEGACY,
            available_stock_qty_cached=12,
        )

    def _row(
        self,
        *,
        product: Product,
        raw_article: str,
        corrected_article_candidate: str,
        raw_brand: str = "WIX FILTERS",
        supplier_id: int = 324,
        confidence: float = 0.95,
        raw_product_name: str = "Фільтр оливи WIX FILTERS",
        autodb_title: str = "Фільтр оливи",
    ) -> ArticleVariantDiagnosticsRow:
        normalized_brand = raw_brand.upper().replace(" ", "")
        return ArticleVariantDiagnosticsRow(
            supplier="gpl",
            raw_brand=raw_brand,
            normalized_brand=normalized_brand,
            supplier_id=supplier_id,
            raw_article=raw_article,
            normalized_article=raw_article,
            raw_product_name=raw_product_name,
            external_sku=raw_article,
            article_variants=(raw_article, corrected_article_candidate),
            raw_name_alt_tokens=(),
            raw_name_contains_alt_article=True,
            external_sku_looks_like_manufacturer_article=True,
            matched_product_ids=(str(product.id),),
            corrected_article_candidate=corrected_article_candidate,
            corrected_article_source="variant",
            autodb_title=autodb_title,
            lookup_articles=True,
            lookup_article_numbers=True,
            lookup_article_m=False,
            lookup_article_nn=False,
            lookup_article_oe=False,
            lookup_article_cross=False,
            lookup_article_ean=False,
            recommendation="try_variant",
            reason="article_in_raw_name_high_confidence",
            confidence=confidence,
            sample_offer_id="sample-offer-id",
        )

    def _report(self, rows: list[ArticleVariantDiagnosticsRow]) -> ArticleVariantDiagnosticsReport:
        return ArticleVariantDiagnosticsReport(
            supplier="gpl",
            total_raw_offers=len(rows),
            total_pairs=len(rows),
            linked_pairs=0,
            unresolved_pairs=len(rows),
            unresolved_supplier_resolved_pairs=len(rows),
            diagnostics_rows=tuple(rows),
            brand_breakdown=(
                BrandVariantDiagnostics(
                    raw_brand="WIX FILTERS",
                    normalized_brand="WIXFILTERS",
                    supplier_id=324,
                    total_pairs=len(rows),
                    linked_pairs=0,
                    not_found_pairs=0,
                    top_article_patterns=(),
                    raw_name_alt_article_count=len(rows),
                    variant_lookup_would_find_count=len(rows),
                    needs_manual_mapping_count=0,
                ),
            ),
            remote_summary=RemoteDiagnosticsSummary(
                batch_size=1000,
                estimated_remote_queries=0,
                unresolved_pairs=len(rows),
                remote_examples=(),
                remote_not_checked_reason="local_diagnostics_only",
            ),
        )

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_only_remaining_excludes_already_linked_before_limit(self, diagnose_mock):
        diagnose_mock.return_value = self._report(
            [
                self._row(product=self.product_same, raw_article="A1", corrected_article_candidate="WIX001"),
                self._row(product=self.product_safe, raw_article="A2", corrected_article_candidate="WIX777"),
            ]
        )
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--only-remaining",
            "--limit",
            "1",
            "--min-confidence",
            "0.9",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("- status_total_already_linked_same_key: 1", output)
        self.assertIn("- selected_for_run: 1", output)
        self.assertIn("- would_apply: 1", output)
        self.assertIn("- skipped_already_linked: 0", output)

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_dry_run_writes_nothing(self, diagnose_mock):
        diagnose_mock.return_value = self._report([self._row(product=self.product_safe, raw_article="A3", corrected_article_candidate="WIX778")])
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--limit",
            "10",
            "--min-confidence",
            "0.9",
            "--dry-run",
            stdout=out,
        )
        self.product_safe.refresh_from_db()

        self.assertEqual(self.product_safe.catalog_source, Product.CATALOG_SOURCE_LEGACY)
        self.assertEqual(str(self.product_safe.autodb_article_key or ""), "")
        self.assertIn("- applied: 0", out.getvalue())
        self.assertIn("- would_apply: 1", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_safe_remaining_candidate_applies(self, diagnose_mock):
        diagnose_mock.return_value = self._report([self._row(product=self.product_safe, raw_article="A4", corrected_article_candidate="WIX779")])
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--only-remaining",
            "--limit",
            "20",
            "--min-confidence",
            "0.9",
            stdout=out,
        )
        self.product_safe.refresh_from_db()

        self.assertEqual(self.product_safe.autodb_supplier_id, 324)
        self.assertEqual(self.product_safe.autodb_article_number, "WIX779")
        self.assertEqual(self.product_safe.autodb_article_key, "324:WIX779")
        self.assertEqual(self.product_safe.catalog_source, Product.CATALOG_SOURCE_AUTODB_PRO)
        self.assertIn("- applied: 1", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_conflicting_key_skipped(self, diagnose_mock):
        diagnose_mock.return_value = self._report([self._row(product=self.product_conflict, raw_article="A5", corrected_article_candidate="WIX888")])
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--limit",
            "20",
            "--min-confidence",
            "0.9",
            "--dry-run",
            stdout=out,
        )
        self.assertIn("- skipped_conflicting_existing_link: 1", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_suspicious_skipped(self, diagnose_mock):
        diagnose_mock.return_value = self._report([self._row(product=self.product_suspicious, raw_article="A6", corrected_article_candidate="WIX889")])
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--limit",
            "20",
            "--min-confidence",
            "0.9",
            "--dry-run",
            stdout=out,
        )
        self.assertIn("- skipped_suspicious: 1", out.getvalue())

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_price_stock_unchanged_and_utr_not_called(self, diagnose_mock, utr_cls):
        diagnose_mock.return_value = self._report([self._row(product=self.product_safe, raw_article="A7", corrected_article_candidate="WIX890")])
        raw_offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="WIX890",
            article="A7",
            normalized_article="A7",
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            product_name="Фільтр оливи WIX FILTERS",
            price=Decimal("123.45"),
            stock_qty=7,
            matched_product=self.product_safe,
            raw_payload={},
        )
        before_price = raw_offer.price
        before_stock = raw_offer.stock_qty
        before_product_stock = self.product_safe.available_stock_qty_cached
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--only-remaining",
            "--limit",
            "20",
            "--min-confidence",
            "0.9",
            stdout=out,
        )
        raw_offer.refresh_from_db()
        self.product_safe.refresh_from_db()

        self.assertEqual(raw_offer.price, before_price)
        self.assertEqual(raw_offer.stock_qty, before_stock)
        self.assertEqual(self.product_safe.available_stock_qty_cached, before_product_stock)
        self.assertIn("- UTR calls: 0", out.getvalue())
        self.assertIn("- price/stock changed: 0", out.getvalue())
        utr_cls.assert_not_called()

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_brands_and_limit_per_brand_selects_per_brand_without_global_limit(self, diagnose_mock):
        fram_product_1 = self._product(sku="FRAM-1")
        fram_product_2 = self._product(sku="FRAM-2")
        diagnose_mock.return_value = self._report(
            [
                self._row(product=self.product_safe, raw_article="W1", corrected_article_candidate="WIX900", raw_brand="WIX FILTERS", supplier_id=324),
                self._row(product=self.product_conflict, raw_article="W2", corrected_article_candidate="WIX901", raw_brand="WIX FILTERS", supplier_id=324),
                self._row(product=fram_product_1, raw_article="F1", corrected_article_candidate="CA9000", raw_brand="FRAM", supplier_id=59),
                self._row(product=fram_product_2, raw_article="F2", corrected_article_candidate="CA9001", raw_brand="FRAM", supplier_id=59),
            ]
        )
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brands",
            "WIX FILTERS,FRAM",
            "--only-remaining",
            "--limit-per-brand",
            "1",
            "--min-confidence",
            "0.9",
            "--dry-run",
            stdout=out,
        )
        output = out.getvalue()

        self.assertIn("- selected_for_run: 2", output)
        self.assertIn("- would_apply: 2", output)
        self.assertIn("brand=FRAM", output)
        self.assertIn("brand=WIX FILTERS", output)
        self.assertIn("brand=FRAM candidates_total=2", output)
        self.assertIn("brand=WIX FILTERS candidates_total=2", output)

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_brands_filter_excludes_non_selected_brand(self, diagnose_mock):
        fram_product = self._product(sku="FRAM-ONLY-1")
        diagnose_mock.return_value = self._report(
            [
                self._row(product=self.product_safe, raw_article="W3", corrected_article_candidate="WIX902", raw_brand="WIX FILTERS", supplier_id=324),
                self._row(product=fram_product, raw_article="F3", corrected_article_candidate="CA9002", raw_brand="FRAM", supplier_id=59),
            ]
        )
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brands",
            "FRAM",
            "--only-remaining",
            "--limit-per-brand",
            "10",
            "--min-confidence",
            "0.9",
            "--dry-run",
            stdout=out,
        )
        output = out.getvalue()

        self.assertIn("- selected_for_run: 1", output)
        self.assertIn("brand=FRAM", output)
        self.assertNotIn("brand=WIX FILTERS", output)

    @patch("apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose")
    def test_diagnostics_limit_is_passed_to_diagnostics_service(self, diagnose_mock):
        diagnose_mock.return_value = self._report([self._row(product=self.product_safe, raw_article="A8", corrected_article_candidate="WIX903")])
        out = StringIO()

        call_command(
            "autodb_apply_article_variant_links",
            "--supplier",
            "GPL",
            "--brand",
            "WIX FILTERS",
            "--only-remaining",
            "--diagnostics-limit",
            "4321",
            "--dry-run",
            stdout=out,
        )

        diagnose_mock.assert_called_once()
        _, kwargs = diagnose_mock.call_args
        self.assertEqual(kwargs["limit"], 4321)

    def test_only_remaining_dry_run_matches_checkpoint_remaining_for_same_scope(self):
        diagnostics_service = AutoDbArticleVariantDiagnosticsService()
        checkpoint_service = AutoDbArticleVariantApplyCheckpointService(diagnostics_service=diagnostics_service)
        row_same = self._row(product=self.product_same, raw_article="A9", corrected_article_candidate="WIX001")
        row_safe = self._row(product=self.product_safe, raw_article="A10", corrected_article_candidate="WIX904")
        report = self._report([row_same, row_safe])

        diagnostics_service.diagnose = lambda **kwargs: report  # type: ignore[method-assign]
        checkpoint = checkpoint_service.build_report(
            supplier_code="gpl",
            limit=5000,
            brand_filter={"WIXFILTERS"},
            min_confidence=0.9,
        )
        remaining = sum(1 for item in checkpoint.checkpoint_rows if item.status == "safe_to_apply")

        out = StringIO()
        with patch(
            "apps.autodb.management.commands.autodb_apply_article_variant_links.AutoDbArticleVariantDiagnosticsService.diagnose",
            return_value=report,
        ):
            call_command(
                "autodb_apply_article_variant_links",
                "--supplier",
                "GPL",
                "--brand",
                "WIX FILTERS",
                "--only-remaining",
                "--min-confidence",
                "0.9",
                "--limit",
                "20",
                "--diagnostics-limit",
                "5000",
                "--dry-run",
                stdout=out,
            )

        self.assertEqual(remaining, 1)
        output = out.getvalue()
        self.assertIn("- selected_for_run: 1", output)
        self.assertIn("- would_apply: 1", output)
