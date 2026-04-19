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

    def fetch_orders_page(self, *, access_token: str, page: int = 1) -> dict:
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/orders/all?page={max(int(page), 1)}",
            headers={"Authorization": f"Bearer {access_token}"},
            payload={},
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        if not isinstance(payload.get("data"), list):
            raise SupplierClientError("GPL вернул неожиданный формат списка заказов.")
        return payload

    def fetch_order(self, *, access_token: str, order_id: int) -> dict:
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/orders/show/{int(order_id)}",
            headers={"Authorization": f"Bearer {access_token}"},
            payload={},
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        if not isinstance(payload.get("data"), dict):
            raise SupplierClientError("GPL вернул неожиданный формат заказа.")
        return payload

    def create_order(
        self,
        *,
        access_token: str,
        products: list[dict[str, int]],
        test_mode: bool = False,
    ) -> dict:
        normalized_products: list[dict[str, int]] = []
        for row in products:
            product_id = int(row.get("id", 0))
            count = int(row.get("count", 0))
            if product_id <= 0 or count <= 0:
                continue
            normalized_products.append({"id": product_id, "count": count})

        if not normalized_products:
            raise SupplierClientError("GPL: требуется передать хотя бы один товар для оформления заказа.")

        payload: dict[str, object] = {
            "products": normalized_products,
            "test": "1" if test_mode else "0",
        }
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/orders/store",
            headers={"Authorization": f"Bearer {access_token}"},
            payload=payload,
        )
        body = response.payload if isinstance(response.payload, dict) else {}
        if not isinstance(body.get("data"), dict):
            raise SupplierClientError("GPL вернул неожиданный формат при создании заказа.")
        return body

    def cancel_order(self, *, access_token: str, order_id: int) -> dict:
        response = http_json_request(
            method="POST",
            url=f"{self.base_url}/api/orders/cancel/{int(order_id)}",
            headers={"Authorization": f"Bearer {access_token}"},
            payload={},
        )
        payload = response.payload if isinstance(response.payload, dict) else {}
        if not isinstance(payload.get("data"), dict):
            raise SupplierClientError("GPL вернул неожиданный формат при отмене заказа.")
        return payload
