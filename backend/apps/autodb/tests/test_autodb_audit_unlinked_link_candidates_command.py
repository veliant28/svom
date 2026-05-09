from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.unlinked_link_candidate_audit import UnlinkedLinkCandidateRow


def _row(*, recommendation: str, semantic_status: str = "compatible", confidence: float = 0.95) -> UnlinkedLinkCandidateRow:
    return UnlinkedLinkCandidateRow(
        product_id="p",
        raw_offer_id="r",
        product_name="Product",
        display_brand="Brand",
        brand_source="supplier_fallback",
        raw_brand="Brand",
        normalized_brand="BRAND",
        raw_code="C1",
        raw_category="cat",
        raw_article="A1",
        raw_name="Name",
        raw_description="Desc",
        raw_group="Group",
        raw_article_td="A1",
        raw_image="",
        supplier_article_candidate="A1",
        manufacturer_article_candidate="A1",
        external_sku_candidate="S1",
        article_from_name_candidate="",
        article_from_description_candidate="",
        ean_candidate="",
        oe_candidate="",
        local_supplier_candidates_count=0,
        remote_supplier_candidates_count=0,
        exact_local_article_match="no",
        exact_remote_article_match="no",
        normalized_article_match="no",
        variant_match="no",
        article_numbers_table_match="no",
        article_ean_match="no",
        article_oe_match="no",
        article_cross_match="no",
        proposed_autodb_supplier_id="",
        proposed_autodb_supplier_name="",
        proposed_autodb_article_number="",
        proposed_autodb_article_key="",
        proposed_autodb_title="",
        confidence=confidence,
        semantic_status=semantic_status,
        recommendation=recommendation,
        reason="reason",
    )


class AutoDbAuditUnlinkedLinkCandidatesCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_audit_unlinked_link_candidates.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_audit_unlinked_link_candidates.get_product_display_brand_payload")
    @patch("apps.autodb.management.commands.autodb_audit_unlinked_link_candidates.UnlinkedLinkCandidateAuditService")
    @patch("apps.autodb.management.commands.autodb_audit_unlinked_link_candidates.Command._load_latest_raw_offer_map")
    @patch("apps.autodb.management.commands.autodb_audit_unlinked_link_candidates.Command._load_unlinked_products")
    def test_summary_output(
        self,
        load_products_mock,
        load_offer_map_mock,
        service_cls_mock,
        brand_payload_mock,
        _ready_mock,
    ):
        load_products_mock.return_value = [SimpleNamespace(id="p1", name="P1"), SimpleNamespace(id="p2", name="P2")]
        load_offer_map_mock.return_value = {
            "p1": {"id": "r1", "raw_payload": {}, "brand_name": "MITKA", "article": "A1", "external_sku": "S1"},
            "p2": {"id": "r2", "raw_payload": {}, "brand_name": "WIX", "article": "A2", "external_sku": "S2"},
        }
        brand_payload_mock.return_value = SimpleNamespace(display_brand="Brand", brand_source="supplier_fallback")

        service = service_cls_mock.return_value
        service.audit_offer.side_effect = [
            _row(recommendation="non_auto_or_supplier_only", semantic_status="conflict", confidence=0.0),
            _row(recommendation="safe_auto_link_candidate", semantic_status="compatible", confidence=0.98),
        ]

        out = StringIO()
        call_command("autodb_audit_unlinked_link_candidates", "--supplier", "GPL", "--limit", "2", stdout=out)
        output = out.getvalue()

        self.assertIn("- total_unlinked: 2", output)
        self.assertIn("- safe_auto_link_candidates: 1", output)
        self.assertIn("- non_auto_or_supplier_only: 1", output)
        self.assertIn("- UTR calls=0", output)


class AutoDbApplyUnlinkedLinkCandidatesCommandTests(SimpleTestCase):
    def test_requires_dry_run(self):
        out = StringIO()
        with self.assertRaisesMessage(Exception, "dry-run only"):
            call_command("autodb_apply_unlinked_link_candidates", "--supplier", "GPL", stdout=out)

    @patch(
        "apps.autodb.management.commands.autodb_apply_unlinked_link_candidates.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_apply_unlinked_link_candidates.get_product_display_brand_payload")
    @patch("apps.autodb.management.commands.autodb_apply_unlinked_link_candidates.UnlinkedLinkCandidateAuditService")
    @patch("apps.autodb.management.commands.autodb_apply_unlinked_link_candidates.Command._load_latest_raw_offer_map")
    @patch("apps.autodb.management.commands.autodb_apply_unlinked_link_candidates.Command._load_unlinked_products")
    def test_dry_run_summary(
        self,
        load_products_mock,
        load_offer_map_mock,
        service_cls_mock,
        brand_payload_mock,
        _ready_mock,
    ):
        load_products_mock.return_value = [SimpleNamespace(id="p1", name="P1"), SimpleNamespace(id="p2", name="P2")]
        load_offer_map_mock.return_value = {
            "p1": {"id": "r1", "raw_payload": {}, "brand_name": "WIX", "article": "A1", "external_sku": "S1"},
            "p2": {"id": "r2", "raw_payload": {}, "brand_name": "MITKA", "article": "A2", "external_sku": "S2"},
        }
        brand_payload_mock.return_value = SimpleNamespace(display_brand="Brand", brand_source="supplier_fallback")
        service = service_cls_mock.return_value
        service.audit_offer.side_effect = [
            _row(recommendation="safe_auto_link_candidate", confidence=0.98),
            _row(recommendation="non_auto_or_supplier_only", semantic_status="conflict", confidence=0.0),
        ]
        out = StringIO()
        call_command(
            "autodb_apply_unlinked_link_candidates",
            "--supplier",
            "GPL",
            "--limit",
            "2",
            "--dry-run",
            "--only-safe",
            stdout=out,
        )
        output = out.getvalue()
        self.assertIn("- candidates_total: 2", output)
        self.assertIn("- selected_safe: 1", output)
        self.assertIn("- would_apply: 1", output)
        self.assertIn("- UTR calls=0", output)
