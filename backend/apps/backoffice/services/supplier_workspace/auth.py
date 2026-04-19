from __future__ import annotations

from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierIntegrationError

from . import serialization, workspace


def obtain_token(service, *, supplier_code: str) -> dict:
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    guard_and_validate_enabled(service, integration=integration, action_key="token_obtain")
    require_credentials(integration=integration)

    try:
        if supplier_code == "utr":
            result = service.utr_client.obtain_token(
                login=integration.login,
                password=integration.password,
                browser_fingerprint=integration.browser_fingerprint or "svom-backoffice",
            )
            service.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                access_expires_at=result.access_expires_at,
                refresh_expires_at=result.refresh_expires_at,
                refreshed=False,
            )
        elif supplier_code == "gpl":
            result = service.gpl_client.obtain_token(
                login=integration.login,
                password=integration.password,
            )
            service.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=integration.refresh_token,
                access_expires_in_seconds=result.expires_in,
                refreshed=False,
            )
        else:
            raise SupplierIntegrationError("Поставщик не поддерживается.")
        service.integration_state.mark_connection_status(integration=integration, status="connected")
    except SupplierClientError as exc:
        service.token_storage.mark_token_error(integration=integration, message=str(exc))
        service.integration_state.mark_connection_status(integration=integration, status="error")
        raise

    return workspace.get_workspace(service, supplier_code=supplier_code)


def refresh_token(service, *, supplier_code: str) -> dict:
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    guard_and_validate_enabled(service, integration=integration, action_key="token_refresh")

    if supplier_code == "utr":
        if not integration.refresh_token:
            raise SupplierIntegrationError("Отсутствует refresh token. Сначала выполните получение токена.")
        try:
            result = service.utr_client.refresh_token(
                refresh_token=integration.refresh_token,
                browser_fingerprint=integration.browser_fingerprint or "svom-backoffice",
            )
            service.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                access_expires_at=result.access_expires_at,
                refresh_expires_at=result.refresh_expires_at,
                refreshed=True,
            )
            service.integration_state.mark_connection_status(integration=integration, status="connected")
        except SupplierClientError as exc:
            service.token_storage.mark_token_error(integration=integration, message=str(exc))
            service.integration_state.mark_connection_status(integration=integration, status="error")
            raise
    elif supplier_code == "gpl":
        if not integration.access_token:
            raise SupplierIntegrationError("Отсутствует access token. Сначала выполните получение токена.")
        try:
            result = service.gpl_client.refresh_token(access_token=integration.access_token)
            service.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=integration.refresh_token,
                access_expires_in_seconds=result.expires_in,
                refreshed=True,
            )
            service.integration_state.mark_connection_status(integration=integration, status="connected")
        except SupplierClientError as exc:
            service.token_storage.mark_token_error(integration=integration, message=str(exc))
            service.integration_state.mark_connection_status(integration=integration, status="error")
            raise
    else:
        raise SupplierIntegrationError("Поставщик не поддерживается.")

    return workspace.get_workspace(service, supplier_code=supplier_code)


def check_connection(service, *, supplier_code: str) -> dict:
    integration = get_supplier_integration_by_code(source_code=supplier_code)
    guard_and_validate_enabled(service, integration=integration, action_key="connection_check")
    require_access_token(integration=integration)

    try:
        if supplier_code == "utr":
            details = service.utr_client.check_connection(access_token=integration.access_token)
        elif supplier_code == "gpl":
            details = service.gpl_client.check_connection(access_token=integration.access_token)
        else:
            raise SupplierIntegrationError("Поставщик не поддерживается.")
        service.integration_state.mark_connection_status(integration=integration, status="connected")
    except SupplierClientError:
        service.integration_state.mark_connection_status(integration=integration, status="error")
        raise

    return serialization.serialize_connection_check(
        details=details,
        workspace_payload=workspace.get_workspace(service, supplier_code=supplier_code),
    )


def guard_and_validate_enabled(service, *, integration, action_key: str) -> None:
    if not integration.is_enabled:
        raise SupplierIntegrationError("Интеграция поставщика отключена.")
    service.guard.acquire_or_raise(integration_id=str(integration.id), action_key=action_key)


def require_credentials(*, integration) -> None:
    if not integration.login or not integration.password:
        raise SupplierIntegrationError("Укажите логин и пароль поставщика.")


def require_access_token(*, integration) -> None:
    if not integration.access_token:
        raise SupplierIntegrationError("Отсутствует access token. Получите токен в блоке подключения.")
