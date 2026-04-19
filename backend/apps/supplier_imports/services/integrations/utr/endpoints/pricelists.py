from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


def get_pricelist_export_params(client, *, access_token: str) -> dict:
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/pricelists/export-params",
        headers={"Authorization": f"Bearer {access_token}"},
        request_reason="pricelist_export_params",
    )
    payload = response.payload
    if not isinstance(payload, dict):
        raise SupplierClientError("UTR вернул неожиданный формат параметров прайса.")
    return payload


def request_pricelist_export(client, *, access_token: str, payload: dict) -> dict:
    response = client._safe_json_request(
        method="POST",
        url=f"{client.base_url}/pricelists/export-request",
        headers={"Authorization": f"Bearer {access_token}"},
        payload=payload,
        force_refresh=True,
        request_reason="pricelist_export_request",
    )
    body = response.payload
    if not isinstance(body, dict):
        raise SupplierClientError("UTR вернул неожиданный формат ответа на запрос прайса.")
    return body


def get_pricelist_status(client, *, access_token: str, pricelist_id: str) -> dict | str:
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/pricelists/{pricelist_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        request_reason="pricelist_status",
    )
    payload = response.payload
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return payload
    raise SupplierClientError("UTR вернул неожиданный формат статуса прайса.")


def list_pricelists(client, *, access_token: str) -> list[dict]:
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/pricelists",
        headers={"Authorization": f"Bearer {access_token}"},
        request_reason="pricelists_list",
    )
    payload = response.payload
    if not isinstance(payload, list):
        raise SupplierClientError("UTR вернул неожиданный формат списка прайсов.")
    rows: list[dict] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def download_pricelist(client, *, access_token: str, export_token: str) -> tuple[bytes, str]:
    response = client._safe_bytes_request(
        method="GET",
        url=f"{client.base_url}/pricelists/export/{export_token}",
        headers={"Authorization": f"Bearer {access_token}"},
        request_reason="pricelist_download",
    )
    content_type = response.headers.get("content-type", "")
    return response.body, content_type


def delete_pricelist(client, *, access_token: str, pricelist_id: str) -> dict:
    response = client._safe_json_request(
        method="DELETE",
        url=f"{client.base_url}/pricelists/delete/{pricelist_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        force_refresh=True,
        request_reason="pricelist_delete",
    )
    payload = response.payload
    if isinstance(payload, dict):
        return payload
    return {}
