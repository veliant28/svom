from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.management.commands.autodb_diagnose_unlinked_products import ProductDiagnosis


class AutoDbDiagnoseUnlinkedProductsCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_diagnose_unlinked_products.Command._select_products", return_value=[])
    def test_no_products_message(self, _select_products_mock):
        out = StringIO()

        call_command("autodb_diagnose_unlinked_products", stdout=out)

        self.assertIn("No unlinked products found.", out.getvalue())

    @patch("apps.autodb.management.commands.autodb_diagnose_unlinked_products.Command._diagnose_product")
    @patch("apps.autodb.management.commands.autodb_diagnose_unlinked_products.Command._select_products")
    def test_summary_output(self, select_products_mock, diagnose_mock):
        select_products_mock.return_value = [SimpleNamespace(id="p1"), SimpleNamespace(id="p2")]
        diagnose_mock.side_effect = [
            ProductDiagnosis(
                product_id="p1",
                reason="link_possible",
                lookup_status="completed",
                has_raw_offers=True,
                brand_matched=True,
                article_found=True,
                link_possible=True,
            ),
            ProductDiagnosis(
                product_id="p2",
                reason="needs_manual_mapping",
                lookup_status="completed",
                has_raw_offers=True,
                brand_matched=True,
                article_found=False,
                link_possible=False,
            ),
        ]
        out = StringIO()

        call_command("autodb_diagnose_unlinked_products", "--limit", "2", stdout=out)

        output = out.getvalue()
        self.assertIn("Summary:", output)
        self.assertIn("total_products_checked: 2", output)
        self.assertIn("linked_possible: 1", output)
        self.assertIn("needs_manual_mapping: 1", output)
        self.assertIn("UTR calls: 0", output)

    @patch("apps.autodb.management.commands.autodb_diagnose_unlinked_products.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_diagnose_unlinked_products.Command._select_products")
    def test_invalid_remote_config_marks_remote_config_error(self, select_products_mock, ensure_remote_ready_mock):
        from apps.autodb.services.remote_config import AutoDbRemoteConfigError

        ensure_remote_ready_mock.side_effect = AutoDbRemoteConfigError("AUTODB_PRO_REMOTE_HOST is empty")
        select_products_mock.return_value = [SimpleNamespace(id="p1", brand=SimpleNamespace(name="NGK"))]
        out = StringIO()

        with patch(
            "apps.autodb.management.commands.autodb_diagnose_unlinked_products.Command._diagnose_product",
            return_value=ProductDiagnosis(
                product_id="p1",
                reason="remote_config_error",
                lookup_status="lookup_not_completed",
                has_raw_offers=False,
                brand_matched=False,
                article_found=False,
                link_possible=False,
                lookup_error="AUTODB_PRO_REMOTE_HOST is empty",
            ),
        ):
            call_command("autodb_diagnose_unlinked_products", "--allow-remote", "--limit", "1", stdout=out)

        output = out.getvalue()
        self.assertIn("remote_check_completed: false", output)

    def test_reason_resolution(self):
        from apps.autodb.management.commands.autodb_diagnose_unlinked_products import Command

        command = Command()
        self.assertEqual(
            command._resolve_reason(
                has_raw_offers=False,
                brand_matched=False,
                article_candidates=[],
                article_found=False,
                lookup_not_completed=False,
            ),
            "no_raw_offers",
        )
        self.assertEqual(
            command._resolve_reason(
                has_raw_offers=True,
                brand_matched=False,
                article_candidates=["A1"],
                article_found=False,
                lookup_not_completed=False,
            ),
            "brand_not_found",
        )
        self.assertEqual(
            command._resolve_reason(
                has_raw_offers=True,
                brand_matched=True,
                article_candidates=["A1"],
                article_found=False,
                lookup_not_completed=False,
            ),
            "needs_manual_mapping",
        )
