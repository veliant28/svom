from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UtrBatchSearchResult:
    rows: list[dict]
    access_token: str
    auth_retry_performed: bool = False
    auth_retry_method: str = ""


def search_details(
    client,
    *,
    access_token: str,
    oem: str,
    brand: str = "",
    force_refresh: bool | None = None,
    request_reason: str = "detail_search",
) -> list[dict]:
    normalized_oem = str(oem or "").strip()
    if not normalized_oem:
        return []

    query_params = {}
    normalized_brand = str(brand or "").strip()
    if normalized_brand:
        query_params["brand"] = normalized_brand

    query_string = f"?{urlencode(query_params)}" if query_params else ""
    url = f"{client.base_url}/api/search/{quote(normalized_oem, safe='')}{query_string}"
    cache_key = client._cache_key("search", normalized_oem, normalized_brand)
    response = client._safe_json_request(
        method="GET",
        url=url,
        headers={"Authorization": f"Bearer {access_token}"},
        cache_key=cache_key,
        force_refresh=force_refresh,
        request_reason=request_reason,
    )
    payload = response.payload if isinstance(response.payload, dict) else {}
    details = payload.get("details")
    if details is None:
        return []
    if not isinstance(details, list):
        raise SupplierClientError("UTR вернул неожиданный формат поиска деталей.")

    rows: list[dict] = []
    for item in details:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def search_details_batch(
    client,
    *,
    access_token: str,
    details: list[dict],
    force_refresh: bool | None = None,
    request_reason: str = "detail_search_batch",
) -> UtrBatchSearchResult:
    normalized_queries: list[dict[str, str]] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        oem = str(item.get("oem") or item.get("article") or "").strip()
        if not oem:
            continue
        brand = str(item.get("brand") or "").strip()
        normalized_queries.append(
            {
                "oem": oem,
                "brand": brand,
            }
        )
    if not normalized_queries:
        return UtrBatchSearchResult(rows=[], access_token=access_token)

    should_force_refresh = client._resolve_force_refresh(force_refresh)
    rows: list[dict] = [{"details": []} for _ in normalized_queries]
    current_access_token = str(access_token or "").strip()
    auth_retry_performed = False
    auth_retry_method = ""
    pending_payload: list[dict] = []
    pending_indexes: list[int] = []

    if not should_force_refresh:
        for index, query in enumerate(normalized_queries):
            cache_key = client._cache_key("search", query["oem"], query["brand"])
            cached_payload = client._cache_get(cache_key)
            if isinstance(cached_payload, dict) and isinstance(cached_payload.get("details"), list):
                cached_details = [item for item in cached_payload.get("details") or [] if isinstance(item, dict)]
                rows[index] = {"details": cached_details}
                client._increment_metric("requests_skipped_cache")
                continue
            payload_item = {"oem": query["oem"]}
            if query["brand"]:
                payload_item["brand"] = query["brand"]
            pending_payload.append(payload_item)
            pending_indexes.append(index)
    else:
        for index, query in enumerate(normalized_queries):
            payload_item = {"oem": query["oem"]}
            if query["brand"]:
                payload_item["brand"] = query["brand"]
            pending_payload.append(payload_item)
            pending_indexes.append(index)

    if pending_payload:
        try:
            response = client._safe_json_request(
                method="POST",
                url=f"{client.base_url}/api/search",
                headers={"Authorization": f"Bearer {current_access_token}"},
                payload={"details": pending_payload},
                force_refresh=True,
                request_reason=request_reason,
            )
        except SupplierClientError as exc:
            if client.is_expired_token_error(exc):
                logger.warning("[UTR] expired-access-token detected during batch search, trying auth recovery.")
                recovered_token, auth_method = client._recover_access_token_for_utr()
                if recovered_token:
                    auth_retry_performed = True
                    auth_retry_method = auth_method
                    current_access_token = recovered_token
                    client._increment_metric("auth_retry_batch_total")
                    logger.info(
                        "[UTR] batch-auth-retry method=%s batch_size=%s reason=%s",
                        auth_method,
                        len(pending_payload),
                        request_reason,
                    )
                    response = client._safe_json_request(
                        method="POST",
                        url=f"{client.base_url}/api/search",
                        headers={"Authorization": f"Bearer {current_access_token}"},
                        payload={"details": pending_payload},
                        force_refresh=True,
                        request_reason=request_reason,
                    )
                else:
                    raise
            else:
                raise
        payload = response.payload
        if not isinstance(payload, list):
            raise SupplierClientError("UTR вернул неожиданный формат пакетного поиска деталей.")

        for result_index, original_index in enumerate(pending_indexes):
            response_item: dict = {}
            if result_index < len(payload) and isinstance(payload[result_index], dict):
                response_item = payload[result_index]
            query = normalized_queries[original_index]
            details_payload = response_item.get("details")
            if isinstance(details_payload, list):
                normalized_details = [item for item in details_payload if isinstance(item, dict)]
                rows[original_index] = {"details": normalized_details}
                cache_key = client._cache_key("search", query["oem"], query["brand"])
                client._cache_set(cache_key, {"details": normalized_details}, timeout=client.cache_ttl_seconds)
            elif isinstance(response_item.get("error"), str):
                rows[original_index] = {"error": response_item["error"]}
            else:
                rows[original_index] = {"details": []}

    return UtrBatchSearchResult(
        rows=rows,
        access_token=current_access_token,
        auth_retry_performed=auth_retry_performed,
        auth_retry_method=auth_retry_method,
    )
