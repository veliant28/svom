from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.management.commands.autodb_audit_inherited_link_opportunities import InheritedAuditRow
from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbApplyInheritedLinksCommandTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="NGK", slug="ngk")
        self.category = Category.objects.create(name="Spark plugs", slug="spark-plugs")
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

    def _product(self, *, sku: str, key: str = "324:WL7042") -> Product:
        return Product.objects.create(
            sku=sku,
            article=sku,
            slug=f"{sku.lower()}-slug",
            name=f"Product {sku}",
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_article_key=key,
            autodb_article_number="",
            autodb_supplier_id=None,
            catalog_source=Product.CATALOG_SOURCE_LEGACY,
            available_stock_qty_cached=10,
        )

    def _row(
        self,
        *,
        product: Product,
        recommendation: str = "can_inherit_high_confidence",
        reason: str = "article_number_in_external_sku",
        raw_brand: str = "WIX FILTERS",
        raw_article: str = "325193",
        suspicious_status: str = "no",
        link_quality_status: str = "unknown",
    ) -> InheritedAuditRow:
        return InheritedAuditRow(
            raw_offer_id="raw-offer-id",
            supplier="gpl",
            raw_brand=raw_brand,
            raw_article=raw_article,
            raw_product_name="Фільтр оливи WIX FILTERS ...",
            matched_product_id=str(product.id),
            matched_product_display_name="Фильтр",
            inherited_autodb_article_key=str(product.autodb_article_key),
            autodb_title="Фильтр",
            autodb_category="",
            link_quality_status=link_quality_status,
            suspicious_status=suspicious_status,
            recommendation=recommendation,
            reason=reason,
            risk_score=20,
            confidence=1.0,
            fitments_excluded_count=0,
        )

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_dry_run_does_not_write(self, ready_mock, load_rows_mock, can_use_mock):
        product = self._product(sku="WL7042")
        load_rows_mock.return_value = [self._row(product=product)]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command("autodb_apply_inherited_links", "--supplier", "GPL", "--limit", "20", "--dry-run", stdout=out)
        product.refresh_from_db()

        self.assertIsNone(product.autodb_supplier_id)
        self.assertEqual(product.autodb_article_number, "")
        self.assertEqual(product.catalog_source, Product.CATALOG_SOURCE_LEGACY)
        self.assertIn("- applied: 0", out.getvalue())
        self.assertIn("- would_apply: 1", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_low_confidence_skipped(self, ready_mock, load_rows_mock, can_use_mock):
        product = self._product(sku="WL7042")
        load_rows_mock.return_value = [self._row(product=product, reason="token_overlap=0.40", recommendation="can_inherit_high_confidence")]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command("autodb_apply_inherited_links", "--supplier", "GPL", "--limit", "20", stdout=out)
        self.assertIn("- skipped_low_confidence: 1", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_needs_manual_review_skipped(self, ready_mock, load_rows_mock, can_use_mock):
        product = self._product(sku="WL7042")
        load_rows_mock.return_value = [self._row(product=product, recommendation="needs_manual_review", reason="low_token_overlap=0.00")]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command("autodb_apply_inherited_links", "--supplier", "GPL", "--limit", "20", stdout=out)
        self.assertIn("- skipped_needs_manual_review: 1", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_suspicious_skipped(self, ready_mock, load_rows_mock, can_use_mock):
        product = self._product(sku="WL7042")
        load_rows_mock.return_value = [self._row(product=product, suspicious_status="yes")]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command("autodb_apply_inherited_links", "--supplier", "GPL", "--limit", "20", stdout=out)
        self.assertIn("- skipped_suspicious: 1", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_trusted_high_confidence_applied(self, ready_mock, load_rows_mock, can_use_mock):
        product = self._product(sku="WL7042")
        load_rows_mock.return_value = [self._row(product=product)]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command("autodb_apply_inherited_links", "--supplier", "GPL", "--limit", "20", stdout=out)
        product.refresh_from_db()

        self.assertEqual(product.autodb_supplier_id, 324)
        self.assertEqual(product.autodb_article_number, "WL7042")
        self.assertEqual(product.autodb_article_key, "324:WL7042")
        self.assertEqual(product.catalog_source, Product.CATALOG_SOURCE_AUTODB_PRO)
        self.assertIn("- applied: 1", out.getvalue())

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_price_stock_unchanged_and_utr_not_called(self, ready_mock, load_rows_mock, can_use_mock, utr_cls):
        product = self._product(sku="WL7042")
        raw_offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="WL7042",
            article="325193",
            normalized_article="325193",
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            product_name="Фільтр оливи WIX FILTERS...",
            price=Decimal("123.45"),
            stock_qty=7,
            matched_product=product,
            raw_payload={},
        )
        before_price = raw_offer.price
        before_stock = raw_offer.stock_qty
        before_prod_stock = product.available_stock_qty_cached

        load_rows_mock.return_value = [self._row(product=product)]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command("autodb_apply_inherited_links", "--supplier", "GPL", "--limit", "20", stdout=out)

        raw_offer.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(raw_offer.price, before_price)
        self.assertEqual(raw_offer.stock_qty, before_stock)
        self.assertEqual(product.available_stock_qty_cached, before_prod_stock)
        self.assertIn("- UTR calls: 0", out.getvalue())
        self.assertIn("- compatibility filtering: disabled/no-op unchanged", out.getvalue())
        utr_cls.assert_not_called()

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_risky_examples_are_skipped_in_output(self, ready_mock, load_rows_mock, can_use_mock):
        p1 = self._product(sku="S1", key="300:820099")
        p2 = self._product(sku="S2", key="300:820099")
        p3 = self._product(sku="S3", key="324:WL7042")
        load_rows_mock.return_value = [
            self._row(product=p1, raw_brand="LSA", raw_article="411124", recommendation="needs_manual_review", reason="low_token_overlap=0.00"),
            self._row(product=p2, raw_brand="MITKA", raw_article="MII107", recommendation="needs_manual_review", reason="low_token_overlap=0.00"),
            self._row(product=p3, raw_brand="WIX FILTERS", raw_article="325193", recommendation="needs_manual_review", reason="low_token_overlap=0.00"),
        ]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command("autodb_apply_inherited_links", "--supplier", "GPL", "--limit", "20", "--dry-run", stdout=out)
        output = out.getvalue()
        self.assertIn("LSA / 411124 / 300:820099: action=skip reason=needs_manual_review", output)
        self.assertIn("MITKA / MII107 / 300:820099: action=skip reason=needs_manual_review", output)
        self.assertIn("WIX FILTERS / 325193 / 324:WL7042: action=skip reason=needs_manual_review", output)

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_only_high_confidence_filters_before_limit(self, ready_mock, load_rows_mock, can_use_mock):
        product_manual = self._product(sku="M1", key="300:820099")
        product_safe = self._product(sku="S1", key="324:WL7042")
        load_rows_mock.return_value = [
            self._row(
                product=product_manual,
                raw_brand="LSA",
                raw_article="411124",
                recommendation="needs_manual_review",
                reason="low_token_overlap=0.00",
            ),
            self._row(
                product=product_safe,
                raw_brand="WIX FILTERS",
                raw_article="325193",
                recommendation="can_inherit_high_confidence",
                reason="article_number_in_raw_name",
            ),
        ]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command(
            "autodb_apply_inherited_links",
            "--supplier",
            "GPL",
            "--only-high-confidence",
            "--order-by",
            "confidence",
            "--limit",
            "1",
            stdout=out,
        )
        product_safe.refresh_from_db()
        output = out.getvalue()
        self.assertEqual(product_safe.autodb_supplier_id, 324)
        self.assertIn("- high_confidence_candidates: 1", output)
        self.assertIn("- safe_candidates: 1", output)
        self.assertIn("- applied: 1", output)

    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.can_use_autodb_fitments_for_public_filtering")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.Command._load_audit_rows")
    @patch("apps.autodb.management.commands.autodb_apply_inherited_links.wait_for_local_autodb_ready")
    def test_brand_filter_limits_scope(self, ready_mock, load_rows_mock, can_use_mock):
        p_wix = self._product(sku="W1", key="324:WL7042")
        p_mann = self._product(sku="M2", key="4:CF1810")
        load_rows_mock.return_value = [
            self._row(
                product=p_wix,
                raw_brand="WIX FILTERS",
                raw_article="325193",
                recommendation="can_inherit_high_confidence",
                reason="article_number_in_raw_name",
            ),
            self._row(
                product=p_mann,
                raw_brand="MANN-FILTER",
                raw_article="TCF 1810",
                recommendation="can_inherit_high_confidence",
                reason="article_number_in_raw_name",
            ),
        ]
        ready_mock.return_value = self._ready_result()
        can_use_mock.return_value = True

        out = StringIO()
        call_command(
            "autodb_apply_inherited_links",
            "--supplier",
            "GPL",
            "--only-high-confidence",
            "--brand",
            "WIX FILTERS",
            "--limit",
            "20",
            "--dry-run",
            stdout=out,
        )
        output = out.getvalue()
        self.assertIn("- candidates_total: 1", output)
        self.assertIn("- high_confidence_candidates: 1", output)
        self.assertIn("- would_apply: 1", output)
