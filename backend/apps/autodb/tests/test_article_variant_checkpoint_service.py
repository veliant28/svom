from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase

from apps.autodb.services.article_variant_checkpoint import AutoDbArticleVariantApplyCheckpointService
from apps.autodb.services.article_variant_diagnostics import (
    ArticleVariantDiagnosticsReport,
    ArticleVariantDiagnosticsRow,
    BrandVariantDiagnostics,
    RemoteDiagnosticsSummary,
)
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class ArticleVariantCheckpointServiceTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="checkpoint-brand", is_active=True)
        self.category = Category.objects.create(name="Category", slug="checkpoint-category", is_active=True)
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

        self.product_same = Product.objects.create(
            sku="CHK-SAME",
            article="CHK-SAME",
            slug="chk-same",
            name="Фільтр",
            name_uk="Фільтр",
            name_ru="Фильтр",
            name_en="Filter",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=324,
            autodb_article_number="WA1234",
            autodb_article_key="324:WA1234",
            is_active=True,
        )
        self.product_conflict = Product.objects.create(
            sku="CHK-CONFLICT",
            article="CHK-CONFLICT",
            slug="chk-conflict",
            name="Фільтр",
            name_uk="Фільтр",
            name_ru="Фильтр",
            name_en="Filter",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=324,
            autodb_article_number="OLD999",
            autodb_article_key="324:OLD999",
            is_active=True,
        )
        self.product_safe = Product.objects.create(
            sku="CHK-SAFE",
            article="CHK-SAFE",
            slug="chk-safe",
            name="Фільтр",
            name_uk="Фільтр",
            name_ru="Фильтр",
            name_en="Filter",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.product_suspicious = Product.objects.create(
            sku="CHK-SUSP",
            article="CHK-SUSP",
            slug="chk-susp",
            name="Резонатор POLMO",
            name_uk="Резонатор POLMO",
            name_ru="Резонатор POLMO",
            name_en="POLMO resonator",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=4873,
            autodb_article_number="17.18",
            autodb_article_key="4873:17.18",
            is_active=True,
        )

        ProductFitment.objects.create(
            product=self.product_suspicious,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=1,
            linkage_type="PassengerCar",
            autodb_article_key="4873:17.18",
            supplier_id=4873,
            article_number="17.18",
            excluded_from_public_filtering=True,
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.product_suspicious,
            autodb_article_key="4873:17.18",
            autodb_supplier_id=4873,
            autodb_article_number="17.18",
            status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            reason="suspicious_link",
        )

        self.offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="123",
            article="123",
            normalized_article="123",
            brand_name="WIX FILTERS",
            normalized_brand="WIXFILTERS",
            product_name="Фільтр WIX FILTERS",
            price=Decimal("10.00"),
            stock_qty=3,
            raw_payload={},
        )

    def _report(self) -> ArticleVariantDiagnosticsReport:
        rows = (
            ArticleVariantDiagnosticsRow(
                supplier="gpl",
                raw_brand="WIX FILTERS",
                normalized_brand="WIXFILTERS",
                supplier_id=324,
                raw_article="123",
                normalized_article="123",
                raw_product_name="Фільтр WIX FILTERS",
                external_sku="123",
                article_variants=("123", "WA1234"),
                raw_name_alt_tokens=(),
                raw_name_contains_alt_article=False,
                external_sku_looks_like_manufacturer_article=False,
                matched_product_ids=(str(self.product_same.id),),
                corrected_article_candidate="WA1234",
                corrected_article_source="variant",
                autodb_title="Фильтр",
                lookup_articles=True,
                lookup_article_numbers=True,
                lookup_article_m=False,
                lookup_article_nn=False,
                lookup_article_oe=False,
                lookup_article_cross=False,
                lookup_article_ean=False,
                recommendation="try_variant",
                reason="variant_matches_supplier_article",
                confidence=0.90,
                sample_offer_id=str(self.offer.id),
            ),
            ArticleVariantDiagnosticsRow(
                supplier="gpl",
                raw_brand="WIX FILTERS",
                normalized_brand="WIXFILTERS",
                supplier_id=324,
                raw_article="124",
                normalized_article="124",
                raw_product_name="Фільтр WIX FILTERS",
                external_sku="124",
                article_variants=("124", "WA9999"),
                raw_name_alt_tokens=(),
                raw_name_contains_alt_article=False,
                external_sku_looks_like_manufacturer_article=False,
                matched_product_ids=(str(self.product_conflict.id),),
                corrected_article_candidate="WA9999",
                corrected_article_source="variant",
                autodb_title="Фильтр",
                lookup_articles=True,
                lookup_article_numbers=True,
                lookup_article_m=False,
                lookup_article_nn=False,
                lookup_article_oe=False,
                lookup_article_cross=False,
                lookup_article_ean=False,
                recommendation="try_variant",
                reason="variant_matches_supplier_article",
                confidence=0.90,
                sample_offer_id=str(self.offer.id),
            ),
            ArticleVariantDiagnosticsRow(
                supplier="gpl",
                raw_brand="WIX FILTERS",
                normalized_brand="WIXFILTERS",
                supplier_id=324,
                raw_article="125",
                normalized_article="125",
                raw_product_name="Фільтр WIX FILTERS",
                external_sku="125",
                article_variants=("125", "WA7777"),
                raw_name_alt_tokens=(),
                raw_name_contains_alt_article=False,
                external_sku_looks_like_manufacturer_article=False,
                matched_product_ids=(str(self.product_safe.id),),
                corrected_article_candidate="WA7777",
                corrected_article_source="variant",
                autodb_title="Фильтр",
                lookup_articles=True,
                lookup_article_numbers=True,
                lookup_article_m=False,
                lookup_article_nn=False,
                lookup_article_oe=False,
                lookup_article_cross=False,
                lookup_article_ean=False,
                recommendation="try_variant",
                reason="variant_matches_supplier_article",
                confidence=0.90,
                sample_offer_id=str(self.offer.id),
            ),
            ArticleVariantDiagnosticsRow(
                supplier="gpl",
                raw_brand="POLMO",
                normalized_brand="POLMO",
                supplier_id=4873,
                raw_article="851718",
                normalized_article="851718",
                raw_product_name="Резонатор POLMO",
                external_sku="851718",
                article_variants=("851718", "17.18"),
                raw_name_alt_tokens=(),
                raw_name_contains_alt_article=False,
                external_sku_looks_like_manufacturer_article=False,
                matched_product_ids=(str(self.product_suspicious.id),),
                corrected_article_candidate="17.18",
                corrected_article_source="variant",
                autodb_title="Амортизатор",
                lookup_articles=True,
                lookup_article_numbers=True,
                lookup_article_m=False,
                lookup_article_nn=False,
                lookup_article_oe=False,
                lookup_article_cross=False,
                lookup_article_ean=False,
                recommendation="try_variant",
                reason="variant_matches_supplier_article",
                confidence=0.90,
                sample_offer_id=str(self.offer.id),
            ),
        )
        breakdown = (
            BrandVariantDiagnostics(
                raw_brand="WIX FILTERS",
                normalized_brand="WIXFILTERS",
                supplier_id=324,
                total_pairs=3,
                linked_pairs=1,
                not_found_pairs=2,
                top_article_patterns=("numeric_only",),
                raw_name_alt_article_count=0,
                variant_lookup_would_find_count=3,
                needs_manual_mapping_count=0,
            ),
            BrandVariantDiagnostics(
                raw_brand="POLMO",
                normalized_brand="POLMO",
                supplier_id=4873,
                total_pairs=1,
                linked_pairs=0,
                not_found_pairs=1,
                top_article_patterns=("numeric_only",),
                raw_name_alt_article_count=0,
                variant_lookup_would_find_count=1,
                needs_manual_mapping_count=0,
            ),
        )
        remote = RemoteDiagnosticsSummary(
            batch_size=1000,
            estimated_remote_queries=0,
            unresolved_pairs=4,
            remote_examples=(),
            remote_not_checked_reason="local_diagnostics_only",
        )
        return ArticleVariantDiagnosticsReport(
            supplier="gpl",
            total_raw_offers=4,
            total_pairs=4,
            linked_pairs=0,
            unresolved_pairs=4,
            unresolved_supplier_resolved_pairs=4,
            diagnostics_rows=rows,
            brand_breakdown=breakdown,
            remote_summary=remote,
        )

    def test_checkpoint_separates_same_key_conflict_safe_and_suspicious(self):
        diagnostics_service = Mock()
        diagnostics_service.diagnose.return_value = self._report()
        service = AutoDbArticleVariantApplyCheckpointService(diagnostics_service=diagnostics_service)

        before_key = self.product_safe.autodb_article_key
        report = service.build_report(supplier_code="gpl", limit=100, min_confidence=0.9)

        rows = {(row.raw_brand, row.raw_article, row.product_id): row for row in report.checkpoint_rows}
        self.assertEqual(
            rows[("WIX FILTERS", "123", str(self.product_same.id))].status,
            service.STATUS_ALREADY_LINKED_SAME_KEY,
        )
        self.assertEqual(
            rows[("WIX FILTERS", "124", str(self.product_conflict.id))].status,
            service.STATUS_ALREADY_LINKED_CONFLICTING_KEY,
        )
        self.assertEqual(
            rows[("WIX FILTERS", "125", str(self.product_safe.id))].status,
            service.STATUS_SAFE_TO_APPLY,
        )
        self.assertEqual(
            rows[("POLMO", "851718", str(self.product_suspicious.id))].status,
            service.STATUS_SKIPPED_SUSPICIOUS,
        )

        wix_summary = next(item for item in report.brand_summaries if item.normalized_brand == "WIXFILTERS")
        self.assertEqual(wix_summary.already_linked_same_key, 1)
        self.assertEqual(wix_summary.already_linked_conflicting_key, 1)
        self.assertEqual(wix_summary.remaining_safe_to_apply, 1)

        polmo_summary = next(item for item in report.brand_summaries if item.normalized_brand == "POLMO")
        self.assertEqual(polmo_summary.recommended_next_action, "review_only")
        self.assertEqual(report.polmo_summary.suspicious, 1)
        self.assertEqual(report.polmo_summary.related_to_known_suspicious_products, 1)
        self.assertEqual(report.polmo_summary.exhaust_to_shock_risk, 1)

        self.product_safe.refresh_from_db()
        self.assertEqual(self.product_safe.autodb_article_key, before_key)

