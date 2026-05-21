from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from django.conf import settings

from apps.autodb.services.remote_config import AutoDbRemoteConfigValidator


def _safe_str(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed


class AutoDbPublicApiClient:
    def __init__(self, *, base_url: str | None = None):
        self.base_url = _safe_str(base_url or getattr(settings, "AUTODB_MANUAL_SEARCH_REMOTE_API_BASE_URL", "https://auto-db.pro/api/v1/"))

    def search(self, *, query: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            action="search",
            params={"q": _safe_str(query)},
        )
        if not isinstance(payload, list):
            return []
        return [row for row in payload if isinstance(row, dict)]

    def search_candidates(self, *, article: str, limit: int = 80) -> list[dict[str, Any]]:
        raw_rows = self.search(query=article)
        grouped: dict[tuple[int, str], dict[str, Any]] = {}
        for row in raw_rows:
            supplier_id = _safe_int(
                row.get("supplierId")
                or row.get("supplierid")
                or row.get("SupplierId")
            )
            matched_article = _safe_str(
                row.get("DataSupplierArticleNumber")
                or row.get("datasupplierarticlenumber")
                or row.get("articleNumber")
                or row.get("articlenumber")
                or row.get("number")
            ).upper()
            if supplier_id is None or not matched_article:
                continue
            key = (supplier_id, matched_article)
            if key not in grouped:
                grouped[key] = {
                    "supplier_id": supplier_id,
                    "matched_stored_article": matched_article,
                    "hits": 0,
                    "matched_table": "auto-db.pro:search",
                }
            grouped[key]["hits"] = int(grouped[key]["hits"]) + 1

        ordered = sorted(
            grouped.values(),
            key=lambda item: (-int(item.get("hits") or 0), int(item.get("supplier_id") or 0), _safe_str(item.get("matched_stored_article"))),
        )
        return ordered[: max(int(limit or 0), 1)]

    def _get_json(self, *, action: str, params: dict[str, object]) -> Any:
        query_params = {"action": action}
        for key, value in params.items():
            query_params[key] = value

        endpoint = urljoin(
            self.base_url if self.base_url.endswith("/") else f"{self.base_url}/",
            f"?{urlencode(query_params)}",
        )

        snapshot = AutoDbRemoteConfigValidator.snapshot()
        username = _safe_str(snapshot.user)
        password = str(snapshot.password or "")
        if not username or not password:
            return []

        auth_value = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        request = Request(
            endpoint,
            method="GET",
            headers={
                "Accept": "*/*",
                "Authorization": f"Basic {auth_value}",
                "User-Agent": "curl/8.4.0",
            },
        )
        timeout = max(int(getattr(settings, "AUTODB_PRO_REMOTE_READ_TIMEOUT", 30) or 30), 5)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                body = response.read()
        except (HTTPError, URLError, TimeoutError, OSError):
            return []

        try:
            text = body.decode("utf-8-sig").lstrip("\ufeff")
            return json.loads(text)
        except Exception:  # noqa: BLE001
            return []

