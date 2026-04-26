from __future__ import annotations

import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource, SupplierPriceList
from apps.supplier_imports.services.price_list_file_cleanup import SupplierPriceListFileCleanupService


class SupplierPriceListFileCleanupServiceTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.source = ImportSource.objects.create(
            code="utr",
            name="UTR",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
        )

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_deletes_stale_downloaded_file_and_clears_db_path(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            file_path = self._write_price_file("utr/stale.xlsx")
            price_list = SupplierPriceList.objects.create(
                supplier=self.supplier,
                source=self.source,
                status=SupplierPriceList.STATUS_DOWNLOADED,
                downloaded_file_path=str(file_path),
                downloaded_at=timezone.now() - timedelta(hours=49),
            )

            result = SupplierPriceListFileCleanupService().cleanup(retention_hours=48)

            price_list.refresh_from_db()
            self.assertFalse(file_path.exists())
            self.assertEqual(price_list.downloaded_file_path, "")
            self.assertEqual(price_list.status, SupplierPriceList.STATUS_READY)
            self.assertEqual(result.files_deleted, 1)
            self.assertEqual(result.db_paths_cleared, 1)

    def test_deletes_stale_orphan_file_under_supplier_price_lists(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            file_path = self._write_price_file("utr/orphan.xlsx")
            old_timestamp = (timezone.now() - timedelta(hours=49)).timestamp()
            os.utime(file_path, (old_timestamp, old_timestamp))

            result = SupplierPriceListFileCleanupService().cleanup(retention_hours=48)

            self.assertFalse(file_path.exists())
            self.assertEqual(result.orphan_files_deleted, 1)

    def test_skips_downloaded_path_outside_supplier_price_lists(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            external_path = Path(self.media_root) / "external.xlsx"
            external_path.write_text("keep", encoding="utf-8")
            price_list = SupplierPriceList.objects.create(
                supplier=self.supplier,
                source=self.source,
                status=SupplierPriceList.STATUS_DOWNLOADED,
                downloaded_file_path=str(external_path),
                downloaded_at=timezone.now() - timedelta(hours=49),
            )

            result = SupplierPriceListFileCleanupService().cleanup(retention_hours=48)

            price_list.refresh_from_db()
            self.assertTrue(external_path.exists())
            self.assertEqual(price_list.downloaded_file_path, str(external_path))
            self.assertEqual(result.unsafe_paths_skipped, 1)

    def _write_price_file(self, relative_path: str) -> Path:
        file_path = Path(self.media_root) / "supplier_price_lists" / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("price", encoding="utf-8")
        return file_path
