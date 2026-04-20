from __future__ import annotations

import json
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request



class MonobankApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class MonobankApiClient:
    BASE_URL = "https://api.monobank.ua"

    def __init__(self, *, token: str, timeout_seconds: int = 20):
        normalized_token = (token or "").strip()
        if not normalized_token:
            raise MonobankApiError("Monobank token is not configured.")
        self._token = normalized_token
        self._timeout_seconds = max(int(timeout_seconds), 5)

    def create_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            method="POST",
            path="/api/merchant/invoice/create",
            json_payload=payload,
        )

    def get_invoice_status(self, *, invoice_id: str) -> dict[str, Any]:
        return self._request_json(
            method="GET",
            path="/api/merchant/invoice/status",
            params={"invoiceId": invoice_id},
        )

    def cancel_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            method="POST",
            path="/api/merchant/invoice/cancel",
            json_payload=payload,
        )

    def remove_invoice(self, *, invoice_id: str) -> dict[str, Any]:
        return self._request_json(
            method="POST",
            path="/api/merchant/invoice/remove",
            json_payload={"invoiceId": invoice_id},
        )

    def finalize_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            method="POST",
            path="/api/merchant/invoice/finalize",
            json_payload=payload,
        )

    def get_invoice_fiscal_checks(self, *, invoice_id: str) -> dict[str, Any]:
        return self._request_json(
            method="GET",
            path="/api/merchant/invoice/fiscal-checks",
            params={"invoiceId": invoice_id},
        )

    def get_webhook_pubkey(self) -> str:
        payload = self._request_json(method="GET", path="/api/merchant/pubkey")

        if isinstance(payload, str):
            return payload.strip()
        if isinstance(payload, dict):
            for key in ("key", "pubkey", "publicKey", "value"):
                candidate = payload.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            for value in payload.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()
        raise MonobankApiError("Monobank returned an unsupported public key format.", payload=payload)

    def get_merchant_details(self) -> dict[str, Any]:
        return self._request_json(method="GET", path="/api/merchant/details")

    @staticmethod
    def get_public_currency() -> list[dict[str, Any]]:
        payload, status_code = _http_json_request(
            url="https://api.monobank.ua/bank/currency",
            method="GET",
            headers={},
            timeout_seconds=20,
        )
        if status_code >= 400:
            raise MonobankApiError("Monobank currency API request failed.", status_code=status_code, payload=payload)
        if not isinstance(payload, list):
            raise MonobankApiError("Monobank currency API returned an unsupported payload.", payload=payload)
        return payload

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        if params:
            query = urllib_parse.urlencode({key: value for key, value in params.items() if value is not None})
            if query:
                url = f"{url}?{query}"
        headers = {"X-Token": self._token}
        payload, status_code = _http_json_request(
            url=url,
            method=method,
            headers=headers,
            json_payload=json_payload,
            timeout_seconds=self._timeout_seconds,
        )
        if status_code >= 400:
            message = "Monobank API request failed."
            if isinstance(payload, dict):
                message = str(payload.get("errText") or payload.get("message") or payload.get("detail") or message)
            raise MonobankApiError(message, status_code=status_code, payload=payload)

        if not isinstance(payload, dict):
            raise MonobankApiError("Monobank API returned an unsupported payload.", payload=payload)

        return payload


def _http_json_request(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    timeout_seconds: int,
    json_payload: dict[str, Any] | None = None,
) -> tuple[Any, int]:
    request_headers = dict(headers)
    data_bytes: bytes | None = None
    if json_payload is not None:
        request_headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(json_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    request = urllib_request.Request(url=url, data=data_bytes, headers=request_headers, method=method.upper())

    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 200))
            raw = response.read()
    except urllib_error.HTTPError as exc:
        status_code = int(exc.code or 500)
        raw = exc.read() if hasattr(exc, "read") else b""
    except urllib_error.URLError as exc:
        raise MonobankApiError("Failed to reach Monobank API.") from exc

    payload = _decode_payload(raw)
    return payload, status_code


def _decode_payload(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
