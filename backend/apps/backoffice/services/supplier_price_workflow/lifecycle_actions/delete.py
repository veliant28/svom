from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierIntegrationError

from ..status import is_utr_nonfatal_delete_error
from .diagnostics import get_price_list_for_source, resolve_source_and_integration


def delete_price_list(service, *, supplier_code: str, price_list_id: str) -> dict[str, Any]:
    source, integration = resolve_source_and_integration(supplier_code=supplier_code)
    row = get_price_list_for_source(price_list_id=price_list_id, source_id=str(source.id))

    deleted_remote = False
    remote_delete_error = ""
    if supplier_code == "utr" and row.request_mode == "utr_api" and row.remote_id:
        if not integration.access_token:
            raise SupplierIntegrationError("Нельзя удалить прайс в UTR: отсутствует access token.")
        try:
            service.utr_client.delete_pricelist(
                access_token=integration.access_token,
                pricelist_id=row.remote_id,
            )
            deleted_remote = True
        except SupplierClientError as exc:
            if is_utr_nonfatal_delete_error(exc):
                remote_delete_error = str(exc)
            else:
                raise SupplierIntegrationError(f"Не удалось удалить прайс в UTR: {exc}") from exc

    deleted_file = False
    if row.downloaded_file_path:
        file_path = Path(row.downloaded_file_path)
        if file_path.exists() and file_path.is_file():
            try:
                file_path.unlink()
                deleted_file = True
            except OSError:
                deleted_file = False

    payload = {
        "deleted": True,
        "deleted_remote": deleted_remote,
        "deleted_file": deleted_file,
        "price_list_id": str(row.id),
        "remote_id": row.remote_id,
        "remote_delete_error": remote_delete_error,
    }
    row.delete()
    return payload
