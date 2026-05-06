from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_fitment_enrichment import ProductFitmentDiagnostics


class AutoDbDiagnoseProductFitmentsCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_diagnose_product_fitments.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_diagnose_product_fitments.Product.objects.select_related")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_fitments.AutoDbProductFitmentEnrichmentService")
    def test_outputs_diagnostics(self, service_cls_mock, select_related_mock, _ready_mock):
        product = SimpleNamespace(id="p1", name="Test", autodb_supplier_id=324, autodb_article_number="92131E")
        select_related_mock.return_value.get.return_value = product

        service = service_cls_mock.return_value
        service.build_diagnostics.return_value = ProductFitmentDiagnostics(
            product_id="p1",
            bridge_supplier_id=324,
            bridge_article_number="92131E",
            bridge_article_key="324:92131E",
            article_li_rows=(
                {
                    "supplierId": 324,
                    "DataSupplierArticleNumber": "92131E",
                    "linkageTypeId": "PassengerCar",
                    "linkageId": 101,
                },
            ),
            passenger_candidates=(
                {
                    "supplierId": 324,
                    "DataSupplierArticleNumber": "92131E",
                    "linkageTypeId": "PassengerCar",
                    "linkageId": 101,
                },
            ),
            passanger_cars_rows=(
                {"id": 101, "modelid": 1, "description": "Camry", "fulldescription": "TOYOTA CAMRY"},
            ),
            current_fitments=(
                {
                    "id": "f1",
                    "source": "autodb_pro",
                    "modification_id": "",
                    "autodb_passanger_car_id": 101,
                    "linkage_type": "PassengerCar",
                    "is_stale": False,
                    "manual_locked": False,
                },
            ),
            proposed_creates=(),
            proposed_updates=({"id": "f1", "manual_locked": False, "is_stale": False},),
            proposed_stale=(),
            skipped_reason="",
        )

        out = StringIO()
        call_command("autodb_diagnose_product_fitments", "--product-id", "p1", stdout=out)

        output = out.getvalue()
        self.assertIn("article_li rows", output)
        self.assertIn("passanger_cars rows for linkageId", output)
        self.assertIn("reason if skipped", output)
        self.assertIn("UTR calls: 0", output)
