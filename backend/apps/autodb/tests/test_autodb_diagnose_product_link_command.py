from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class AutoDbDiagnoseProductLinkCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.Command._print_raw_offer_search")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.Command._resolve_products", return_value=[])
    def test_search_without_products_prints_raw_offer_probe(self, _resolve_products, print_raw_mock):
        out = StringIO()

        call_command("autodb_diagnose_product_link", "--search", "SIFR6A11", stdout=out)

        self.assertIn("No Product found for diagnostics", out.getvalue())
        print_raw_mock.assert_called_once_with(search="SIFR6A11")

    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.AutoDbArticleLookupService")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.SupplierBrandMatcher")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.Command._collect_raw_offers", return_value=[])
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.Command._resolve_products")
    def test_output_includes_reason_for_unlinked_product(
        self,
        resolve_products_mock,
        _collect_raw_offers_mock,
        matcher_cls_mock,
        lookup_cls_mock,
    ):
        product = SimpleNamespace(
            id="p-1",
            name="0127 Свічка запалювання SIFR6A11",
            article="SIFR6A11",
            sku="sku-1",
            autodb_supplier_id=None,
            autodb_article_number="",
            autodb_article_key="",
            brand=SimpleNamespace(name="NGK"),
        )
        resolve_products_mock.return_value = [product]

        matcher_instance = matcher_cls_mock.return_value
        matcher_instance.resolve_many.return_value = {}

        lookup_instance = lookup_cls_mock.return_value
        lookup_instance.lookup.return_value = SimpleNamespace(
            found=False,
            supplier_id=None,
            canonical_article_number="",
            supplier_source="local",
            article_source="not_found",
            remote_supplier_called=False,
            remote_article_called=False,
            article_search_variants=("SIFR6A11",),
            warnings=["supplier_not_found", "article_not_found"],
        )
        out = StringIO()

        call_command("autodb_diagnose_product_link", "--product-id", "p-1", stdout=out)

        output = out.getvalue()
        self.assertIn("reason: brand_not_found_in_suppliers", output)
        self.assertIn("UTR calls: 0", output)

    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.AutoDbArticleLookupService")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.SupplierBrandMatcher")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.Command._collect_raw_offers", return_value=[])
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.Command._resolve_products")
    def test_allow_remote_passed_to_lookup(
        self,
        resolve_products_mock,
        _collect_raw_offers_mock,
        matcher_cls_mock,
        lookup_cls_mock,
    ):
        product = SimpleNamespace(
            id="p-remote",
            name="Test",
            article="SIFR6A11",
            sku="sku-1",
            autodb_supplier_id=None,
            autodb_article_number="",
            autodb_article_key="",
            brand=SimpleNamespace(name="NGK"),
        )
        resolve_products_mock.return_value = [product]
        matcher_instance = matcher_cls_mock.return_value
        matcher_instance.resolve_many.return_value = {}
        lookup_instance = lookup_cls_mock.return_value
        lookup_instance.lookup.return_value = SimpleNamespace(
            found=False,
            supplier_id=None,
            canonical_article_number="",
            supplier_source="local",
            article_source="not_found",
            remote_supplier_called=True,
            remote_article_called=True,
            article_search_variants=("SIFR6A11", "SIFR6A-11"),
            warnings=["article_not_found"],
        )
        out = StringIO()

        call_command("autodb_diagnose_product_link", "--product-id", "p-remote", "--allow-remote", stdout=out)

        lookup_instance.lookup.assert_called()
        first_call = lookup_instance.lookup.call_args_list[0]
        self.assertTrue(first_call.kwargs["allow_remote"])

    def test_collect_article_candidates_reads_raw_payload_candidate_fields(self):
        from apps.autodb.management.commands.autodb_diagnose_product_link import Command

        command = Command()
        product = SimpleNamespace(article="SIFR6A11", autodb_article_number="", sku="SKU-1")
        raw_offers = [
            SimpleNamespace(
                article="",
                normalized_article="",
                external_sku="",
                raw_payload={
                    "Артикул ТД": "SIFR6A-11",
                    "ean": "1234567890123",
                    "oe_number": "OE-777",
                    "cross_ref": "REF-999",
                },
            )
        ]

        buckets = command._collect_article_candidates(product=product, raw_offers=raw_offers)

        self.assertIn("SIFR6A11", buckets["article_numbers"])
        self.assertIn("SIFR6A-11", buckets["article_numbers"])
        self.assertIn("1234567890123", buckets["ean"])
        self.assertIn("OE-777", buckets["oe"])
        self.assertIn("REF-999", buckets["cross"])

    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_diagnose_product_link.Command._resolve_products")
    def test_allow_remote_invalid_config_returns_remote_config_error(self, resolve_products_mock, ensure_remote_ready_mock):
        from apps.autodb.services.remote_config import AutoDbRemoteConfigError

        ensure_remote_ready_mock.side_effect = AutoDbRemoteConfigError(
            "Remote Auto-DB Pro is requested but config is invalid: AUTODB_PRO_REMOTE_HOST is empty"
        )
        product = SimpleNamespace(
            id="p-config",
            name="Test",
            article="SIFR6A11",
            sku="sku-1",
            autodb_supplier_id=None,
            autodb_article_number="",
            autodb_article_key="",
            brand=SimpleNamespace(name="NGK"),
        )
        resolve_products_mock.return_value = [product]
        out = StringIO()

        call_command("autodb_diagnose_product_link", "--product-id", "p-config", "--allow-remote", stdout=out)

        output = out.getvalue()
        self.assertIn("reason: remote_config_error", output)
        self.assertIn("lookup_status: lookup_not_completed", output)
        self.assertNotIn("needs_manual_mapping", output)
