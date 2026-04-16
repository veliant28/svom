from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.utils import timezone

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError


@dataclass(frozen=True)
class HttpJsonResponse:
    status: int
    payload: object


@dataclass(frozen=True)
class HttpBytesResponse:
    status: int
    body: bytes
    headers: dict[str, str]


def parse_datetime_maybe(value: str | None):
    if not value:
        return None

    variants = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    )
    for fmt in variants:
        try:
            dt = datetime.strptime(value, fmt)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(value)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except ValueError:
        return None


def http_json_request(
    *,
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> HttpJsonResponse:
    body: bytes | None = None
    request_headers = {"Accept": "application/json", **(headers or {})}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(
        url=url,
        method=method.upper(),
        headers=request_headers,
        data=body,
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            data = json.loads(raw) if raw else {}
            return HttpJsonResponse(status=response.status, payload=data)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        message = _extract_error_message(raw) or f"HTTP {exc.code}"
        raise SupplierClientError(message, status_code=exc.code) from exc
    except URLError as exc:
        raise SupplierClientError("Не удалось выполнить запрос к API поставщика.") from exc
    except json.JSONDecodeError as exc:
        raise SupplierClientError("Поставщик вернул некорректный ответ (не JSON).") from exc


def http_bytes_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> HttpBytesResponse:
    request_headers = headers or {}
    request = Request(
        url=url,
        method=method.upper(),
        headers=request_headers,
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return HttpBytesResponse(
                status=response.status,
                body=response.read(),
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        message = _extract_error_message(raw) or f"HTTP {exc.code}"
        raise SupplierClientError(message, status_code=exc.code) from exc
    except URLError as exc:
        raise SupplierClientError("Не удалось выполнить запрос к API поставщика.") from exc


def _extract_error_message(raw: str) -> str:
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()[:500]

    if isinstance(payload, dict):
        if isinstance(payload.get("message"), str):
            return payload["message"][:500]
        nested = payload.get("message")
        if isinstance(nested, dict) and isinstance(nested.get("message"), str):
            return nested["message"][:500]
        if isinstance(payload.get("detail"), str):
            return payload["detail"][:500]
    return raw.strip()[:500]
