from __future__ import annotations

from . import actions, auth, imports, status, workspace
from .types import WorkspaceServiceDependencies, build_default_dependencies


class SupplierWorkspaceService:
    def __init__(self, *, dependencies: WorkspaceServiceDependencies | None = None):
        deps = dependencies or build_default_dependencies()
        self.guard = deps.guard
        self.token_storage = deps.token_storage
        self.integration_state = deps.integration_state
        self.utr_client = deps.utr_client
        self.utr_brand_import = deps.utr_brand_import
        self.gpl_client = deps.gpl_client
        self.import_orchestration = deps.import_orchestration

    def list_suppliers(self) -> list[dict]:
        return workspace.list_suppliers(self)

    def get_workspace(self, *, supplier_code: str) -> dict:
        return workspace.get_workspace(self, supplier_code=supplier_code)

    def update_settings(
        self,
        *,
        supplier_code: str,
        login: str | None = None,
        password: str | None = None,
        browser_fingerprint: str | None = None,
        is_enabled: bool | None = None,
    ) -> dict:
        return actions.update_settings(
            self,
            supplier_code=supplier_code,
            login=login,
            password=password,
            browser_fingerprint=browser_fingerprint,
            is_enabled=is_enabled,
        )

    def obtain_token(self, *, supplier_code: str) -> dict:
        return auth.obtain_token(self, supplier_code=supplier_code)

    def refresh_token(self, *, supplier_code: str) -> dict:
        return auth.refresh_token(self, supplier_code=supplier_code)

    def check_connection(self, *, supplier_code: str) -> dict:
        return auth.check_connection(self, supplier_code=supplier_code)

    def run_import(self, *, supplier_code: str, dry_run: bool = False, dispatch_async: bool = False) -> dict:
        return imports.run_import(
            self,
            supplier_code=supplier_code,
            dry_run=dry_run,
            dispatch_async=dispatch_async,
        )

    def sync_prices(self, *, supplier_code: str, dispatch_async: bool = False) -> dict:
        return imports.sync_prices(self, supplier_code=supplier_code, dispatch_async=dispatch_async)

    def import_utr_brands(self) -> dict:
        return imports.import_utr_brands(self)

    def publish_mapped_products(
        self,
        *,
        supplier_code: str,
        run_id: str | None = None,
        include_needs_review: bool = False,
        dry_run: bool = False,
        reprice_after_publish: bool = True,
    ) -> dict:
        return imports.publish_mapped_products(
            self,
            supplier_code=supplier_code,
            run_id=run_id,
            include_needs_review=include_needs_review,
            dry_run=dry_run,
            reprice_after_publish=reprice_after_publish,
        )

    def _fetch_utr_brand_rows(self, *, integration, supplier_code: str) -> tuple[list[dict], str]:
        return imports.fetch_utr_brand_rows(self, integration=integration, supplier_code=supplier_code)

    def get_cooldown(self, *, supplier_code: str) -> dict:
        return workspace.get_cooldown(self, supplier_code=supplier_code)

    # Back-compat private wrappers
    def _guard_and_validate_enabled(self, *, integration, action_key: str) -> None:
        return auth.guard_and_validate_enabled(self, integration=integration, action_key=action_key)

    def _require_credentials(self, *, integration) -> None:
        return auth.require_credentials(integration=integration)

    def _require_access_token(self, *, integration) -> None:
        return auth.require_access_token(integration=integration)

    def _resolve_connection_status(self, *, integration) -> str:
        return status.resolve_connection_status(integration=integration)
