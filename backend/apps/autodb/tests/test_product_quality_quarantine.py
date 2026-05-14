from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.product_quality_quarantine import (
    AutoDbProductQualityQuarantinePlanItem,
    AutoDbProductQualityQuarantineService,
)
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer


class AutoDbProductQualityQuarantineServiceTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.brand = Brand.objects.create(name="POLMO", slug="polmo-quarantine", is_active=True)
        self.category = Category.objects.create(name="Exhaust", slug="exhaust-quarantine", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-QUAR-1",
            svom_sku="SVOM-QUAR-1",
            article="01111",
            name="POLMO Exhaust 01111",
            slug="polmo-exhaust-01111",
            brand=self.brand,
            category=self.category,
            display_brand_name="POLMO",
            autodb_supplier_id=4873,
            is_active=True,
        )
        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.offer = SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=4,
            lead_time_days=0,
            is_available=True,
        )
        self.service = AutoDbProductQualityQuarantineService()

    def test_apply_plan_dry_run_then_apply_then_repeat_is_idempotent(self):
        plan = [
            AutoDbProductQualityQuarantinePlanItem(
                product_id=str(self.product.id),
                status="skipped_split_product_candidate",
                reason="split_product_candidate",
                sku="SVOM-QUAR-1",
                bucket="split_product_candidate",
            )
        ]
        before_jobs = AutoDbMatchJob.objects.count()
        before_evidence = AutoDbMatchEvidence.objects.count()

        dry_rows, dry_summary = self.service.apply_plan(plan=plan, dry_run=True)
        self.assertEqual(len(dry_rows), 1)
        self.assertEqual(dry_rows[0].action, "would_create")
        self.assertEqual(dry_summary["would_create"], 1)
        self.assertEqual(AutoDbMatchJob.objects.count(), before_jobs)
        self.assertEqual(AutoDbMatchEvidence.objects.count(), before_evidence)

        apply_rows, apply_summary = self.service.apply_plan(plan=plan, dry_run=False)
        self.assertEqual(len(apply_rows), 1)
        self.assertEqual(apply_rows[0].action, "created")
        self.assertEqual(apply_summary["jobs_affected"], 1)
        self.assertEqual(AutoDbMatchJob.objects.count(), before_jobs + 1)
        self.assertEqual(AutoDbMatchEvidence.objects.count(), before_evidence + 1)
        created = AutoDbMatchJob.objects.filter(product=self.product, supplier_offer__isnull=True).first()
        self.assertIsNotNone(created)
        self.assertEqual(str(created.status), "skipped_split_product_candidate")
        self.assertEqual(str(created.article_source_type), "product_quality_quarantine")

        repeat_rows, repeat_summary = self.service.apply_plan(plan=plan, dry_run=True)
        self.assertEqual(len(repeat_rows), 1)
        self.assertEqual(repeat_rows[0].action, "skipped_already_quarantined")
        self.assertEqual(repeat_summary["would_update"], 0)
        self.assertEqual(repeat_summary["skipped_already_quarantined"], 1)


class AutoDbMatchJobBuilderQuarantineTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        brand = Brand.objects.create(name="POLMO", slug="polmo-builder-quarantine", is_active=True)
        category = Category.objects.create(name="Exhaust", slug="exhaust-builder-quarantine", is_active=True)
        self.product = Product.objects.create(
            sku="SKU-BUILD-QUAR-1",
            article="01111",
            name="POLMO Exhaust",
            slug="polmo-exhaust-builder",
            brand=brand,
            category=category,
            display_brand_name="POLMO",
            autodb_supplier_id=4873,
            is_active=True,
        )
        gpl = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        utr = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.offer_a = SupplierOffer.objects.create(
            supplier=gpl,
            product=self.product,
            supplier_sku="01111",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=3,
            lead_time_days=0,
            is_available=True,
        )
        self.offer_b = SupplierOffer.objects.create(
            supplier=utr,
            product=self.product,
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="500.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=1,
            lead_time_days=0,
            is_available=True,
        )
        AutoDbMatchJob.objects.create(
            product=self.product,
            supplier_offer=None,
            supplier_code="",
            raw_brand="POLMO",
            normalized_brand="POLMO",
            resolved_supplier_id=4873,
            article_source_type="product_quality_quarantine",
            article_value="",
            canonical_article="",
            status="skipped_split_product_candidate",
            last_error="split_product_candidate",
            metadata_json={
                "quarantine": {
                    "active": True,
                    "status": "skipped_split_product_candidate",
                    "reason": "split_product_candidate",
                }
            },
        )

    def test_builder_uses_product_level_quarantine_state(self):
        article_resolver = SimpleNamespace(
            resolve=lambda **kwargs: SimpleNamespace(  # noqa: ARG005
                is_usable=True,
                source_type="payload_manufacturer_article",
                article_value="01111",
                canonical_article="01111",
                reason="",
                confidence=1.0,
            )
        )
        brand_resolver = SimpleNamespace(
            resolve=lambda **kwargs: SimpleNamespace(  # noqa: ARG005
                is_mapped=True,
                supplier_id=4873,
                normalized_brand="POLMO",
                decision="mapped",
                reason="ok",
                resolver_source="exact_supplier",
            )
        )
        builder = AutoDbMatchJobBuilder(article_resolver=article_resolver, brand_resolver=brand_resolver)

        rows = builder.build_jobs(supplier_code="", limit=10, dry_run=True)
        target_rows = [row for row in rows if str(row.product_id) == str(self.product.id)]
        self.assertEqual(len(target_rows), 2)
        self.assertTrue(all(row.status == "skipped_split_product_candidate" for row in target_rows))
        self.assertTrue(all(row.resolver_source == "product_quality_quarantine" for row in target_rows))
