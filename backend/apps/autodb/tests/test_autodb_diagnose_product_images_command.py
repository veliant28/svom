from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_image_enrichment import AutoDbImageDiagnostics
from apps.supplier_imports.services.gpl_images import GplImageDiagnostics


class AutoDbDiagnoseProductImagesCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_diagnose_product_images.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_diagnose_product_images.SupplierRawOffer.objects.filter")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_images.Product.objects.select_related")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_images.GplProductImageService")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_images.AutoDbProductImageEnrichmentService")
    def test_outputs_diagnostics(self, autodb_cls_mock, gpl_cls_mock, select_related_mock, offers_filter_mock, _ready_mock):
        product = SimpleNamespace(
            id="p1",
            name="Test",
            images=SimpleNamespace(order_by=lambda *args, **kwargs: []),
        )
        select_related_mock.return_value.prefetch_related.return_value.get.return_value = product
        offers_filter_mock.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = []

        gpl_cls_mock.return_value.build_diagnostics.return_value = GplImageDiagnostics(
            product_id="p1",
            source_code="gpl",
            latest_offer_id="r1",
            payload_keys=("image_url",),
            candidates=("https://cdn.example.com/a.jpg",),
        )
        autodb_cls_mock.return_value.build_diagnostics.return_value = AutoDbImageDiagnostics(
            product_id="p1",
            bridge_supplier_id=300,
            bridge_article_number="820099",
            bridge_article_key="300:820099",
            article_images_rows=({"supplierId": 300, "DataSupplierArticleNumber": "820099", "FileName": "a.jpg"},),
            candidates=(
                {
                    "remote_url": "https://autodb.example.com/a.jpg",
                    "reference": "a.jpg",
                    "reference_kind": "FileName",
                    "pending_url_resolution": False,
                },
            ),
        )

        out = StringIO()
        call_command("autodb_diagnose_product_images", "--product-id", "p1", stdout=out)

        output = out.getvalue()
        self.assertIn("bridge.autodb_article_key: 300:820099", output)
        self.assertIn("GPL image candidates", output)
        self.assertIn("reason if skipped", output)
        self.assertIn("UTR calls: 0", output)
