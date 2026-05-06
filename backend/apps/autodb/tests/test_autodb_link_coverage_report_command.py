from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.raw_offer_enrichment import PairBucket, PairResolution
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbLinkCoverageReportCommandTests(TestCase):
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
        self.brand = Brand.objects.create(name="NGK", slug="ngk")
        self.category = Category.objects.create(name="Spark plugs", slug="spark-plugs")

    def _create_product(self, *, sku: str, linked: bool) -> Product:
        return Product.objects.create(
            sku=sku,
            article=sku,
            slug=f"{sku.lower()}-slug",
            name=f"Product {sku}",
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_supplier_id=1 if linked else None,
            autodb_article_number=sku if linked else "",
            autodb_article_key=f"1:{sku}" if linked else "",
            catalog_source=Product.CATALOG_SOURCE_AUTODB_PRO if linked else Product.CATALOG_SOURCE_LEGACY,
            available_stock_qty_cached=7,
        )

    def _create_offer(
        self,
        *,
        external_sku: str,
        article: str,
        brand: str,
        normalized_brand: str,
        normalized_article: str,
        matched_product: Product | None = None,
        match_status: str = SupplierRawOffer.MATCH_STATUS_UNMATCHED,
        match_reason: str = "",
        stock_qty: int = 1,
        raw_payload: dict | None = None,
    ) -> SupplierRawOffer:
        return SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku=external_sku,
            article=article,
            normalized_article=normalized_article,
            brand_name=brand,
            normalized_brand=normalized_brand,
            product_name=f"{brand} {article}",
            stock_qty=stock_qty,
            matched_product=matched_product,
            match_status=match_status,
            match_reason=match_reason,
            raw_payload=raw_payload or {},
        )

    def _ready_result(self) -> LocalAutoDbReadinessResult:
        return LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        )

    def _fake_signal_summary(self) -> dict[str, int | str]:
        return {
            "unlinked_offers": 0,
            "ean_offers": 0,
            "oe_offers": 0,
            "cross_offers": 0,
            "ean_unique_values": 0,
            "oe_unique_values": 0,
            "cross_unique_values": 0,
            "ean_local_lookup_opportunities": 0,
            "oe_local_lookup_opportunities": 0,
            "cross_local_lookup_opportunities": 0,
            "lookup_mode": "local-only",
        }

    def _resolve_local_chunk(self, buckets: list[PairBucket]) -> list[PairResolution]:
        rows: list[PairResolution] = []
        for bucket in buckets:
            if bucket.normalized_article == "TR5A10":
                rows.append(
                    PairResolution(
                        bucket=bucket,
                        supplier_id=1,
                        canonical_article_number="TR5A-10",
                        article_key="1:TR5A-10",
                        source="local",
                        reason="matched_local",
                    )
                )
            else:
                rows.append(
                    PairResolution(
                        bucket=bucket,
                        supplier_id=1,
                        source="not_found",
                        reason="article_not_found_for_supplier",
                    )
                )
        return rows

    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_local_only_uses_remote_not_checked_status(self, resolve_local_mock, ready_mock, signal_mock):
        self._create_offer(
            external_sku="MISS-1",
            article="MISS-1",
            normalized_article="MISS1",
            brand="NGK",
            normalized_brand="NGK",
        )

        resolve_local_mock.side_effect = self._resolve_local_chunk
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()

        out = StringIO()
        call_command("autodb_link_coverage_report", "--supplier", "GPL", "--sample-not-found", "0", "--sample-linked", "0", stdout=out)

        output = out.getvalue()
        self.assertIn("- local_not_found_remote_not_checked: 1", output)
        self.assertNotIn("remote_disabled", output)

    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_inherited_opportunity_reported_separately(self, resolve_local_mock, ready_mock, signal_mock):
        linked_product = self._create_product(sku="INH-1", linked=True)
        self._create_offer(
            external_sku="INH-1",
            article="INH-1",
            normalized_article="INH1",
            brand="NGK",
            normalized_brand="NGK",
            matched_product=linked_product,
        )

        resolve_local_mock.side_effect = self._resolve_local_chunk
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()

        out = StringIO()
        call_command("autodb_link_coverage_report", "--supplier", "GPL", "--sample-not-found", "0", "--sample-linked", "0", stdout=out)

        output = out.getvalue()
        self.assertIn("- inherited_opportunity: 1", output)
        self.assertIn("- count offers: 1", output)
        self.assertIn("- count unique pairs: 1", output)

    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_suspicious_excluded_from_trusted_coverage(self, resolve_local_mock, ready_mock, signal_mock):
        linked_product = self._create_product(sku="TR5A-10", linked=True)
        AutoDbProductLinkQuality.objects.create(
            product=linked_product,
            autodb_article_key=linked_product.autodb_article_key,
            autodb_supplier_id=1,
            autodb_article_number="TR5A-10",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="test",
        )
        self._create_offer(
            external_sku="TR5A-10",
            article="TR5A-10",
            normalized_article="TR5A10",
            brand="NGK",
            normalized_brand="NGK",
            matched_product=linked_product,
        )

        resolve_local_mock.side_effect = self._resolve_local_chunk
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()

        out = StringIO()
        call_command("autodb_link_coverage_report", "--supplier", "GPL", "--sample-not-found", "0", "--sample-linked", "0", stdout=out)

        output = out.getvalue()
        self.assertIn("- suspicious_link: 1", output)
        self.assertIn("- trusted-product coverage % (linked - suspicious): 0.00", output)

    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_meaningful_only_separates_invalid_and_non_auto(self, resolve_local_mock, ready_mock, signal_mock):
        self._create_offer(
            external_sku="BAD-1",
            article="BAD-1",
            normalized_article="BAD1",
            brand="ТМК",
            normalized_brand="",
        )
        self._create_offer(
            external_sku="CS-1",
            article="CS-1",
            normalized_article="CS1",
            brand="CS SYSTEM",
            normalized_brand="CSSYSTEM",
        )

        resolve_local_mock.side_effect = self._resolve_local_chunk
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()

        out = StringIO()
        call_command(
            "autodb_link_coverage_report",
            "--supplier",
            "GPL",
            "--meaningful-only",
            "--sample-not-found",
            "0",
            "--sample-linked",
            "0",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Meaningful-only filter:", output)
        self.assertIn("- excluded_invalid: 1", output)
        self.assertIn("- excluded_non_auto: 1", output)

    @override_settings(AUTODB_PRO_REMOTE_ENABLED=True)
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_allow_remote_requires_safety_limits(self, resolve_local_mock, ready_mock, signal_mock, remote_ready_mock):
        self._create_offer(
            external_sku="MISS-1",
            article="MISS-1",
            normalized_article="MISS1",
            brand="NGK",
            normalized_brand="NGK",
        )

        resolve_local_mock.side_effect = self._resolve_local_chunk
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()
        remote_ready_mock.return_value = None

        with self.assertRaisesMessage(CommandError, "Remote mode safety"):
            call_command("autodb_link_coverage_report", "--supplier", "GPL", "--allow-remote")

    @override_settings(AUTODB_PRO_REMOTE_ENABLED=True)
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_remote_chunk")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_remote_limit_allows_remote_sample(self, resolve_local_mock, resolve_remote_mock, ready_mock, signal_mock, remote_ready_mock):
        self._create_offer(
            external_sku="MISS-1",
            article="MISS-1",
            normalized_article="MISS1",
            brand="NGK",
            normalized_brand="NGK",
        )

        resolve_local_mock.side_effect = self._resolve_local_chunk
        resolve_remote_mock.return_value = [
            PairResolution(
                bucket=PairBucket(
                    normalized_brand="NGK",
                    normalized_article="MISS1",
                    sample_brand="NGK",
                    sample_article="MISS-1",
                    article_variants=("MISS1",),
                ),
                supplier_id=1,
                canonical_article_number="MISS-1",
                article_key="1:MISS-1",
                source="remote",
                reason="matched_remote",
            )
        ]
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()
        remote_ready_mock.return_value = None

        out = StringIO()
        call_command(
            "autodb_link_coverage_report",
            "--supplier",
            "GPL",
            "--allow-remote",
            "--remote-limit",
            "1",
            "--sample-not-found",
            "0",
            "--sample-linked",
            "0",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Remote mode summary:", output)
        self.assertIn("- remote_checked: True", output)
        resolve_remote_mock.assert_called()

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_remote_chunk")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_read_only_and_utr_not_called(
        self,
        resolve_local_mock,
        resolve_remote_mock,
        ready_mock,
        signal_mock,
        utr_cls,
    ):
        linked_product = self._create_product(sku="NO-WRITE", linked=True)
        offer = self._create_offer(
            external_sku="NO-WRITE",
            article="NO-WRITE",
            normalized_article="NOWRITE",
            brand="NGK",
            normalized_brand="NGK",
            matched_product=linked_product,
            stock_qty=13,
        )

        before_product = Product.objects.get(pk=linked_product.pk)
        before_offer = SupplierRawOffer.objects.get(pk=offer.pk)

        resolve_local_mock.side_effect = self._resolve_local_chunk
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()

        out = StringIO()
        call_command("autodb_link_coverage_report", "--supplier", "GPL", "--sample-not-found", "0", "--sample-linked", "0", stdout=out)

        after_product = Product.objects.get(pk=linked_product.pk)
        after_offer = SupplierRawOffer.objects.get(pk=offer.pk)

        self.assertEqual(after_product.autodb_article_key, before_product.autodb_article_key)
        self.assertEqual(after_product.available_stock_qty_cached, before_product.available_stock_qty_cached)
        self.assertEqual(after_offer.stock_qty, before_offer.stock_qty)
        self.assertEqual(after_offer.price, before_offer.price)
        resolve_remote_mock.assert_not_called()
        utr_cls.assert_not_called()
        self.assertIn("- report_mode: read-only", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_link_coverage_report.Command._compute_ean_oe_cross_opportunities")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_link_coverage_report.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_csv_export_still_works(self, resolve_local_mock, ready_mock, signal_mock):
        linked_product = self._create_product(sku="TR5A-10", linked=True)
        self._create_offer(
            external_sku="TR5A-10",
            article="TR5A-10",
            normalized_article="TR5A10",
            brand="NGK",
            normalized_brand="NGK",
            matched_product=linked_product,
        )

        resolve_local_mock.side_effect = self._resolve_local_chunk
        ready_mock.return_value = self._ready_result()
        signal_mock.return_value = self._fake_signal_summary()

        csv_path = Path("/tmp/autodb_link_coverage_report_test.csv")
        if csv_path.exists():
            csv_path.unlink()

        call_command(
            "autodb_link_coverage_report",
            "--supplier",
            "GPL",
            "--sample-not-found",
            "0",
            "--sample-linked",
            "0",
            "--export-csv",
            str(csv_path),
        )

        self.assertTrue(csv_path.exists())
        body = csv_path.read_text(encoding="utf-8")
        self.assertIn("coverage_status", body)
        self.assertIn("linked_exact_local", body)
