from __future__ import annotations

from dataclasses import dataclass

from apps.supplier_imports.services.integrations.gpl_client import GplClient
from apps.supplier_imports.services.integrations.import_orchestration_service import SupplierImportOrchestrationService
from apps.supplier_imports.services.integrations.integration_state_service import SupplierIntegrationStateService
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.integrations.token_storage_service import SupplierTokenStorageService
from apps.supplier_imports.services.integrations.utr_brand_import_service import UtrBrandImportService
from apps.supplier_imports.services.integrations.utr_client import UtrClient


@dataclass(frozen=True)
class WorkspaceServiceDependencies:
    guard: SupplierRateLimitGuardService
    token_storage: SupplierTokenStorageService
    integration_state: SupplierIntegrationStateService
    utr_client: UtrClient
    utr_brand_import: UtrBrandImportService
    gpl_client: GplClient
    import_orchestration: SupplierImportOrchestrationService


def build_default_dependencies() -> WorkspaceServiceDependencies:
    return WorkspaceServiceDependencies(
        guard=SupplierRateLimitGuardService(),
        token_storage=SupplierTokenStorageService(),
        integration_state=SupplierIntegrationStateService(),
        utr_client=UtrClient(),
        utr_brand_import=UtrBrandImportService(),
        gpl_client=GplClient(),
        import_orchestration=SupplierImportOrchestrationService(),
    )
