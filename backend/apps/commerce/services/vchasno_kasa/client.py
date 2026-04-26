from __future__ import annotations

import json
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .exceptions import VchasnoKasaApiError, VchasnoKasaConfigError


class VchasnoKasaApiClient:
    BASE_URL = "https://kasa.vchasno.ua"

    def __init__(self, *, token: str, timeout_seconds: int = 20) -> None:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise VchasnoKasaConfigError(
                "API токен замовлень Вчасно не задан (Налаштування компанії -> Інтеграція замовлень -> API).",
                code="VCHASNO_KASA_TOKEN_MISSING",
            )
        self._token = normalized_token
        self._timeout_seconds = max(int(timeout_seconds), 5)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/api/v1/orders", payload)

    def list_orders(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/api/v1/orders/list", payload)

    def execute_fiscal(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/api/v3/fiscal/execute", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib_request.Request(
            url=f"{self.BASE_URL}{path}",
            data=raw_payload,
            headers={
                "Authorization": self._token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=self._timeout_seconds) as response:
                status_code = int(getattr(response, "status", 200))
                body = response.read()
        except urllib_error.HTTPError as exc:
            status_code = int(exc.code or 500)
            body = exc.read() if hasattr(exc, "read") else b""
        except urllib_error.URLError as exc:
            raise VchasnoKasaApiError("Не удалось подключиться к Вчасно.Каса.") from exc

        payload_json = _decode_payload(body)
        if status_code >= 400:
            message = _resolve_error_message(payload_json, status_code=status_code)
            raise VchasnoKasaApiError(
                message,
                status_code=status_code,
                details={"response": payload_json if isinstance(payload_json, dict) else {}},
            )
        if not isinstance(payload_json, dict):
            raise VchasnoKasaApiError("Вчасно.Каса вернула неподдерживаемый формат ответа.")
        return payload_json


def _decode_payload(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _resolve_error_message(payload_json: Any, *, status_code: int) -> str:
    fallback = f"Ошибка ответа Вчасно.Каса (HTTP {int(status_code)})."
    if not isinstance(payload_json, dict):
        return fallback

    for key in ("message", "detail", "error", "raw"):
        value = payload_json.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    errors = payload_json.get("errors")
    if isinstance(errors, str) and errors.strip():
        return errors.strip()
    if isinstance(errors, list):
        first_text = next((item for item in errors if isinstance(item, str) and item.strip()), "")
        if first_text:
            return first_text.strip()
        for item in errors:
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, str) and value.strip():
                        return value.strip()

    for value in payload_json.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            first_text = next((item for item in value if isinstance(item, str) and item.strip()), "")
            if first_text:
                return first_text.strip()

    return fallback
