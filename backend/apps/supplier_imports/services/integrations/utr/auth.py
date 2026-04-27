from __future__ import annotations

import logging
import time
from uuid import uuid4
from dataclasses import dataclass

from django.core.cache import cache
from django.utils import timezone

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.selectors import get_supplier_integration_by_code

from apps.supplier_imports.services.integrations.client_utils import parse_datetime_maybe

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupplierTokenResult:
    access_token: str
    refresh_token: str
    access_expires_at: object | None
    refresh_expires_at: object | None = None


def obtain_token(client, *, login: str, password: str, browser_fingerprint: str) -> SupplierTokenResult:
    response = client._safe_json_request(
        method="POST",
        url=f"{client.base_url}/api/login_check",
        payload={
            "email": login,
            "password": password,
            "browser_fingerprint": browser_fingerprint,
        },
        force_refresh=True,
        request_reason="auth_obtain_token",
    )
    payload = response.payload if isinstance(response.payload, dict) else {}
    token = str(payload.get("token", "")).strip()
    refresh_token = str(payload.get("refresh_token", "")).strip()
    if not token:
        raise SupplierClientError("UTR не вернул access token.")
    if not refresh_token:
        raise SupplierClientError("UTR не вернул refresh token.")
    return SupplierTokenResult(
        access_token=token,
        refresh_token=refresh_token,
        access_expires_at=parse_datetime_maybe(str(payload.get("expires_at", ""))),
        refresh_expires_at=None,
    )


def refresh_token(client, *, refresh_token: str, browser_fingerprint: str) -> SupplierTokenResult:
    response = client._safe_json_request(
        method="POST",
        url=f"{client.base_url}/api/token/refresh",
        payload={
            "refresh_token": refresh_token,
            "browser_fingerprint": browser_fingerprint,
        },
        force_refresh=True,
        request_reason="auth_refresh_token",
    )
    payload = response.payload if isinstance(response.payload, dict) else {}
    token = str(payload.get("token", "")).strip()
    next_refresh_token = str(payload.get("refresh_token", "")).strip()
    if not token:
        raise SupplierClientError("UTR не вернул access token при обновлении.")
    if not next_refresh_token:
        raise SupplierClientError("UTR не вернул refresh token при обновлении.")
    return SupplierTokenResult(
        access_token=token,
        refresh_token=next_refresh_token,
        access_expires_at=parse_datetime_maybe(str(payload.get("expires_at", ""))),
        refresh_expires_at=None,
    )


def recover_access_token_for_utr(client) -> tuple[str, str]:
    owner_token = uuid4().hex
    lock_key = "utr:auth_recovery_lock"
    for _attempt in range(120):
        try:
            if cache.add(lock_key, owner_token, timeout=90):
                break
        except Exception:
            break
        time.sleep(0.5)
    else:
        logger.warning("[UTR] token recovery lock wait timed out.")
        return "", ""

    try:
        return _recover_access_token_for_utr_unlocked(client)
    finally:
        try:
            if cache.get(lock_key) == owner_token:
                cache.delete(lock_key)
        except Exception:
            pass


def _recover_access_token_for_utr_unlocked(client) -> tuple[str, str]:
    integration = get_supplier_integration_by_code(source_code="utr")
    current_token = str(integration.access_token or "").strip()
    if current_token and (
        integration.access_token_expires_at is None
        or integration.access_token_expires_at > timezone.now()
    ):
        return current_token, "existing"

    browser_fingerprint = integration.browser_fingerprint or "svom-backoffice"

    if integration.refresh_token:
        try:
            result = client.refresh_token(
                refresh_token=integration.refresh_token,
                browser_fingerprint=browser_fingerprint,
            )
            client.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                access_expires_at=result.access_expires_at,
                refresh_expires_at=result.refresh_expires_at,
                refreshed=True,
            )
            client._increment_metric("auth_refresh_total")
            logger.info("[UTR] token refresh succeeded for batch-retry.")
            return result.access_token, "refresh"
        except SupplierClientError as exc:
            logger.warning("[UTR] token refresh failed during batch-retry: %s", exc)

    login = str(integration.login or "").strip()
    password = str(integration.password or "").strip()
    if login and password:
        try:
            result = client.obtain_token(
                login=login,
                password=password,
                browser_fingerprint=browser_fingerprint,
            )
            client.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                access_expires_at=result.access_expires_at,
                refresh_expires_at=result.refresh_expires_at,
                refreshed=False,
            )
            client._increment_metric("auth_relogin_total")
            logger.info("[UTR] re-login succeeded for batch-retry.")
            return result.access_token, "relogin"
        except SupplierClientError as exc:
            logger.warning("[UTR] re-login failed during batch-retry: %s", exc)

    return "", ""
