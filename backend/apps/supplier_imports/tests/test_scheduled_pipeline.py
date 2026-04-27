from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierIntegration
from apps.supplier_imports.services.scheduling.pipeline import ScheduledSupplierImportPipelineService


class ScheduledSupplierImportPipelineTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="ARAL", slug="aral", is_active=True)
        self.category = Category.objects.create(name="Oils", slug="oils", is_active=True)
        self.product = Product.objects.create(
            sku="AR-20488",
            article="AR-20488",
            name="Aral BlueTronic 10W-40 1Lx12",
            slug="aral-bluetronic-10w40-1l",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.source = ImportSource.objects.create(
            code="utr",
            name="UTR",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_UTR,
            parser_options={"persistence_mode": "current_offers"},
            input_path="",
            is_active=True,
            is_auto_import_enabled=True,
            auto_reprice_after_import=True,
            auto_reindex_after_import=True,
        )
        SupplierIntegration.objects.create(
            supplier=self.supplier,
            source=self.source,
            is_enabled=True,
            access_token="token",
        )

    def test_current_offers_pipeline_skips_raw_publish_and_reprices_reindexes_delta(self):
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="0007523",
            purchase_price=Decimal("140.24"),
            stock_qty=95,
            is_available=True,
        )
        run = ImportRun.objects.create(
            source=self.source,
            status=ImportRun.STATUS_PARTIAL,
            trigger="test",
            summary={"persistence_mode": "current_offers"},
        )

        workspace_service = MagicMock()
        price_workflow = MagicMock()
        indexer = MagicMock()
        indexer.reindex_products.return_value = {
            "indexed": 1,
            "errors": 0,
            "total": 1,
            "backend": "test",
        }
        service = ScheduledSupplierImportPipelineService()
        product_ids = [str(self.product.id)]

        with (
            patch(
                "apps.backoffice.services.supplier_workspace_service.SupplierWorkspaceService",
                return_value=workspace_service,
            ),
            patch(
                "apps.backoffice.services.supplier_price_workflow_service.SupplierPriceWorkflowService",
                return_value=price_workflow,
            ),
            patch("apps.supplier_imports.services.scheduling.pipeline.ProductIndexer", return_value=indexer),
            patch.object(service, "_ensure_token", return_value={"mode": "noop", "status": "ok"}),
            patch.object(service, "_request_with_cooldown_retry", return_value={"id": "price-list-1"}),
            patch.object(service, "_download_with_polling", return_value={"status": "downloaded"}),
            patch.object(
                service,
                "_import_with_cooldown_retry",
                return_value={
                    "run_id": str(run.id),
                    "result": {"persistence_mode": "current_offers"},
                },
            ),
            patch.object(service, "_wait_utr_price_cooldown", return_value=None),
            patch.object(service, "_collect_reindex_product_ids", return_value=product_ids),
            patch.object(service, "_reprice_product_ids", return_value={"repriced": 1, "skipped": 0, "errors": 0}) as reprice,
        ):
            result = service.run(source_code="utr")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.payload["publish"]["mode"], "current_offers")
        self.assertTrue(result.payload["publish"]["raw_publish_skipped"])
        self.assertEqual(result.payload["publish"]["repricing"], {"repriced": 1, "skipped": 0, "errors": 0})
        self.assertEqual(result.payload["reindexed_product_ids"], 1)
        workspace_service.publish_mapped_products.assert_not_called()
        reprice.assert_called_once_with(product_ids=product_ids, source_code="utr", run_id=str(run.id))
        indexer.reindex_products.assert_called_once_with(product_ids=product_ids)
