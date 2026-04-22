from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


def _extract_message(payload: object) -> str:
    if isinstance(payload, str):
        return payload.strip()[:500]
    if not isinstance(payload, dict):
        return ""

    for key in ("message", "detail", "error", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
        if isinstance(value, dict):
            nested = _extract_message(value)
            if nested:
                return nested
    return ""


def _looks_like_problem_payload(payload: dict) -> bool:
    status = payload.get("status")
    has_problem_keys = any(key in payload for key in ("title", "detail", "type"))
    if has_problem_keys and isinstance(status, int):
        return True
    if has_problem_keys and isinstance(status, str) and status.strip().isdigit():
        return True
    if "class" in payload and "trace" in payload and "detail" in payload:
        return True
    return False


def _normalize_applicability_payload(payload: object) -> list[dict] | None:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, str):
        message = payload.strip()
        if message:
            raise SupplierClientError(message[:500])
        return []
    if not isinstance(payload, dict):
        return None

    # UTR sometimes returns problem-details object instead of applicability rows.
    # Treat it as empty applicability for this detail_id.
    if _looks_like_problem_payload(payload):
        return []

    # Direct single-row object shape.
    if isinstance(payload.get("manufacturer"), str) and isinstance(payload.get("models"), list):
        return [payload]

    # Common wrappers seen in UTR responses across endpoint versions.
    for key in ("data", "items", "result", "applicability", "rows", "payload", "response", "list"):
        if key not in payload:
            continue
        nested = _normalize_applicability_payload(payload.get(key))
        if nested is not None:
            return nested

    # Some responses can have a single unknown top-level envelope.
    if len(payload) == 1:
        (_, only_value), = payload.items()
        nested = _normalize_applicability_payload(only_value)
        if nested is not None:
            return nested

    return None


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

    rows = _normalize_applicability_payload(payload)
    if rows is not None:
        return rows

    message = _extract_message(payload)
    if message:
        raise SupplierClientError(message)

    if isinstance(payload, dict):
        keys = ",".join(sorted(str(key) for key in payload.keys())[:12])
        if keys:
            raise SupplierClientError(f"UTR вернул неожиданный формат применяемости (keys: {keys}).")
    raise SupplierClientError("UTR вернул неожиданный формат применяемости.")


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
