from __future__ import annotations

from typing import Any

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.services.integrations.gpl_client import GplClient
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.integrations.utr_client import UtrClient

from . import analyzers, diagnostics, gateway, lifecycle, serialization, status


class SupplierPriceWorkflowService:
    UTR_EXPECTED_GENERATION_SECONDS = 180
    PARAM_OPTIONS_LIMIT = 5000

    def __init__(self, *, guard=None, utr_client=None, gpl_client=None):
        self.guard = guard or SupplierRateLimitGuardService()
        self.utr_client = utr_client or UtrClient()
        self.gpl_client = gpl_client or GplClient()

    def list_price_lists(self, *, supplier_code: str) -> list[dict]:
        return lifecycle.list_price_lists(self, supplier_code=supplier_code)

    def get_request_params(self, *, supplier_code: str) -> dict[str, Any]:
        return lifecycle.get_request_params(self, supplier_code=supplier_code)

    def request_price_list(
        self,
        *,
        supplier_code: str,
        requested_format: str,
        in_stock: bool,
        show_scancode: bool,
        utr_article: bool,
        visible_brands: list[int] | None = None,
        categories: list[str] | None = None,
        models_filter: list[str] | None = None,
    ) -> dict:
        return lifecycle.request_price_list(
            self,
            supplier_code=supplier_code,
            requested_format=requested_format,
            in_stock=in_stock,
            show_scancode=show_scancode,
            utr_article=utr_article,
            visible_brands=visible_brands,
            categories=categories,
            models_filter=models_filter,
        )

    def download_price_list(self, *, supplier_code: str, price_list_id: str) -> dict:
        return lifecycle.download_price_list(self, supplier_code=supplier_code, price_list_id=price_list_id)

    def import_price_list_to_raw(self, *, supplier_code: str, price_list_id: str) -> dict:
        return lifecycle.import_price_list_to_raw(self, supplier_code=supplier_code, price_list_id=price_list_id)

    def delete_price_list(self, *, supplier_code: str, price_list_id: str) -> dict[str, Any]:
        return lifecycle.delete_price_list(self, supplier_code=supplier_code, price_list_id=price_list_id)

    # Back-compat private wrappers
    def _sync_utr_remote_price_lists(self, *, source, integration) -> None:
        gateway.sync_utr_remote_price_lists(self, source=source, integration=integration)

    def _get_price_list(self, *, price_list_id: str, source_id: str):
        return diagnostics.get_price_list(price_list_id=price_list_id, source_id=source_id)

    def _refresh_generating_state(self, *, row, supplier_code: str, integration) -> None:
        lifecycle.refresh_generating_state(self, row=row, supplier_code=supplier_code, integration=integration)

    def _hydrate_utr_remote_fields(self, *, row, access_token: str) -> None:
        gateway.hydrate_utr_remote_fields(self, row=row, access_token=access_token)

    def _extract_file_metadata(self, *, source_file, supplier_code: str):
        return analyzers.extract_file_metadata(source_file=source_file, supplier_code=supplier_code).to_dict()

    def _detect_price_columns(self, *, headers: list[str]) -> list[str]:
        return analyzers.detect_price_columns(headers=headers)

    def _detect_warehouse_columns(self, *, headers: list[str], supplier_code: str, price_columns: list[str]) -> list[str]:
        return analyzers.detect_warehouse_columns(headers=headers, supplier_code=supplier_code, price_columns=price_columns)

    def _resolve_source_file_path(self, raw_path: str):
        return analyzers.resolve_source_file_path(raw_path)

    def _resolve_extension(self, *, requested_format: str, source_file_name: str) -> str:
        return analyzers.resolve_extension(requested_format=requested_format, source_file_name=source_file_name)

    def _extract_remote_status(self, payload: dict | str) -> str:
        return status.extract_remote_status(payload)

    def _normalize_status_value(self, value: Any) -> str:
        return status.normalize_status_value(value)

    def _is_ready_status(self, status_value: str) -> bool:
        return status.is_ready_status(status_value)

    def _is_failed_status(self, status_value: str) -> bool:
        return status.is_failed_status(status_value)

    def _is_utr_nonfatal_delete_error(self, exc: SupplierClientError) -> bool:
        return status.is_utr_nonfatal_delete_error(exc)

    def _generation_wait_seconds(self, *, row) -> int:
        return status.generation_wait_seconds(expected_ready_at=row.expected_ready_at)

    def _serialize_price_list(self, *, row, cooldown_wait_seconds: int) -> dict[str, Any]:
        return serialization.serialize_price_list(row=row, cooldown_wait_seconds=cooldown_wait_seconds)

    def _human_size(self, size: int) -> str:
        return analyzers.human_size(size)
