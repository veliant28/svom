from __future__ import annotations

from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from apps.backoffice.services.supplier_price_workflow.lifecycle_actions.download import download_price_list
from apps.backoffice.services.supplier_price_workflow.lifecycle_actions.request import request_price_list
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource, SupplierIntegration, SupplierPriceList


class _StubService:
    def __init__(self, gpl_client):
        self.gpl_client = gpl_client
        self.guard = _StubGuard()


class _StubGuard:
    def get_status(self, *, integration):
        return type("CooldownStatus", (), {"wait_seconds": 0})()


class _StubGplClient:
    def fetch_prices_page(
        self,
        *,
        access_token: str,
        page: int = 1,
        per_page: int = 100,
        filter_payload: dict | None = None,
    ) -> dict:
        del access_token, per_page, filter_payload
        if page == 1:
            return {
                "meta": {"current_page": 1, "last_page": 2},
                "data": {
                    "titles": {
                        "cid": "Код",
                        "category": "Група",
                        "article": "Артикул",
                        "name": "Найменування",
                        "description": "Опис",
                        "price_currency_980": "Ціна UAH",
                        "count_warehouse_3": "Склад Київ",
                    },
                    "items": [
                        {
                            "cid": "0001",
                            "category": "ARAL",
                            "article": "AR-1",
                            "name": "Aral Example 1",
                            "description": "desc 1",
                            "price_currency_980": "100.00",
                            "count_warehouse_3": "2",
                        }
                    ],
                },
            }

        return {
            "meta": {"current_page": 2, "last_page": 2},
            "data": {
                "titles": {
                    "cid": "Код",
                    "category": "Група",
                    "article": "Артикул",
                    "name": "Найменування",
                    "description": "Опис",
                    "price_currency_980": "Ціна UAH",
                    "count_warehouse_3": "Склад Київ",
                },
                "items": [
                    {
                        "cid": "0002",
                        "category": "ARAL",
                        "article": "AR-2",
                        "name": "Aral Example 2",
                        "description": "desc 2",
                        "price_currency_980": "200.00",
                        "count_warehouse_3": "5",
                    }
                ],
            },
        }


class SupplierPriceWorkflowGplScheduleTests(TestCase):
    def setUp(self):
        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="/GPL.xlsx",
            is_active=True,
            is_auto_import_enabled=True,
        )
        self.integration = SupplierIntegration.objects.create(
            supplier=supplier,
            source=self.source,
            is_enabled=True,
            login="demo",
            password="demo",
            access_token="token",
            access_token_expires_at=timezone.now(),
        )

    def test_request_price_list_uses_gpl_api_mode_without_local_file(self):
        payload = request_price_list(
            _StubService(gpl_client=_StubGplClient()),
            supplier_code="gpl",
            requested_format="xlsx",
            in_stock=True,
            show_scancode=False,
            utr_article=False,
            visible_brands=[],
            categories=[],
            models_filter=[],
        )

        self.assertEqual(payload["request_mode"], "gpl_api")
        self.assertEqual(payload["status"], SupplierPriceList.STATUS_READY)

    def test_download_price_list_builds_runtime_xlsx_from_gpl_api(self):
        row = SupplierPriceList.objects.create(
            supplier=self.source.supplier,
            source=self.source,
            integration=self.integration,
            status=SupplierPriceList.STATUS_READY,
            request_mode="gpl_api",
            requested_format="xlsx",
            source_file_name="",
            source_file_path="",
        )

        payload = download_price_list(
            _StubService(gpl_client=_StubGplClient()),
            supplier_code="gpl",
            price_list_id=str(row.id),
        )
        row.refresh_from_db()

        self.assertEqual(row.status, SupplierPriceList.STATUS_DOWNLOADED)
        self.assertTrue(row.downloaded_file_path.endswith(".xlsx"))
        self.assertTrue(Path(row.downloaded_file_path).exists())
        self.assertEqual(row.row_count, 2)
        self.assertIn("price_currency_980", row.price_columns)
        self.assertIn("count_warehouse_3", row.warehouse_columns)
        self.assertEqual(payload["status"], SupplierPriceList.STATUS_DOWNLOADED)
