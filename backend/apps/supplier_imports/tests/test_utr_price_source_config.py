from __future__ import annotations

from django.test import TestCase

from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.selectors import ensure_default_import_sources
from apps.supplier_imports.tasks.run_scheduled_supplier_pipeline import run_scheduled_supplier_pipeline_task


class UtrPriceSourceConfigTests(TestCase):
    def test_default_utr_price_source_still_exists(self):
        sources = ensure_default_import_sources()
        source = sources["utr"]

        self.assertEqual(source.code, "utr")
        self.assertEqual(source.parser_type, ImportSource.PARSER_UTR)
        self.assertEqual(source.supplier.code, "utr")

    def test_scheduled_price_import_task_uses_default_queue(self):
        self.assertIn(getattr(run_scheduled_supplier_pipeline_task, "queue", None), (None, ""))
