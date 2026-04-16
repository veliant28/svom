from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.services import ImportQualityService


class ImportQualityServiceTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="ARAL", slug="aral", is_active=True)
        category = Category.objects.create(name="Oils", slug="oils", is_active=True)
        self.product = Product.objects.create(
            sku="AR-20488",
            article="AR-20488",
            name="Aral",
            slug="aral",
            brand=brand,
            category=category,
            is_active=True,
        )
        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
        )

    def _create_raw_offer(self, *, run: ImportRun, status: str, reason: str = ""):
        SupplierRawOffer.objects.create(
            run=run,
            source=self.source,
            supplier=self.source.supplier,
            external_sku=f"SKU-{status}-{reason or 'x'}-{run.id}",
            article="AR-20488",
            normalized_article="AR20488",
            brand_name="ARAL",
            normalized_brand="ARAL",
            product_name="Aral",
            currency="UAH",
            price=Decimal("100.00"),
            stock_qty=1,
            match_status=status,
            match_reason=reason,
            matched_product=self.product if status in {SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED, SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED} else None,
            is_valid=status in {SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED, SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED},
            skip_reason=reason,
        )

    def test_quality_metrics_and_comparison_flags(self):
        previous = ImportRun.objects.create(
            source=self.source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            processed_rows=10,
            errors_count=1,
        )
        for _ in range(6):
            self._create_raw_offer(run=previous, status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)
        ImportQualityService().refresh_for_run(run=previous)

        current = ImportRun.objects.create(
            source=self.source,
            status=ImportRun.STATUS_PARTIAL,
            trigger="test",
            processed_rows=10,
            errors_count=2,
        )
        for _ in range(3):
            self._create_raw_offer(run=current, status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)
        self._create_raw_offer(run=current, status=SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED)
        for _ in range(2):
            self._create_raw_offer(
                run=current,
                status=SupplierRawOffer.MATCH_STATUS_UNMATCHED,
                reason=SupplierRawOffer.MATCH_REASON_ARTICLE_CONFLICT,
            )
        self._create_raw_offer(
            run=current,
            status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED,
            reason=SupplierRawOffer.MATCH_REASON_AMBIGUOUS,
        )
        self._create_raw_offer(run=current, status=SupplierRawOffer.MATCH_STATUS_IGNORED)

        result = ImportQualityService().refresh_for_run(run=current)
        quality = result.quality

        self.assertEqual(quality.total_rows, 10)
        self.assertEqual(quality.matched_rows, 4)
        self.assertEqual(float(quality.match_rate), 40.0)
        self.assertEqual(float(quality.error_rate), 20.0)
        self.assertTrue(quality.requires_operator_attention)
        codes = {item.get("code") for item in quality.flags}
        self.assertIn("match_rate_drop", codes)
        self.assertIn("error_rate_high", codes)

    def test_category_mapping_quality_mode_uses_category_statuses(self):
        run = ImportRun.objects.create(
            source=self.source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="command:import_categorized_supplier_prices",
            processed_rows=10,
            errors_count=0,
            summary={
                "quality_mode": "category_mapping",
                "category_total_rows": 10,
                "category_status_counts": {
                    SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED: 8,
                    SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED: 1,
                    SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW: 1,
                    SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED: 0,
                },
            },
        )

        result = ImportQualityService().refresh_for_run(run=run)
        quality = result.quality

        self.assertEqual(quality.total_rows, 10)
        self.assertEqual(quality.manual_matched_rows, 8)
        self.assertEqual(quality.auto_matched_rows, 1)
        self.assertEqual(quality.conflict_rows, 1)
        self.assertEqual(quality.unmatched_rows, 0)
        self.assertEqual(quality.matched_rows, 10)
        self.assertEqual(float(quality.match_rate), 100.0)
        self.assertEqual(float(quality.error_rate), 0.0)
        self.assertFalse(quality.requires_operator_attention)
