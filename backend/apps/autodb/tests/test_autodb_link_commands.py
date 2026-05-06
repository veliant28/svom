from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.product_linker import ProductLinkResult


class AutoDbLinkCommandsTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_link_product.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_link_product.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_link_product.AutoDbProductLinkService.link_product_by_id")
    def test_autodb_link_product_command(self, link_mock, _ensure_remote_ready_mock, _ready_mock):
        link_mock.return_value = ProductLinkResult(
            linked=True,
            link_status="linked",
            product_id="p1",
            supplier_id=10,
            article_id=20,
            article_number="W712/95",
            article_key="10:W712/95",
            normalized_brand="BOSCH",
            normalized_article="W71295",
        )
        out = StringIO()

        call_command("autodb_link_product", "--product-id", "p1", stdout=out)

        self.assertIn("linked: True", out.getvalue())
        self.assertIn("link_status: linked", out.getvalue())
        link_mock.assert_called_once_with(product_id="p1", dry_run=False, allow_remote=True)

    @patch(
        "apps.autodb.management.commands.autodb_link_product.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_link_product.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_link_product.AutoDbProductLinkService.link_product_by_id")
    def test_autodb_link_product_dry_run_command(self, link_mock, _ensure_remote_ready_mock, _ready_mock):
        link_mock.return_value = ProductLinkResult(
            linked=False,
            link_status="needs_manual_mapping",
            product_id="p1",
            supplier_id=None,
            article_id=None,
            article_number="",
            article_key="",
            normalized_brand="NGK",
            normalized_article="SIFR6A11",
        )
        out = StringIO()

        call_command("autodb_link_product", "--product-id", "p1", "--dry-run", stdout=out)

        self.assertIn("dry_run: True", out.getvalue())
        link_mock.assert_called_once_with(product_id="p1", dry_run=True, allow_remote=True)

    @patch("apps.autodb.management.commands.autodb_link_offer.AutoDbProductLinkService.link_from_raw_offer")
    def test_autodb_link_offer_command(self, link_mock):
        link_mock.return_value = ProductLinkResult(
            linked=False,
            link_status="not_found",
            product_id="p2",
            supplier_id=None,
            article_id=None,
            article_number="",
            article_key="",
            normalized_brand="UNKNOWN",
            normalized_article="NOPE",
            warnings=["article_not_found"],
        )
        out = StringIO()

        call_command("autodb_link_offer", "--raw-offer-id", "r1", stdout=out)

        self.assertIn("linked: False", out.getvalue())
        self.assertIn("article_not_found", out.getvalue())

    @patch(
        "apps.autodb.management.commands.autodb_link_product.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_link_product.AutoDbRemoteConfigValidator.ensure_remote_ready")
    def test_link_product_fails_fast_on_invalid_remote_config(self, ensure_remote_ready_mock, _ready_mock):
        from django.core.management.base import CommandError

        from apps.autodb.services.remote_config import AutoDbRemoteConfigError

        ensure_remote_ready_mock.side_effect = AutoDbRemoteConfigError(
            "Remote Auto-DB Pro is requested but config is invalid: AUTODB_PRO_REMOTE_HOST is empty"
        )

        with self.assertRaises(CommandError):
            call_command("autodb_link_product", "--product-id", "p1", "--dry-run")
