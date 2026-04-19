from __future__ import annotations

from apps.supplier_imports.selectors import get_supplier_integration_by_code

from . import workspace


def update_settings(
    service,
    *,
    supplier_code: str,
    login: str | None = None,
    password: str | None = None,
    browser_fingerprint: str | None = None,
    is_enabled: bool | None = None,
) -> dict:
    integration = get_supplier_integration_by_code(source_code=supplier_code)

    if login is not None or password is not None or browser_fingerprint is not None:
        service.token_storage.update_credentials(
            integration=integration,
            login=login if login is not None else integration.login,
            password=password if password is not None else integration.password,
            browser_fingerprint=browser_fingerprint if browser_fingerprint is not None else integration.browser_fingerprint,
        )

    if is_enabled is not None:
        integration.is_enabled = bool(is_enabled)
        integration.save(update_fields=("is_enabled", "updated_at"))

    return workspace.get_workspace(service, supplier_code=supplier_code)
