from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.commerce.models import VchasnoKasaSettings
from apps.commerce.services.vchasno_kasa import service


class VchasnoKasaShiftStatusTests(SimpleTestCase):
    def test_shift_status_zero_is_closed_even_if_shift_id_present(self):
        payload = service._serialize_shift_status_from_response(
            response={
                "res": 0,
                "errortxt": "",
                "info": {
                    "shift_status": 0,
                    "shift_id": "10298847-ce47-668c-0e9a-cbd189550966",
                },
            }
        )

        self.assertEqual(payload["status_key"], "closed")
        self.assertFalse(payload["is_open"])
        self.assertEqual(payload["message"], "Зміну закрито.")

    def test_shift_status_one_is_open(self):
        payload = service._serialize_shift_status_from_response(
            response={
                "res": 0,
                "errortxt": "",
                "info": {
                    "shift_status": 1,
                    "shift_id": "shift-open-1",
                },
            }
        )

        self.assertEqual(payload["status_key"], "open")
        self.assertTrue(payload["is_open"])
        self.assertEqual(payload["message"], "Зміну відкрито.")

    @patch("apps.commerce.services.vchasno_kasa.service.VchasnoKasaApiClient.execute_fiscal")
    @patch("apps.commerce.services.vchasno_kasa.service.get_vchasno_kasa_settings")
    def test_close_shift_handles_already_closed_response(self, mock_get_settings, mock_execute_fiscal):
        mock_get_settings.return_value = VchasnoKasaSettings(
            is_enabled=True,
            api_token="orders-token",
            fiscal_api_token="fiscal-token",
        )
        mock_execute_fiscal.return_value = {
            "res": 2007,
            "errortxt": "Необхідно відкрити зміну",
            "info": {},
        }

        payload = service.close_vchasno_shift()

        self.assertEqual(payload["status_key"], "closed")
        self.assertFalse(payload["is_open"])
        self.assertTrue(payload["can_open"])
        self.assertEqual(payload["message"], "Зміну закрито.")

    @patch("apps.commerce.services.vchasno_kasa.service.VchasnoKasaApiClient.execute_fiscal")
    @patch("apps.commerce.services.vchasno_kasa.service.get_vchasno_kasa_settings")
    def test_close_shift_uses_task_eleven(self, mock_get_settings, mock_execute_fiscal):
        mock_get_settings.return_value = VchasnoKasaSettings(
            is_enabled=True,
            api_token="orders-token",
            fiscal_api_token="fiscal-token",
        )
        mock_execute_fiscal.return_value = {
            "res": 0,
            "errortxt": "",
            "info": {"shift_id": "s-1"},
        }

        payload = service.close_vchasno_shift()

        mock_execute_fiscal.assert_called_once_with({"fiscal": {"task": 11, "cashier": "SVOM"}})
        self.assertEqual(payload["status_key"], "closed")
        self.assertFalse(payload["is_open"])
        self.assertEqual(payload["message"], "Зміну закрито.")

    @patch("apps.commerce.services.vchasno_kasa.service.open_vchasno_shift")
    @patch("apps.commerce.services.vchasno_kasa.service.VchasnoKasaApiClient.execute_fiscal")
    def test_auto_open_shift_for_receipt_calls_open_when_closed(self, mock_execute_fiscal, mock_open_shift):
        settings = VchasnoKasaSettings(
            is_enabled=True,
            api_token="orders-token",
            fiscal_api_token="fiscal-token",
        )
        mock_execute_fiscal.return_value = {
            "res": 0,
            "errortxt": "",
            "info": {"shift_status": 0, "shift_id": "s-1"},
        }

        service._auto_open_shift_for_receipt_if_closed(settings=settings)

        mock_execute_fiscal.assert_called_once_with({"fiscal": {"task": 18}})
        mock_open_shift.assert_called_once()

    @patch("apps.commerce.services.vchasno_kasa.service._apply_provider_payload")
    @patch("apps.commerce.services.vchasno_kasa.service.VchasnoKasaApiClient.create_order")
    @patch("apps.commerce.services.vchasno_kasa.service.build_vchasno_order_payload")
    @patch("apps.commerce.services.vchasno_kasa.service._get_or_create_sale_receipt")
    @patch("apps.commerce.services.vchasno_kasa.service._auto_open_shift_for_receipt_if_closed")
    @patch("apps.commerce.services.vchasno_kasa.service.ensure_vchasno_kasa_settings_ready")
    def test_issue_receipt_attempts_auto_open_shift(
        self,
        mock_ensure_ready,
        mock_auto_open,
        mock_get_receipt,
        mock_build_payload,
        mock_create_order,
        mock_apply_payload,
    ):
        settings = VchasnoKasaSettings(
            is_enabled=True,
            api_token="orders-token",
            fiscal_api_token="fiscal-token",
            rro_fn="PRRO-1",
        )
        receipt = SimpleNamespace(receipt_url="", fiscal_status_code=None, response_payload=None)
        mock_ensure_ready.return_value = settings
        mock_get_receipt.return_value = receipt
        mock_build_payload.return_value = {"data": {}}
        mock_create_order.return_value = {"statusCode": 11}

        result = service.issue_order_receipt(order=SimpleNamespace(), actor=None)

        self.assertIs(result, receipt)
        mock_auto_open.assert_called_once_with(settings=settings)
        mock_apply_payload.assert_called_once()

    @patch("apps.commerce.services.vchasno_kasa.service._apply_provider_payload")
    @patch("apps.commerce.services.vchasno_kasa.service.VchasnoKasaApiClient.create_order")
    @patch("apps.commerce.services.vchasno_kasa.service.build_vchasno_order_payload")
    @patch("apps.commerce.services.vchasno_kasa.service._get_or_create_sale_receipt")
    @patch("apps.commerce.services.vchasno_kasa.service.sync_order_receipt")
    @patch("apps.commerce.services.vchasno_kasa.service._auto_open_shift_for_receipt_if_closed")
    @patch("apps.commerce.services.vchasno_kasa.service.ensure_vchasno_kasa_settings_ready")
    def test_issue_receipt_does_not_force_sync_after_error_response(
        self,
        mock_ensure_ready,
        mock_auto_open,
        mock_sync,
        mock_get_receipt,
        mock_build_payload,
        mock_create_order,
        mock_apply_payload,
    ):
        settings = VchasnoKasaSettings(
            is_enabled=True,
            api_token="orders-token",
            fiscal_api_token="fiscal-token",
            rro_fn="PRRO-1",
        )
        receipt = SimpleNamespace(
            receipt_url="",
            fiscal_status_code=None,
            response_payload={"response": {"code": 1001}},
            error_code="VCHASNO_KASA_ERROR",
            error_message="Помилка при перевірці даних",
        )
        mock_ensure_ready.return_value = settings
        mock_get_receipt.return_value = receipt
        mock_build_payload.return_value = {"data": {}}
        mock_create_order.return_value = {"statusCode": 11}

        result = service.issue_order_receipt(order=SimpleNamespace(), actor=None)

        self.assertIs(result, receipt)
        mock_sync.assert_not_called()
        mock_create_order.assert_called_once()
        mock_apply_payload.assert_called_once()

    def test_resolve_receipt_status_key_prefers_error_when_status_missing(self):
        receipt = SimpleNamespace(
            fiscal_status_key="",
            fiscal_status_code=None,
            error_code="VCHASNO_KASA_ERROR",
            error_message="Помилка при перевірці даних",
        )

        status_key = service._resolve_receipt_status_key(receipt=receipt)

        self.assertEqual(status_key, "error")
