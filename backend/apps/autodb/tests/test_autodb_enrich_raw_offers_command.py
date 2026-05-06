from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.raw_offer_enrichment import RawOfferEnrichmentSummary
from apps.autodb.services.remote_config import AutoDbRemoteConfigError


class AutoDbEnrichRawOffersCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_enrich_raw_offers.wait_for_local_autodb_ready",
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
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="remote.example",
        AUTODB_PRO_REMOTE_DATABASE="autodb",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    @patch("apps.autodb.management.commands.autodb_enrich_raw_offers.AutoDbRawOfferEnrichmentService.run")
    def test_dry_run_defaults_to_local_only(self, run_mock, _ready_mock):
        run_mock.return_value = RawOfferEnrichmentSummary(total_raw_offers=10, unique_pairs=3)
        out = StringIO()

        call_command("autodb_enrich_raw_offers", "--dry-run", stdout=out)

        self.assertFalse(run_mock.call_args.kwargs["allow_remote"])
        self.assertIn("Dry-run mode: remote Auto-DB fallback is disabled", out.getvalue())

    @patch(
        "apps.autodb.management.commands.autodb_enrich_raw_offers.wait_for_local_autodb_ready",
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
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="remote.example",
        AUTODB_PRO_REMOTE_DATABASE="autodb",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    @patch("apps.autodb.management.commands.autodb_enrich_raw_offers.AutoDbRawOfferEnrichmentService.run")
    def test_allow_remote_in_dry_run_switch(self, run_mock, _ready_mock):
        run_mock.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1)

        call_command("autodb_enrich_raw_offers", "--dry-run", "--allow-remote")

        self.assertTrue(run_mock.call_args.kwargs["allow_remote"])

    @patch(
        "apps.autodb.management.commands.autodb_enrich_raw_offers.wait_for_local_autodb_ready",
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
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="remote.example",
        AUTODB_PRO_REMOTE_DATABASE="autodb",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    @patch("apps.autodb.management.commands.autodb_enrich_raw_offers.AutoDbRawOfferEnrichmentService.run")
    def test_real_run_uses_setting_based_remote_by_default(self, run_mock, _ready_mock):
        run_mock.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1)

        call_command("autodb_enrich_raw_offers")

        self.assertTrue(run_mock.call_args.kwargs["allow_remote"])

    @patch(
        "apps.autodb.management.commands.autodb_enrich_raw_offers.wait_for_local_autodb_ready",
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
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="remote.example",
        AUTODB_PRO_REMOTE_DATABASE="autodb",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    @patch("apps.autodb.management.commands.autodb_enrich_raw_offers.AutoDbRawOfferEnrichmentService.run")
    def test_no_remote_overrides_enabled_remote(self, run_mock, _ready_mock):
        run_mock.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1)

        call_command("autodb_enrich_raw_offers", "--no-remote")

        self.assertFalse(run_mock.call_args.kwargs["allow_remote"])

    @patch(
        "apps.autodb.management.commands.autodb_enrich_raw_offers.wait_for_local_autodb_ready",
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
    @override_settings(AUTODB_PRO_REMOTE_ENABLED=False)
    @patch("apps.autodb.management.commands.autodb_enrich_raw_offers.AutoDbRawOfferEnrichmentService.run")
    def test_prints_summary_and_elapsed(self, run_mock, _ready_mock):
        run_mock.return_value = RawOfferEnrichmentSummary(
            total_raw_offers=100,
            unique_pairs=90,
            local_hits=70,
            remote_hits=0,
            not_found=20,
            failed=1,
            enriched_articles=10,
            linked_products=30,
            skipped_no_matched_product=5,
            skipped_disabled_no_remote=2,
            remote_enabled=False,
            remote_attempted=False,
            remote_queries=0,
            remote_errors=0,
            remote_disabled_reason="setting_remote_lookup_disabled",
            elapsed_seconds=3.25,
        )
        out = StringIO()

        call_command("autodb_enrich_raw_offers", "--progress-every", "20", stdout=out)

        output = out.getvalue()
        self.assertIn("total raw offers: 100", output)
        self.assertIn("remote_enabled: False", output)
        self.assertIn("remote_disabled_reason: setting_remote_lookup_disabled", output)
        self.assertIn("elapsed seconds: 3.250", output)
        self.assertIn("UTR calls: 0", output)

    @patch(
        "apps.autodb.management.commands.autodb_enrich_raw_offers.wait_for_local_autodb_ready",
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
    @patch("apps.autodb.management.commands.autodb_enrich_raw_offers.AutoDbRemoteConfigValidator.ensure_remote_ready")
    @patch("apps.autodb.management.commands.autodb_enrich_raw_offers.AutoDbRawOfferEnrichmentService.run")
    @override_settings(AUTODB_PRO_REMOTE_ENABLED=True)
    def test_invalid_remote_config_falls_back_to_local_only(self, run_mock, ensure_ready_mock, _ready_mock):
        ensure_ready_mock.side_effect = AutoDbRemoteConfigError("AUTODB_PRO_REMOTE_HOST is empty")
        run_mock.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1)
        out = StringIO()

        call_command("autodb_enrich_raw_offers", "--allow-remote", "--dry-run", stdout=out)
        self.assertFalse(run_mock.call_args.kwargs["allow_remote"])
        self.assertEqual(
            run_mock.call_args.kwargs["remote_disabled_reason"],
            "remote_config_error:AUTODB_PRO_REMOTE_HOST is empty",
        )
