from __future__ import annotations

from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierCooldownError, SupplierIntegrationError
from apps.supplier_imports.services.integrations.gpl_client import GplClient
from apps.supplier_imports.services.integrations.import_orchestration_service import SupplierImportOrchestrationService
from apps.supplier_imports.services.integrations.integration_state_service import SupplierIntegrationStateService
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.integrations.token_storage_service import SupplierTokenStorageService
from apps.supplier_imports.services.integrations.utr_brand_import_service import UtrBrandImportService
from apps.supplier_imports.services.integrations.utr_client import UtrClient
from apps.supplier_imports.services.mapped_offer_publish_service import SupplierMappedOffersPublishService

from .supplier_workspace.service import SupplierWorkspaceService as _SupplierWorkspaceService
from .supplier_workspace.types import WorkspaceServiceDependencies


class SupplierWorkspaceService(_SupplierWorkspaceService):
    def __init__(self):
        super().__init__(
            dependencies=WorkspaceServiceDependencies(
                guard=SupplierRateLimitGuardService(),
                token_storage=SupplierTokenStorageService(),
                integration_state=SupplierIntegrationStateService(),
                utr_client=UtrClient(),
                utr_brand_import=UtrBrandImportService(),
                gpl_client=GplClient(),
                import_orchestration=SupplierImportOrchestrationService(),
            )
        )


__all__ = [
    "SupplierWorkspaceService",
    "SupplierClientError",
    "SupplierCooldownError",
    "SupplierIntegrationError",
    "UtrClient",
    "GplClient",
    "SupplierRateLimitGuardService",
    "SupplierTokenStorageService",
    "SupplierIntegrationStateService",
    "UtrBrandImportService",
    "SupplierImportOrchestrationService",
    "SupplierMappedOffersPublishService",
]
