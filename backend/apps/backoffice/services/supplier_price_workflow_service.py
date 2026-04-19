from __future__ import annotations

from apps.supplier_imports.services.integrations.gpl_client import GplClient
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.integrations.utr_client import UtrClient

from .supplier_price_workflow.service import SupplierPriceWorkflowService as _SupplierPriceWorkflowService


class SupplierPriceWorkflowService(_SupplierPriceWorkflowService):
    def __init__(self):
        super().__init__(
            guard=SupplierRateLimitGuardService(),
            utr_client=UtrClient(),
            gpl_client=GplClient(),
        )


__all__ = ["SupplierPriceWorkflowService", "UtrClient", "GplClient", "SupplierRateLimitGuardService"]
