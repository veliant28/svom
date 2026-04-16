from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import PriceHistory, PricingPolicy, Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRowError, ImportRun, ImportSource
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
