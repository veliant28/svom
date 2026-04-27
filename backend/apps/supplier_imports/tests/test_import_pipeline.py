from __future__ import annotations

import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import PriceHistory, PricingPolicy, Supplier, SupplierOffer
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
