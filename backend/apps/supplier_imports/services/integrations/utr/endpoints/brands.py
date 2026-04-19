from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


def check_connection(client, *, access_token: str) -> dict:
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/api/brands",
        headers={"Authorization": f"Bearer {access_token}"},
        request_reason="connection_check",
    )
    payload = response.payload
    if isinstance(payload, list):
        return {
            "ok": True,
            "brands_count": len(payload),
        }
    if isinstance(payload, dict):
        return {"ok": True, "payload": payload}
    return {"ok": True}


def fetch_brands(client, *, access_token: str) -> list[dict]:
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/api/brands",
        headers={"Authorization": f"Bearer {access_token}"},
        request_reason="brands_fetch",
    )
    payload = response.payload
    if not isinstance(payload, list):
        raise SupplierClientError("UTR вернул неожиданный формат списка брендов.")
    rows: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        external_code = str(item.get("externalCode", "")).strip()
        rows.append(
            {
                "name": name,
                "external_code": external_code,
            }
        )
    return rows
