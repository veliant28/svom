from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.autodb.services.raw_offer_enrichment import RawOfferEnrichmentSummary
from apps.autodb.services.remote_config import AutoDbRemoteConfigError
from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.services.import_runner.autodb_postprocess import SupplierImportAutoDbPostProcessor


class SupplierImportAutoDbPostProcessorTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="NGK", slug="ngk", is_active=True)
        self.category = Category.objects.create(name="Spark plugs", slug="spark-plugs", is_active=True)
        self.product = Product.objects.create(
            sku="NGK-0127",
            article="0127",
            name="NGK Product",
            slug="ngk-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            is_active=True,
        )
        self.run = ImportRun.objects.create(
            source=self.source,
            status=ImportRun.STATUS_RUNNING,
            trigger="test",
            dry_run=False,
        )
        SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="SIFR6A11",
            article="0127",
            normalized_article="0127",
            brand_name="NGK",
            normalized_brand="ngk",
            product_name="Свічка запалювання SIFR6A11",
            matched_product=self.product,
            match_status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED,
        )

    def test_flags_disabled_skip_autodb_processing(self):
        raw_service = MagicMock()
        name_service = MagicMock()
        gpl_image_service = MagicMock()
        autodb_image_service = MagicMock()
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=name_service,
            gpl_image_service=gpl_image_service,
            autodb_image_service=autodb_image_service,
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=False,
            autodb_enrich=False,
            update_product_names=False,
        )

        self.assertFalse(raw_service.run.called)
        self.assertFalse(name_service.enrich_product.called)
        self.assertFalse(gpl_image_service.sync_product_images.called)
        self.assertFalse(autodb_image_service.sync_product_images.called)
        self.assertEqual(summary.raw_offers_processed, 1)
        self.assertEqual(summary.products_linked, 0)
        self.assertEqual(summary.product_names_updated, 0)
        self.assertEqual(summary.utr_catalog_calls, 0)

    def test_image_update_flag_runs_gpl_and_autodb_image_services(self):
        self.product.autodb_supplier_id = 15
        self.product.autodb_article_number = "0127"
        self.product.autodb_article_key = "15:0127"
        self.product.save(update_fields=("autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"))

        gpl_image_service = MagicMock()
        gpl_image_service.sync_product_images.return_value = SimpleNamespace(created=1, stale_marked=0)
        autodb_image_service = MagicMock()
        autodb_image_service.sync_product_images.return_value = SimpleNamespace(created=1, stale_marked=0)

        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=MagicMock(),
            product_name_service=MagicMock(),
            gpl_image_service=gpl_image_service,
            autodb_image_service=autodb_image_service,
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=False,
            autodb_enrich=False,
            update_product_names=False,
            update_product_images=True,
        )

        gpl_image_service.sync_product_images.assert_called_once()
        autodb_image_service.sync_product_images.assert_called_once()
        self.assertEqual(summary.product_images_updated, 2)

    def test_enrichment_and_name_update_use_linked_products_only(self):
        self.product.autodb_supplier_id = 15
        self.product.autodb_article_number = "0127"
        self.product.autodb_article_key = "15:0127"
        self.product.save(update_fields=("autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"))

        raw_service = MagicMock()
        raw_service.run.return_value = RawOfferEnrichmentSummary(
            total_raw_offers=1,
            unique_pairs=1,
            local_hits=1,
            remote_hits=0,
            linked_products=1,
            elapsed_seconds=0.01,
        )
        name_service = MagicMock()
        name_service.build_diagnostics.return_value = SimpleNamespace(
            source_kind=Product.NAME_SOURCE_AUTODB_PRO,
            source_title_after_cleanup="Свічка запалювання",
        )
        name_service.enrich_product.return_value = SimpleNamespace(
            status="updated",
            translation_status=Product.NAME_TRANSLATION_TRANSLATED,
        )
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=name_service,
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=False,
            autodb_enrich=True,
            update_product_names=True,
            allow_remote_lookup=False,
        )

        self.assertTrue(raw_service.run.called)
        self.assertTrue(name_service.enrich_product.called)
        self.assertEqual(summary.unique_pairs, 1)
        self.assertEqual(summary.autodb_local_hits, 1)
        self.assertEqual(summary.products_linked, 1)
        self.assertEqual(summary.product_names_updated, 1)
        self.assertEqual(summary.translation_pending, 0)
        self.assertEqual(summary.translation_failed, 0)
        self.assertEqual(summary.utr_catalog_calls, 0)

    def test_manual_locked_name_is_not_overwritten(self):
        self.product.autodb_supplier_id = 15
        self.product.autodb_article_number = "0127"
        self.product.autodb_article_key = "15:0127"
        self.product.name_manually_locked = True
        self.product.save(
            update_fields=(
                "autodb_supplier_id",
                "autodb_article_number",
                "autodb_article_key",
                "name_manually_locked",
                "updated_at",
            )
        )

        raw_service = MagicMock()
        name_service = MagicMock()
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=name_service,
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=False,
            autodb_enrich=False,
            update_product_names=True,
        )

        self.assertEqual(summary.names_skipped_manual_locked, 1)
        self.assertFalse(name_service.enrich_product.called)

    def test_skips_name_update_when_no_autodb_title(self):
        self.product.autodb_supplier_id = 15
        self.product.autodb_article_number = "0127"
        self.product.autodb_article_key = "15:0127"
        self.product.save(update_fields=("autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"))

        raw_service = MagicMock()
        name_service = MagicMock()
        name_service.build_diagnostics.return_value = SimpleNamespace(
            source_kind=Product.NAME_SOURCE_SUPPLIER_FALLBACK,
            source_title_after_cleanup="Свічка запалювання SIFR6A11",
        )
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=name_service,
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=False,
            autodb_enrich=False,
            update_product_names=True,
        )

        self.assertEqual(summary.names_skipped_no_autodb_title, 1)
        self.assertFalse(name_service.enrich_product.called)

    def test_dry_run_is_propagated(self):
        self.product.autodb_supplier_id = 15
        self.product.autodb_article_number = "0127"
        self.product.autodb_article_key = "15:0127"
        self.product.save(update_fields=("autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"))

        raw_service = MagicMock()
        raw_service.run.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1, linked_products=1)
        name_service = MagicMock()
        name_service.build_diagnostics.return_value = SimpleNamespace(
            source_kind=Product.NAME_SOURCE_AUTODB_PRO,
            source_title_after_cleanup="Свічка запалювання",
        )

        def _enrich_product(*, dry_run, **kwargs):
            self.assertTrue(dry_run)
            return SimpleNamespace(status="updated", translation_status=Product.NAME_TRANSLATION_TRANSLATED)

        name_service.enrich_product.side_effect = _enrich_product
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=name_service,
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=True,
            autodb_enrich=True,
            update_product_names=True,
            allow_remote_lookup=False,
        )

        raw_service.run.assert_called_once()
        self.assertTrue(raw_service.run.call_args.kwargs["dry_run"])
        self.assertEqual(summary.product_names_updated, 1)

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED=True,
    )
    @patch("apps.supplier_imports.services.import_runner.autodb_postprocess.AutoDbRemoteConfigValidator.ensure_remote_ready")
    def test_invalid_remote_config_falls_back_to_local_only(self, ensure_remote_ready_mock):
        ensure_remote_ready_mock.side_effect = AutoDbRemoteConfigError(
            "Remote Auto-DB Pro is requested but config is invalid: AUTODB_PRO_REMOTE_HOST is empty"
        )
        raw_service = MagicMock()
        raw_service.run.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1)
        name_service = MagicMock()
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=name_service,
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=False,
            autodb_enrich=True,
            update_product_names=False,
        )

        self.assertFalse(summary.remote_enabled)
        self.assertFalse(summary.remote_check_completed)
        self.assertIn("AUTODB_PRO_REMOTE_HOST", summary.remote_config_error)
        self.assertFalse(raw_service.run.call_args.kwargs["allow_remote"])

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED=True,
    )
    @patch("apps.supplier_imports.services.import_runner.autodb_postprocess.AutoDbRemoteConfigValidator.ensure_remote_ready")
    def test_setting_enables_remote_lookup_for_real_run(self, ensure_remote_ready_mock):
        raw_service = MagicMock()
        raw_service.run.return_value = RawOfferEnrichmentSummary(
            total_raw_offers=1,
            unique_pairs=1,
            remote_attempted=True,
            remote_queries=1,
            remote_hits=1,
            remote_errors=0,
        )
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=MagicMock(),
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=False,
            autodb_enrich=True,
            update_product_names=False,
        )

        ensure_remote_ready_mock.assert_called_once()
        self.assertTrue(raw_service.run.call_args.kwargs["allow_remote"])
        self.assertTrue(summary.remote_enabled)
        self.assertTrue(summary.remote_attempted)
        self.assertEqual(summary.remote_queries, 1)
        self.assertEqual(summary.remote_hits, 1)

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED=True,
    )
    @patch("apps.supplier_imports.services.import_runner.autodb_postprocess.AutoDbRemoteConfigValidator.ensure_remote_ready")
    def test_dry_run_disables_remote_unless_explicit_override(self, ensure_remote_ready_mock):
        raw_service = MagicMock()
        raw_service.run.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1)
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=MagicMock(),
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=True,
            autodb_enrich=True,
            update_product_names=False,
            allow_remote_lookup=None,
        )

        ensure_remote_ready_mock.assert_not_called()
        self.assertFalse(raw_service.run.call_args.kwargs["allow_remote"])
        self.assertEqual(summary.remote_disabled_reason, "dry_run_requires_explicit_remote")

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED=False,
    )
    @patch("apps.supplier_imports.services.import_runner.autodb_postprocess.AutoDbRemoteConfigValidator.ensure_remote_ready")
    def test_explicit_override_enables_remote_in_dry_run(self, ensure_remote_ready_mock):
        raw_service = MagicMock()
        raw_service.run.return_value = RawOfferEnrichmentSummary(total_raw_offers=1, unique_pairs=1)
        processor = SupplierImportAutoDbPostProcessor(
            raw_offer_enrichment_service=raw_service,
            product_name_service=MagicMock(),
        )

        summary = processor.run_for_import(
            run=self.run,
            dry_run=True,
            autodb_enrich=True,
            update_product_names=False,
            allow_remote_lookup=True,
        )

        ensure_remote_ready_mock.assert_called_once()
        self.assertTrue(raw_service.run.call_args.kwargs["allow_remote"])
        self.assertTrue(summary.remote_enabled)
