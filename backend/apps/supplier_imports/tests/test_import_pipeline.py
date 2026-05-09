from __future__ import annotations

import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.pricing.models import PriceHistory, PricingPolicy, ProductPrice, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRowError, ImportRun, ImportSource, OfferMatchReview, SupplierRawOffer
from apps.supplier_imports.services import SupplierImportRunner


class SupplierImportPipelineTests(TestCase):
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
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)

    def test_import_run_creation_and_offer_create(self):
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "opt2_currency_980": "100.00",
                "opt4_currency_980": "90.00",
                "opt10_currency_980": "80.00",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95",
                "count_warehouse_4": "10"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                is_active=True,
                auto_reprice=False,
            )

            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        self.assertEqual(run.status, ImportRun.STATUS_SUCCESS)
        self.assertEqual(run.offers_created, 1)
        self.assertEqual(run.errors_count, 0)

        offer = SupplierOffer.objects.get(supplier=self.supplier, product=self.product, supplier_sku="0007523")
        self.assertEqual(offer.purchase_price, Decimal("140.24"))
        self.assertEqual([level["label"] for level in offer.price_levels], ["ОПТ2", "ОПТ4", "ОПТ10", "РРЦ"])
        self.assertTrue(offer.price_levels[-1]["is_primary"])
        self.assertEqual(offer.stock_qty, 105)

    def test_row_error_handling_when_required_fields_missing(self):
        payload = """
        {
          "data": {
            "items": [
              {
                "name": "Broken row",
                "rrc_currency_980": "100.00"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl-broken.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                is_active=True,
                auto_reprice=False,
            )

            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        self.assertEqual(run.status, ImportRun.STATUS_FAILED)
        self.assertGreater(run.errors_count, 0)
        self.assertEqual(ImportRowError.objects.filter(run=run).count(), run.errors_count)

    def test_supplier_offer_upsert_updates_existing(self):
        payload_first = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "opt2_currency_980": "100.00",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "5"
              }
            ]
          }
        }
        """
        payload_second = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "rrc_currency_980": "150.50",
                "count_warehouse_3": "8"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                is_active=True,
                auto_reprice=False,
            )

            file_path.write_text(payload_first, encoding="utf-8")
            run_first = SupplierImportRunner().run_source(source=source, trigger="test")

            file_path.write_text(payload_second, encoding="utf-8")
            run_second = SupplierImportRunner().run_source(source=source, trigger="test")

        first = ImportRun.objects.get(id=run_first.run_id)
        second = ImportRun.objects.get(id=run_second.run_id)
        self.assertEqual(first.offers_created, 1)
        self.assertEqual(second.offers_updated, 1)

        offer = SupplierOffer.objects.get(supplier=self.supplier, product=self.product, supplier_sku="0007523")
        self.assertEqual(offer.purchase_price, Decimal("150.50"))
        self.assertEqual(offer.stock_qty, 8)

    def test_current_offer_persistence_does_not_create_raw_history(self):
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "current_offers"},
                is_active=True,
                auto_reprice=False,
            )

            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        self.assertEqual(run.status, ImportRun.STATUS_SUCCESS)
        self.assertEqual(run.summary["persistence_mode"], "current_offers")
        self.assertIn("timings", run.summary)
        self.assertIn("cache_stats", run.summary)
        self.assertEqual(SupplierRawOffer.objects.filter(run=run).count(), 0)
        self.assertEqual(OfferMatchReview.objects.count(), 0)

        offer = SupplierOffer.objects.get(supplier=self.supplier, product=self.product, supplier_sku="0007523")
        self.assertEqual(offer.purchase_price, Decimal("140.24"))
        self.assertEqual(offer.price_levels[-1]["label"], "РРЦ")
        self.assertEqual(offer.stock_qty, 95)
        self.assertIsNotNone(offer.last_seen_at)

    def test_current_offer_persistence_disables_missing_supplier_skus(self):
        stale_product = Product.objects.create(
            sku="AR-OLD",
            article="AR-OLD",
            name="Old Aral product",
            slug="old-aral-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.supplier,
            product=stale_product,
            supplier_sku="OLD-SKU",
            purchase_price=Decimal("10.00"),
            stock_qty=3,
            is_available=True,
        )
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "current_offers"},
                is_active=True,
                auto_reprice=False,
            )

            SupplierImportRunner().run_source(source=source, trigger="test")

        stale_offer = SupplierOffer.objects.get(supplier=self.supplier, supplier_sku="OLD-SKU")
        self.assertFalse(stale_offer.is_available)
        self.assertEqual(stale_offer.stock_qty, 0)

    def test_current_offer_persistence_prunes_old_row_errors_by_run_retention(self):
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "BROKEN-SKU",
                "category": "UNKNOWN",
                "article": "NO-SUCH-ARTICLE",
                "name": "Unmatched item",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "1"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={
                    "persistence_mode": "current_offers",
                    "row_error_retention_runs": 2,
                },
                is_active=True,
                auto_reprice=False,
            )

            now = timezone.now()
            old_runs = []
            for offset in (3, 2, 1):
                old_run = ImportRun.objects.create(
                    source=source,
                    status=ImportRun.STATUS_PARTIAL,
                    trigger="test",
                    started_at=now - timedelta(days=offset),
                    finished_at=now - timedelta(days=offset),
                    errors_count=1,
                )
                old_runs.append(old_run)
                ImportRowError.objects.create(
                    run=old_run,
                    source=source,
                    message=f"Old error {offset}",
                    error_code="old_error",
                )

            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        self.assertEqual(run.status, ImportRun.STATUS_PARTIAL)
        self.assertEqual(ImportRowError.objects.filter(run=run).count(), 1)
        self.assertEqual(run.summary["row_error_retention"]["keep_runs"], 2)
        self.assertEqual(run.summary["row_error_retention"]["deleted"], 2)

        retained_run_ids = set(ImportRowError.objects.filter(source=source).values_list("run_id", flat=True))
        self.assertEqual(retained_run_ids, {old_runs[-1].id, run.id})

    def test_current_offer_persistence_bootstraps_clean_catalog_for_gpl(self):
        Product.objects.all().delete()
        SupplierOffer.objects.all().delete()

        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "BOOT-001",
                "category": "WIX FILTERS",
                "article": "WL7067",
                "name": "Масляний фільтр",
                "rrc_currency_980": "250.00",
                "count_warehouse_3": "7"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl-bootstrap.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "current_offers"},
                is_active=True,
                auto_reprice=False,
            )

            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        self.assertEqual(run.status, ImportRun.STATUS_SUCCESS)
        self.assertEqual(run.errors_count, 0)
        self.assertGreaterEqual(run.offers_created, 1)
        self.assertEqual(SupplierRawOffer.objects.filter(run=run).count(), 1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(SupplierOffer.objects.filter(supplier=self.supplier).count(), 1)
        self.assertEqual(run.summary["current_offer_rows"]["bootstrap_unmatched_enabled"], 1)

    @patch("apps.supplier_imports.services.import_runner.persistence.GplImportCategoryAssignmentResolver")
    def test_gpl_bootstrap_uses_combined_category_resolver_and_assigns_leaf_only(self, resolver_cls_mock):
        Product.objects.all().delete()
        SupplierOffer.objects.all().delete()
        SupplierRawOffer.objects.all().delete()

        root = Category.objects.create(
            name="Root",
            slug="root-test",
            is_active=True,
            is_assignable=False,
        )
        leaf = Category.objects.create(
            name="Leaf",
            slug="leaf-test",
            parent=root,
            is_active=True,
            is_assignable=True,
        )

        resolver = resolver_cls_mock.return_value
        resolver.decide_group.return_value = SimpleNamespace(
            mapping_status="assigned_by_group_mapping",
            proposed_category_slug="leaf-test",
            proposed_category_name="Leaf",
            proposed_root_name="Root",
            category_id=str(leaf.id),
            category_is_assignable=True,
            matched_rule="group_rule",
            confidence=0.99,
            reason="group_mapping_candidate",
            invalid_target=False,
            non_assignable_target=False,
            missing_target=False,
        )
        resolver.decide_row.return_value = SimpleNamespace(
            mapping_status="assigned_by_group_mapping",
            proposed_category_slug="leaf-test",
            proposed_category_name="Leaf",
            proposed_root_name="Root",
            category_id=str(leaf.id),
            category_is_assignable=True,
            matched_rule="group_rule",
            confidence=0.99,
            reason="group_mapping_candidate",
            invalid_target=False,
            non_assignable_target=False,
            missing_target=False,
        )

        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "BOOT-002",
                "category": "Anything",
                "article": "LEAF-001",
                "name": "Leaf product",
                "rrc_currency_980": "250.00",
                "count_warehouse_3": "7",
                "Зображення товару": "https://cdn.example.com/leaf.webp"
              }
            ]
          }
        }
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl-bootstrap-leaf.json"
            file_path.write_text(payload, encoding="utf-8")
            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "current_offers"},
                is_active=True,
                auto_reprice=False,
            )
            result = SupplierImportRunner().run_source(
                source=source,
                trigger="test",
                autodb_enrich=False,
                update_product_names=False,
                update_product_images=False,
            )

        run = ImportRun.objects.get(id=result.run_id)
        product = Product.objects.get(sku="GPL-BOOT002")
        raw_offer = SupplierRawOffer.objects.get(run=run)
        image = ProductImage.objects.get(product=product, source=ProductImage.SOURCE_GPL_PRICE)
        self.assertEqual(product.category_id, leaf.id)
        self.assertEqual(raw_offer.mapped_category_id, leaf.id)
        self.assertTrue(image.is_primary)
        self.assertEqual(run.summary["gpl_category_assignment"]["assigned_by_group_mapping"], 1)
        self.assertEqual(run.summary["gpl_category_assignment"]["invalid_target_count"], 0)
        self.assertEqual(run.summary["autodb_supplier_import"]["enabled"], False)

    @patch("apps.supplier_imports.services.import_runner.persistence.GplImportCategoryAssignmentResolver")
    def test_gpl_bootstrap_rejects_root_target_and_keeps_category_null(self, resolver_cls_mock):
        Product.objects.all().delete()
        SupplierOffer.objects.all().delete()
        SupplierRawOffer.objects.all().delete()

        root = Category.objects.create(
            name="Root only",
            slug="root-only",
            is_active=True,
            is_assignable=False,
        )
        category_count_before = Category.objects.count()

        resolver = resolver_cls_mock.return_value
        resolver.decide_group.return_value = SimpleNamespace(
            mapping_status="conflict",
            proposed_category_slug="root-only",
            proposed_category_name="Root only",
            proposed_root_name="Root only",
            category_id=str(root.id),
            category_is_assignable=False,
            matched_rule="bad_rule",
            confidence=0.8,
            reason="target_root_forbidden",
            invalid_target=True,
            non_assignable_target=False,
            missing_target=False,
        )
        resolver.decide_row.return_value = SimpleNamespace(
            mapping_status="conflict",
            proposed_category_slug="root-only",
            proposed_category_name="Root only",
            proposed_root_name="Root only",
            category_id=str(root.id),
            category_is_assignable=False,
            matched_rule="bad_rule",
            confidence=0.8,
            reason="target_root_forbidden",
            invalid_target=True,
            non_assignable_target=False,
            missing_target=False,
        )

        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "BOOT-003",
                "category": "Unknown",
                "article": "ROOT-001",
                "name": "Root conflict product",
                "rrc_currency_980": "120.00",
                "count_warehouse_3": "1",
                "Зображення товару": "https://cdn.example.com/root.webp"
              }
            ]
          }
        }
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl-bootstrap-root.json"
            file_path.write_text(payload, encoding="utf-8")
            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "current_offers"},
                is_active=True,
                auto_reprice=False,
            )
            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        product = Product.objects.get(sku="GPL-BOOT003")
        raw_offer = SupplierRawOffer.objects.get(run=run)
        self.assertIsNone(product.category_id)
        self.assertIsNone(raw_offer.mapped_category_id)
        self.assertEqual(raw_offer.category_mapping_status, SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW)
        self.assertEqual(run.summary["gpl_category_assignment"]["conflict"], 1)
        self.assertEqual(run.summary["gpl_category_assignment"]["invalid_target_count"], 1)
        self.assertEqual(Category.objects.count(), category_count_before)

    def test_import_row_limit_caps_processed_rows(self):
        payload = """
        {
          "data": {
            "items": [
              {"cid": "A-1", "category": "ARAL", "article": "AR-20488", "name": "A", "rrc_currency_980": "100.00", "count_warehouse_3": "1"},
              {"cid": "A-2", "category": "ARAL", "article": "AR-20488", "name": "B", "rrc_currency_980": "101.00", "count_warehouse_3": "1"},
              {"cid": "A-3", "category": "ARAL", "article": "AR-20488", "name": "C", "rrc_currency_980": "102.00", "count_warehouse_3": "1"}
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl-limit.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "current_offers"},
                is_active=True,
                auto_reprice=False,
            )

            result = SupplierImportRunner().run_source(source=source, trigger="test", row_limit=2)

        run = ImportRun.objects.get(id=result.run_id)
        self.assertEqual(run.parsed_rows, 2)
        self.assertEqual(run.processed_rows, 2)
        self.assertEqual(run.summary["row_limit"], 2)

    def test_repricing_after_import(self):
        PricingPolicy.objects.create(
            name="Global import policy",
            scope=PricingPolicy.SCOPE_GLOBAL,
            priority=100,
            percent_markup=Decimal("10.00"),
            fixed_markup=Decimal("5.00"),
            min_margin_percent=Decimal("0.00"),
            min_price=Decimal("0.00"),
            rounding_step=Decimal("1.00"),
            psychological_rounding=False,
            lock_auto_recalc=False,
            is_active=True,
        )

        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "rrc_currency_980": "100.00",
                "count_warehouse_3": "10"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                is_active=True,
                auto_reprice=True,
            )

            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        self.assertEqual(run.status, ImportRun.STATUS_SUCCESS)
        self.assertGreater(run.repriced_products, 0)

        history = PriceHistory.objects.filter(product=self.product, source=PriceHistory.SOURCE_IMPORT).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.new_price, Decimal("110.00"))

    def test_raw_history_persists_supplier_product_name_without_product_name_override(self):
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Supplier raw product name",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95"
              }
            ]
          }
        }
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "raw_history"},
                is_active=True,
                auto_reprice=False,
            )

            result = SupplierImportRunner().run_source(source=source, trigger="test")

        run = ImportRun.objects.get(id=result.run_id)
        raw_offer = SupplierRawOffer.objects.filter(run=run).first()
        self.assertIsNotNone(raw_offer)
        self.assertEqual(raw_offer.product_name, "Supplier raw product name")
        self.product.refresh_from_db()
        self.assertEqual(self.product.name_uk, "")
        self.assertEqual(self.product.name_ru, "")
        self.assertEqual(self.product.name_en, "")

    def test_utr_raw_history_dry_run_does_not_write_raw_or_business_rows(self):
        content = """Артикул UTR;Артикул;Найменування;Бренд;Валюта;Ціна;Київська обл.
