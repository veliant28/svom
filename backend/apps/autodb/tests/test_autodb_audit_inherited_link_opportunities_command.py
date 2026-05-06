from __future__ import annotations

from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.raw_offer_enrichment import PairBucket, PairResolution
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbAuditInheritedLinkOpportunitiesCommandTests(TestCase):
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

    def _create_product(self, *, sku: str, name: str = "Свічка запалювання", linked: bool = True) -> Product:
        return Product.objects.create(
            sku=sku,
            article=sku,
            slug=f"{sku.lower()}-slug",
            name=name,
            brand=self.brand,
            category=self.category,
            is_active=True,
            autodb_supplier_id=1 if linked else None,
            autodb_article_number=sku if linked else "",
            autodb_article_key=f"1:{sku}" if linked else "",
            catalog_source=Product.CATALOG_SOURCE_AUTODB_PRO if linked else Product.CATALOG_SOURCE_LEGACY,
            available_stock_qty_cached=9,
        )

    def _create_offer(
        self,
        *,
        external_sku: str,
        article: str,
        product_name: str,
        matched_product: Product,
        brand_name: str = "NGK",
        normalized_brand: str = "NGK",
        normalized_article: str = "",
        price: Decimal = Decimal("99.99"),
        stock_qty: int = 4,
    ) -> SupplierRawOffer:
        return SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku=external_sku,
            article=article,
            normalized_article=normalized_article or article.replace("-", ""),
            brand_name=brand_name,
            normalized_brand=normalized_brand,
            product_name=product_name,
            matched_product=matched_product,
            price=price,
            stock_qty=stock_qty,
            raw_payload={},
        )

    def _resolve_local_unlinked(self, buckets: list[PairBucket]) -> list[PairResolution]:
        return [
            PairResolution(
                bucket=bucket,
                supplier_id=1,
                source="not_found",
                reason="article_not_found_for_supplier",
            )
            for bucket in buckets
        ]

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_trusted_product_classified_as_high_confidence_can_inherit(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
        utr_client_cls,
    ):
        product = self._create_product(sku="TR5A-10")
        self._create_offer(
            external_sku="TR5A-10",
            article="TR5A-10",
            product_name="Свічка запалювання NGK TR5A-10",
            matched_product=product,
        )

        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Spark Plug TR5A-10", "autodb_category": "Spark plugs"}

        out = StringIO()
        call_command("autodb_audit_inherited_link_opportunities", "--supplier", "GPL", "--limit", "1000", stdout=out)

        output = out.getvalue()
        self.assertIn("- high_confidence_can_inherit: 1", output)
        self.assertIn("recommendation=can_inherit_high_confidence", output)
        self.assertIn("- UTR calls: 0", output)
        focused_mock.assert_called_once()
        utr_client_cls.assert_not_called()

    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_suspicious_product_is_blocked(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
    ):
        product = self._create_product(sku="BPR7ES-11")
        AutoDbProductLinkQuality.objects.create(
            product=product,
            autodb_article_key=product.autodb_article_key,
            autodb_supplier_id=1,
            autodb_article_number="BPR7ES-11",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="test",
        )
        ProductFitment.objects.create(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_article_key=product.autodb_article_key,
            excluded_from_public_filtering=True,
        )
        self._create_offer(
            external_sku="BPR7ES-11",
            article="BPR7ES-11",
            product_name="Свічка запалювання BPR7ES-11",
            matched_product=product,
        )

        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Spark Plug BPR7ES-11", "autodb_category": "Spark plugs"}

        out = StringIO()
        call_command("autodb_audit_inherited_link_opportunities", "--supplier", "GPL", "--limit", "1000", stdout=out)
        output = out.getvalue()
        self.assertIn("- suspicious_do_not_inherit: 1", output)
        self.assertIn("- blocked_by_suspicious_quality: 1", output)
        self.assertIn("- count fitments excluded: 1", output)
        focused_mock.assert_called_once()

    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_mismatched_title_category_becomes_manual_review(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
    ):
        product = self._create_product(sku="WL7042", name="Свічка запалювання")
        wix_brand = Brand.objects.create(name="WIX FILTERS", slug="wix-filters-test")
        product.brand = wix_brand
        product.save(update_fields=("brand", "updated_at"))
        self._create_offer(
            external_sku="NO-SKU",
            article="325193",
            product_name="Фільтр оливи для двигуна",
            matched_product=product,
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            normalized_article="325193",
        )

        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Brake Drum Set", "autodb_category": "Suspension components"}

        out = StringIO()
        call_command("autodb_audit_inherited_link_opportunities", "--supplier", "GPL", "--limit", "1000", stdout=out)
        output = out.getvalue()
        self.assertIn("- needs_manual_review: 1", output)
        self.assertIn("recommendation=needs_manual_review", output)
        focused_mock.assert_called_once()

    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_article_number_in_external_sku_is_high_confidence(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
    ):
        product = self._create_product(sku="WL7042", name="Фильтр")
        wix_brand = Brand.objects.create(name="WIX FILTERS", slug="wix-filters-ext")
        product.brand = wix_brand
        product.save(update_fields=("brand", "updated_at"))
        self._create_offer(
            external_sku="WL7042",
            article="325193",
            product_name="Фільтр оливи WIX FILTERS",
            matched_product=product,
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            normalized_article="325193",
        )
        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Фильтр", "autodb_category": "Filters"}

        out = StringIO()
        call_command("autodb_audit_inherited_link_opportunities", "--supplier", "GPL", "--limit", "1000", stdout=out)
        output = out.getvalue()
        self.assertIn("recommendation=can_inherit_high_confidence", output)
        self.assertIn("reason=article_number_in_external_sku", output)
        focused_mock.assert_called_once()

    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_article_number_in_raw_name_is_high_confidence(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
    ):
        product = self._create_product(sku="WL7042", name="Фильтр")
        wix_brand = Brand.objects.create(name="WIX FILTERS", slug="wix-filters-name")
        product.brand = wix_brand
        product.save(update_fields=("brand", "updated_at"))
        self._create_offer(
            external_sku="NO-MATCH",
            article="325193",
            product_name="Фільтр оливи WIX FILTERS BMW (WL-7042)",
            matched_product=product,
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            normalized_article="325193",
        )
        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Фильтр", "autodb_category": "Filters"}

        out = StringIO()
        call_command("autodb_audit_inherited_link_opportunities", "--supplier", "GPL", "--limit", "1000", stdout=out)
        output = out.getvalue()
        self.assertIn("recommendation=can_inherit_high_confidence", output)
        self.assertIn("reason=article_number_in_raw_name", output)
        focused_mock.assert_called_once()

    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_mitka_semantic_conflict_stays_manual_review(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
    ):
        product = self._create_product(sku="820099", name="Шарнирный комплект")
        product.autodb_article_key = "300:820099"
        product.autodb_supplier_id = 300
        product.save(update_fields=("autodb_article_key", "autodb_supplier_id", "updated_at"))
        self._create_offer(
            external_sku="MII107",
            article="MII107",
            product_name="Емаль автомобільна MITKA Буран металік аерозоль 400 мл (MII107)",
            matched_product=product,
            brand_name="MITKA",
            normalized_brand="MITKA",
            normalized_article="MII107",
        )
        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Шарнирный комплект", "autodb_category": "Шарнирный комплект"}

        out = StringIO()
        call_command("autodb_audit_inherited_link_opportunities", "--supplier", "GPL", "--limit", "1000", stdout=out)
        output = out.getvalue()
        self.assertIn("recommendation=needs_manual_review", output)
        self.assertIn("semantic_conflict_supplier_non_part_vs_autodb_part", output)
        focused_mock.assert_called_once()

    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_csv_export_works(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
    ):
        product = self._create_product(sku="TR5A-10")
        self._create_offer(
            external_sku="TR5A-10",
            article="TR5A-10",
            product_name="Свічка запалювання NGK TR5A-10",
            matched_product=product,
        )

        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Spark Plug TR5A-10", "autodb_category": "Spark plugs"}

        csv_path = Path("/tmp/gpl_inherited_audit_test.csv")
        if csv_path.exists():
            csv_path.unlink()

        call_command(
            "autodb_audit_inherited_link_opportunities",
            "--supplier",
            "GPL",
            "--limit",
            "1000",
            "--export-csv",
            str(csv_path),
        )
        self.assertTrue(csv_path.exists())
        content = csv_path.read_text(encoding="utf-8")
        self.assertIn("supplier,raw_brand,raw_article,raw_product_name,matched_product_id", content)
        self.assertIn("gpl,NGK,TR5A-10", content)
        focused_mock.assert_called_once()

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._print_focused_cases")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.Command._lookup_autodb_context")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.wait_for_local_autodb_ready")
    @patch("apps.autodb.management.commands.autodb_audit_inherited_link_opportunities.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_report_is_read_only_and_price_stock_unchanged(
        self,
        resolve_local_mock,
        ready_mock,
        lookup_mock,
        focused_mock,
        utr_client_cls,
    ):
        product = self._create_product(sku="RC-AD216")
        offer = self._create_offer(
            external_sku="RC-AD216",
            article="0516",
            product_name="Комплект проводів RC-AD216",
            matched_product=product,
            brand_name="NGK",
            normalized_brand="NGK",
            normalized_article="0516",
            price=Decimal("2048.86"),
            stock_qty=6,
        )

        before_product_count = Product.objects.count()
        before_offer_count = SupplierRawOffer.objects.count()
        before_supplier_offer_count = SupplierOffer.objects.count()
        before_product_updated = product.updated_at
        before_offer_updated = offer.updated_at
        before_product_stock = product.available_stock_qty_cached
        before_offer_price = offer.price
        before_offer_stock = offer.stock_qty
        before_key = product.autodb_article_key

        resolve_local_mock.side_effect = self._resolve_local_unlinked
        ready_mock.return_value = self._ready_result()
        lookup_mock.return_value = {"autodb_title": "Ignition wire set RC-AD216", "autodb_category": "Ignition"}

        out = StringIO()
        call_command("autodb_audit_inherited_link_opportunities", "--supplier", "GPL", "--limit", "1000", stdout=out)

        product.refresh_from_db()
        offer.refresh_from_db()

        self.assertEqual(Product.objects.count(), before_product_count)
        self.assertEqual(SupplierRawOffer.objects.count(), before_offer_count)
        self.assertEqual(SupplierOffer.objects.count(), before_supplier_offer_count)
        self.assertEqual(product.updated_at, before_product_updated)
        self.assertEqual(offer.updated_at, before_offer_updated)
        self.assertEqual(product.available_stock_qty_cached, before_product_stock)
        self.assertEqual(offer.price, before_offer_price)
        self.assertEqual(offer.stock_qty, before_offer_stock)
        self.assertEqual(product.autodb_article_key, before_key)
        self.assertIn("- report_mode: read-only (no Product/SupplierRawOffer writes)", out.getvalue())
        focused_mock.assert_called_once()
        utr_client_cls.assert_not_called()
