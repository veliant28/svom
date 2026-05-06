from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.clone_runtime_status import CloneRuntimeStatus
from apps.autodb.services.product_fitment_audit import ProductFitmentAuditRow, ProductFitmentAuditSummary


class AutoDbAuditProductFitmentsCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_audit_product_fitments.get_passanger_car_trees_runtime_status")
    @patch("apps.autodb.management.commands.autodb_audit_product_fitments.AutoDbProductFitmentAuditService")
    def test_outputs_distribution_and_runtime_status(self, service_cls_mock, runtime_mock):
        service = service_cls_mock.return_value
        service.build_queryset.return_value = object()
        rows = [
            ProductFitmentAuditRow(
                product_id="p1",
                name_uk="Шарнірний комплект",
                name_ru="Шарнирный комплект",
                name_en="Joint kit",
                brand="Brand",
                article="820099",
                autodb_article_key="300:820099",
                autodb_article_title="Шарнирный комплект",
                autodb_prd_title="Шарнирный комплект",
                fitment_count=3,
                stale_fitment_count=0,
                sample_autodb_passanger_car_id=4215,
                sample_vehicle_label="HONDA / LEGEND / HONDA LEGEND 3.2 i 24V (KA7) / 1991-1996",
                suspicious_flags=(),
                suspicious_reason="",
                raw_linkage_type_counts={"PassengerCar": 3},
                missing_passanger_car_ids=(),
                persisted_quality_status="trusted",
                persisted_quality_reason="",
                persisted_excluded_from_public_filtering=False,
                persisted_manual_override=False,
            )
        ]
        summary = ProductFitmentAuditSummary(
            audited_products=1,
            total_fitments=3,
            min_fitments=3,
            max_fitments=3,
            avg_fitments=3.0,
            median_fitments=3.0,
            suspicious_products=0,
            products_over_1000_fitments=(),
            top_products=(("p1", "Шарнірний комплект", 3),),
            linkage_type_counts={"PassengerCar": 3, "CommercialVehicle": 1},
            autodb_fitment_linkage_counts={"PassengerCar": 3},
            missing_passanger_car_count=0,
            sample_rows=tuple(rows),
        )
        service.audit_queryset.return_value = (rows, summary)
        runtime_mock.return_value = CloneRuntimeStatus(
            table="passanger_car_trees",
            state_status="running",
            actual_status="paused",
            process_running=False,
            pid=None,
            processed_rows=13870000,
            total_rows=14983071,
            failed_rows=0,
            table_row_count=13880539,
            last_cursor="keyset:[102811,17994,1]",
            started_at=None,
            finished_at=None,
            updated_at=None,
            last_error="process_not_running_resume_allowed",
            reconciled=True,
            reconcile_note="process_not_running_resume_allowed",
        )

        out = StringIO()
        call_command("autodb_audit_product_fitments", "--limit", "100", "--persist-quality", stdout=out)

        output = out.getvalue()
        self.assertIn("- audited_products: 1", output)
        self.assertIn("- avg_fitments: 3.0", output)
        self.assertIn("- flagged_products_any_reason: 0", output)
        self.assertIn("persist_quality=True", output)
        self.assertIn("raw article_li linkageTypeId summary", output)
        self.assertIn("persisted quality summary", output)
        self.assertIn("passanger_car_trees actual status", output)
        self.assertIn("actual_status=paused", output)
        self.assertIn("suspicious_link examples", output)
        self.assertIn("UTR calls: 0", output)
