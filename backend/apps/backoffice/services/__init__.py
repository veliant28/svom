from importlib import import_module

__all__ = [
    "ImportActionsService",
    "OrderOperationsService",
    "OrderActionResult",
    "OrderSupplierService",
    "PricingControlService",
    "ProductOperationsService",
    "ProductBulkCategoryMoveResult",
    "ProcurementService",
    "SupplierPriceWorkflowService",
    "SupplierWorkspaceService",
]

_EXPORTS = {
    "ImportActionsService": ("apps.backoffice.services.import_actions_service", "ImportActionsService"),
    "OrderOperationsService": ("apps.backoffice.services.order_operations_service", "OrderOperationsService"),
    "OrderActionResult": ("apps.backoffice.services.order_operations_service", "OrderActionResult"),
    "OrderSupplierService": ("apps.backoffice.services.order_supplier_service", "OrderSupplierService"),
    "PricingControlService": ("apps.backoffice.services.pricing_control_service", "PricingControlService"),
    "ProductOperationsService": ("apps.backoffice.services.product_operations_service", "ProductOperationsService"),
    "ProductBulkCategoryMoveResult": (
        "apps.backoffice.services.product_operations_service",
        "ProductBulkCategoryMoveResult",
    ),
    "ProcurementService": ("apps.backoffice.services.procurement_service", "ProcurementService"),
    "SupplierPriceWorkflowService": (
        "apps.backoffice.services.supplier_price_workflow_service",
        "SupplierPriceWorkflowService",
    ),
    "SupplierWorkspaceService": ("apps.backoffice.services.supplier_workspace_service", "SupplierWorkspaceService"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_path, attr_name = target
    module = import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
