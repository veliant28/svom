from __future__ import annotations

import os
from dataclasses import dataclass

from apps.supplier_imports.services.integrations.client_utils import http_json_request
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


@dataclass(frozen=True)
class GplTokenResult:
    access_token: str
    expires_in: int | None


class GplClient:
    def __init__(self, *, base_url: str | None = None):
        raw = base_url or os.getenv("GPL_API_BASE_URL", "https://online.gpl.ua")
        self.base_url = raw.rstrip("/")

    def obtain_token(self, *, login: str, password: str) -> GplTokenResult:
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/auth/login",
            payload={"login": login, "password": password},
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        token = str(payload.get("access_token", "")).strip()
        if not token:
            raise SupplierClientError("GPL не вернул access token.")

        expires_in_raw = payload.get("expires_in")
        expires_in: int | None = None
        if isinstance(expires_in_raw, int):
            expires_in = expires_in_raw
        elif isinstance(expires_in_raw, str) and expires_in_raw.isdigit():
            expires_in = int(expires_in_raw)

        return GplTokenResult(access_token=token, expires_in=expires_in)

    def refresh_token(self, *, access_token: str) -> GplTokenResult:
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/auth/refresh",
            headers={"Authorization": f"Bearer {access_token}"},
            payload={},
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        token = str(payload.get("access_token", "")).strip()
        if not token:
            raise SupplierClientError("GPL не вернул обновленный access token.")

        expires_in_raw = payload.get("expires_in")
        expires_in: int | None = None
        if isinstance(expires_in_raw, int):
            expires_in = expires_in_raw
        elif isinstance(expires_in_raw, str) and expires_in_raw.isdigit():
            expires_in = int(expires_in_raw)

        return GplTokenResult(access_token=token, expires_in=expires_in)

    def check_connection(self, *, access_token: str) -> dict:
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            payload={},
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        return {
            "ok": True,
            "login": payload.get("login", ""),
            "name": payload.get("name", ""),
        }

    def fetch_prices_page(
        self,
        *,
        access_token: str,
        page: int = 1,
        filter_payload: dict | None = None,
    ) -> dict:
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/prices?page={max(int(page), 1)}",
            headers={"Authorization": f"Bearer {access_token}"},
            payload={"filter": filter_payload or {}},
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        if not isinstance(payload.get("data"), dict):
            raise SupplierClientError("GPL вернул неожиданный формат страницы прайса.")
        return payload
