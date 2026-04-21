from __future__ import annotations

import json
import uuid
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.utils import timezone

from apps.commerce.models import NovaPaySettings

NOVAPAY_API_BASE_URL = "https://api-qecom.novapay.ua"
NOVAPAY_STATUS_PATH = "/v1/get-status"


class NovaPayApiError(RuntimeError):
    pass


def get_novapay_settings() -> NovaPaySettings:
    settings, _ = NovaPaySettings.objects.get_or_create(code=NovaPaySettings.DEFAULT_CODE)
    return settings


def test_novapay_connection() -> dict[str, Any]:
    settings = get_novapay_settings()
    merchant_id = str(settings.merchant_id or "").strip()
    api_token = str(settings.api_token or "").strip()
    if not merchant_id:
        return _save_check_result(settings=settings, ok=False, message="NovaPay merchant_id is not configured.")
    if not api_token:
        return _save_check_result(settings=settings, ok=False, message="NovaPay API token (X-Sign) is not configured.")

    status_code: int
    payload: dict[str, Any]
    try:
        status_code, payload = _request_status(
            merchant_id=merchant_id,
            api_token=api_token,
            session_id=str(uuid.uuid4()),
        )
    except NovaPayApiError as exc:
        return _save_check_result(settings=settings, ok=False, message=str(exc))

    code = str(payload.get("code") or "").strip()
    error_message = str(payload.get("error") or "").strip()

    if status_code == 200:
        return _save_check_result(settings=settings, ok=True, message="Connection successful.")
    if status_code == 400 and code == "SessionNotFoundError":
        return _save_check_result(
            settings=settings,
            ok=True,
            message="Connection successful (test session not found).",
        )
    if status_code in {401, 403}:
        message = error_message or code or "NovaPay credentials are invalid."
        return _save_check_result(settings=settings, ok=False, message=message)
    message = error_message or code or f"NovaPay API returned HTTP {status_code}."
    return _save_check_result(settings=settings, ok=False, message=message)


def _request_status(*, merchant_id: str, api_token: str, session_id: str) -> tuple[int, dict[str, Any]]:
    payload = {
        "merchant_id": merchant_id,
        "session_id": session_id,
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib_request.Request(
        url=f"{NOVAPAY_API_BASE_URL}{NOVAPAY_STATUS_PATH}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Sign": api_token,
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return int(response.status), _parse_json(raw)
    except urllib_error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        return int(exc.code), _parse_json(raw)
    except urllib_error.URLError as exc:
        raise NovaPayApiError("Failed to reach NovaPay API.") from exc


def _parse_json(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _save_check_result(*, settings: NovaPaySettings, ok: bool, message: str) -> dict[str, Any]:
    now = timezone.now()
    settings.last_connection_checked_at = now
    settings.last_connection_ok = bool(ok)
    settings.last_connection_message = str(message or "").strip()
    settings.save(
        update_fields=(
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
            "updated_at",
        )
    )
    return {
        "ok": bool(ok),
        "message": settings.last_connection_message,
    }
