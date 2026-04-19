from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


def fetch_applicability(
    client,
    *,
    access_token: str,
    detail_id: str,
    force_refresh: bool | None = None,
    request_reason: str = "detail_applicability",
) -> list[dict]:
    normalized_detail_id = str(detail_id or "").strip()
    cache_key = client._cache_key("applicability", normalized_detail_id)
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/api/applicability/{normalized_detail_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        cache_key=cache_key,
        force_refresh=force_refresh,
        request_reason=request_reason,
    )
    payload = response.payload
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise SupplierClientError("UTR вернул неожиданный формат применяемости.")
    rows: list[dict] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def fetch_detail(
    client,
    *,
    access_token: str,
    detail_id: str,
    force_refresh: bool | None = None,
    request_reason: str = "detail_info",
) -> dict:
    normalized_detail_id = str(detail_id or "").strip()
    cache_key = client._cache_key("detail", normalized_detail_id)
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/api/detail/{normalized_detail_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        cache_key=cache_key,
        force_refresh=force_refresh,
        request_reason=request_reason,
    )
    payload = response.payload
    if not isinstance(payload, dict):
        raise SupplierClientError("UTR вернул неожиданный формат информации о детали.")
    return payload


def fetch_characteristics(
    client,
    *,
    access_token: str,
    detail_id: str,
    force_refresh: bool | None = None,
    request_reason: str = "detail_characteristics",
) -> list[dict]:
    normalized_detail_id = str(detail_id or "").strip()
    cache_key = client._cache_key("characteristics", normalized_detail_id)
    response = client._safe_json_request(
        method="GET",
        url=f"{client.base_url}/api/characteristics/{normalized_detail_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        cache_key=cache_key,
        force_refresh=force_refresh,
        request_reason=request_reason,
    )
    payload = response.payload
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise SupplierClientError("UTR вернул неожиданный формат характеристик.")
    rows: list[dict] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
    return rows
