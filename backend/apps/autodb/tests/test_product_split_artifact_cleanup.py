from __future__ import annotations

from django.test import TestCase

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.autodb.services.matching.product_split_artifact_cleanup import AutoDbSplitArtifactCleanupService
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer


class AutoDbSplitArtifactCleanupServiceTests(TestCase):
    databases = {"default"}

    def setUp(self):
        brand = Brand.objects.create(name="FEBI BILSTEIN", slug="febi-cleanup", is_active=True)
        category = Category.objects.create(name="Exhaust", slug="exhaust-cleanup", is_active=True)
        self.product = Product.objects.create(
            sku="ORPHAN-SPLIT-1",
            article="01111",
            name="Orphan split",
            slug="orphan-split-1",
            brand=brand,
            category=category,
            is_active=False,
            display_brand_name="FEBI BILSTEIN",
        )
        self.service = AutoDbSplitArtifactCleanupService()

    def test_deletes_safe_orphan_product(self):
        plan = self.service.plan(product_id=str(self.product.id))
        self.assertTrue(plan.clean)
        self.assertTrue(plan.would_delete_product)
        self.assertFalse(plan.would_keep_inactive_and_ignore)

        result = self.service.apply(product_id=str(self.product.id))
        self.assertTrue(result.deleted)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_applies_ignore_marker_when_dependencies_exist(self):
        supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        SupplierOffer.objects.create(
            supplier=supplier,
            product=self.product,
            supplier_sku="FE01111",
            currency="UAH",
            purchase_price="100.00",
            price_levels=[],
            logistics_cost="0.00",
            extra_cost="0.00",
            stock_qty=0,
            lead_time_days=0,
            is_available=False,
        )

        plan = self.service.plan(product_id=str(self.product.id))
        self.assertTrue(plan.clean)
        self.assertFalse(plan.would_delete_product)
        self.assertTrue(plan.would_keep_inactive_and_ignore)

        before_jobs = AutoDbMatchJob.objects.count()
        before_evidence = AutoDbMatchEvidence.objects.count()
        result = self.service.apply(product_id=str(self.product.id))
        self.assertFalse(result.deleted)
        self.assertTrue(result.ignored_marker_applied)
        self.assertEqual(AutoDbMatchJob.objects.count(), before_jobs + 1)
        self.assertEqual(AutoDbMatchEvidence.objects.count(), before_evidence + 1)

        job = AutoDbMatchJob.objects.get(id=result.service_job_id)
        marker = (job.metadata_json or {}).get("split_artifact_cleanup", {})
        self.assertTrue(bool(marker.get("ignore_as_artifact")))