UTR-001;AR-20488;UTR test row;ARAL;UAH;140.24;5
"""

        utr_supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        before_products = Product.objects.count()
        before_offers = SupplierOffer.objects.count()
        before_prices = ProductPrice.objects.count()
        before_raw_rows = SupplierRawOffer.objects.count()
        before_reviews = OfferMatchReview.objects.count()

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "utr.csv"
            file_path.write_text(content, encoding="utf-8")
            source = ImportSource.objects.create(
                code="utr",
                name="UTR",
                supplier=utr_supplier,
                parser_type=ImportSource.PARSER_UTR,
                input_path=str(file_path),
                parser_options={"persistence_mode": "raw_history"},
                is_active=True,
                auto_reprice=False,
            )
            result = SupplierImportRunner().run_source(source=source, trigger="test", dry_run=True)

        run = ImportRun.objects.get(id=result.run_id)
        self.assertTrue(run.dry_run)
        self.assertEqual(SupplierRawOffer.objects.filter(run=run).count(), 0)
        self.assertEqual(Product.objects.count(), before_products)
        self.assertEqual(SupplierOffer.objects.count(), before_offers)
        self.assertEqual(ProductPrice.objects.count(), before_prices)
        self.assertEqual(SupplierRawOffer.objects.count(), before_raw_rows)
        self.assertEqual(OfferMatchReview.objects.count(), before_reviews)

        self.assertIn("raw_history_rows", run.summary)
        self.assertEqual(run.summary["persistence_mode"], "raw_history")
        self.assertEqual(run.summary["raw_history_rows"]["raw_rows_written"], 0)
        self.assertEqual(run.summary["raw_history_rows"]["match_reviews_written"], 0)
        self.assertEqual(run.summary["raw_history_rows"]["would_create_raw_rows"], 1)
        self.assertEqual(run.summary["raw_history_rows"]["would_create_match_reviews"], 1)

    def test_gpl_current_offers_dry_run_remains_no_write(self):
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95"
              }
            ]
          }
        }
        """
        before_products = Product.objects.count()
        before_offers = SupplierOffer.objects.count()
        before_prices = ProductPrice.objects.count()
        before_raw_rows = SupplierRawOffer.objects.count()
        before_reviews = OfferMatchReview.objects.count()

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")
            source = ImportSource.objects.create(
                code="gpl-dry",
                name="GPL dry",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                parser_options={"persistence_mode": "current_offers"},
                is_active=True,
                auto_reprice=False,
            )
            result = SupplierImportRunner().run_source(source=source, trigger="test", dry_run=True)

        run = ImportRun.objects.get(id=result.run_id)
        self.assertTrue(run.dry_run)
        self.assertEqual(run.summary["persistence_mode"], "current_offers")
        self.assertEqual(run.summary["current_offer_rows"]["raw_offers_written"], 0)
        self.assertEqual(Product.objects.count(), before_products)
        self.assertEqual(SupplierOffer.objects.count(), before_offers)
        self.assertEqual(ProductPrice.objects.count(), before_prices)
        self.assertEqual(SupplierRawOffer.objects.count(), before_raw_rows)
        self.assertEqual(OfferMatchReview.objects.count(), before_reviews)

    @patch("apps.supplier_imports.services.import_runner.service.autodb_postprocess.SupplierImportAutoDbPostProcessor")
    def test_runner_passes_autodb_overrides_to_postprocess(self, postprocessor_cls_mock):
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95"
              }
            ]
          }
        }
        """
        summary_stub = SimpleNamespace(to_dict=lambda: {"enabled": True, "name_update_enabled": True})
        postprocessor_cls_mock.return_value.run_for_import.return_value = summary_stub

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                is_active=True,
                auto_reprice=False,
            )

            result = SupplierImportRunner().run_source(
                source=source,
                trigger="test",
                autodb_enrich=True,
                update_product_names=True,
                autodb_limit=15,
            )

        run = ImportRun.objects.get(id=result.run_id)
        postprocessor_cls_mock.return_value.run_for_import.assert_called_once()
        kwargs = postprocessor_cls_mock.return_value.run_for_import.call_args.kwargs
        self.assertEqual(kwargs["run"].id, run.id)
        self.assertFalse(kwargs["dry_run"])
        self.assertTrue(kwargs["autodb_enrich"])
        self.assertTrue(kwargs["update_product_names"])
        self.assertEqual(kwargs["limit"], 15)
        self.assertIsNone(kwargs["allow_remote_lookup"])
        self.assertIn("autodb_supplier_import", run.summary)

    @patch("apps.supplier_imports.services.import_runner.service.autodb_postprocess.SupplierImportAutoDbPostProcessor")
    def test_runner_passes_autodb_remote_override_to_postprocess(self, postprocessor_cls_mock):
        payload = """
        {
          "data": {
            "items": [
              {
                "cid": "0007523",
                "category": "ARAL",
                "article": "AR-20488",
                "name": "Aral BlueTronic 10W-40 1Lx12",
                "rrc_currency_980": "140.24",
                "count_warehouse_3": "95"
              }
            ]
          }
        }
        """
        summary_stub = SimpleNamespace(to_dict=lambda: {"enabled": True, "name_update_enabled": False})
        postprocessor_cls_mock.return_value.run_for_import.return_value = summary_stub

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "gpl.json"
            file_path.write_text(payload, encoding="utf-8")

            source = ImportSource.objects.create(
                code="gpl",
                name="GPL",
                supplier=self.supplier,
                parser_type=ImportSource.PARSER_GPL,
                input_path=str(file_path),
                is_active=True,
                auto_reprice=False,
            )

            SupplierImportRunner().run_source(
                source=source,
                trigger="test",
                autodb_enrich=True,
                autodb_allow_remote=True,
            )

        kwargs = postprocessor_cls_mock.return_value.run_for_import.call_args.kwargs
        self.assertTrue(kwargs["allow_remote_lookup"])
