from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackofficeCapabilityDefinition:
    code: str
    permission_codename: str
    title: str
    description: str


BACKOFFICE_CAPABILITIES: tuple[BackofficeCapabilityDefinition, ...] = (
    BackofficeCapabilityDefinition(
        code="backoffice.access",
        permission_codename="bo_cap_backoffice_access",
        title="Backoffice access",
        description="Allows entering backoffice.",
    ),
    BackofficeCapabilityDefinition(
        code="users.view",
        permission_codename="bo_cap_users_view",
        title="Users view",
        description="Read users in backoffice.",
    ),
    BackofficeCapabilityDefinition(
        code="users.manage",
        permission_codename="bo_cap_users_manage",
        title="Users manage",
        description="Create/update/deactivate users in backoffice.",
    ),
    BackofficeCapabilityDefinition(
        code="users.card.edit.administrator",
        permission_codename="bo_cap_users_card_edit_administrator",
        title="Users card edit (administrator)",
        description="Allow administrators to edit user cards.",
    ),
    BackofficeCapabilityDefinition(
        code="users.card.edit.manager",
        permission_codename="bo_cap_users_card_edit_manager",
        title="Users card edit (manager)",
        description="Allow managers to edit user cards.",
    ),
    BackofficeCapabilityDefinition(
        code="users.card.edit.all",
        permission_codename="bo_cap_users_card_edit_all",
        title="Users card edit (all roles)",
        description="Allow any backoffice role to edit user cards.",
    ),
    BackofficeCapabilityDefinition(
        code="groups.view",
        permission_codename="bo_cap_groups_view",
        title="Groups view",
        description="Read groups and role permissions.",
    ),
    BackofficeCapabilityDefinition(
        code="groups.manage",
        permission_codename="bo_cap_groups_manage",
        title="Groups manage",
        description="Create/update groups and assigned capabilities.",
    ),
    BackofficeCapabilityDefinition(
        code="catalog.view",
        permission_codename="bo_cap_catalog_view",
        title="Catalog view",
        description="Read catalog entities in backoffice.",
    ),
    BackofficeCapabilityDefinition(
        code="catalog.manage",
        permission_codename="bo_cap_catalog_manage",
        title="Catalog manage",
        description="Manage catalog entities in backoffice.",
    ),
    BackofficeCapabilityDefinition(
        code="orders.view",
        permission_codename="bo_cap_orders_view",
        title="Orders view",
        description="Read orders and order details.",
    ),
    BackofficeCapabilityDefinition(
        code="orders.manage",
        permission_codename="bo_cap_orders_manage",
        title="Orders manage",
        description="Perform order operations in backoffice.",
    ),
    BackofficeCapabilityDefinition(
        code="customers.support",
        permission_codename="bo_cap_customers_support",
        title="Customers support",
        description="Customer service actions in order flow.",
    ),
    BackofficeCapabilityDefinition(
        code="pricing.view",
        permission_codename="bo_cap_pricing_view",
        title="Pricing view",
        description="Read pricing dashboards and data.",
    ),
    BackofficeCapabilityDefinition(
        code="pricing.manage",
        permission_codename="bo_cap_pricing_manage",
        title="Pricing manage",
        description="Manage pricing settings and recalculation.",
    ),
    BackofficeCapabilityDefinition(
        code="suppliers.view",
        permission_codename="bo_cap_suppliers_view",
        title="Suppliers view",
        description="Read suppliers and supplier data.",
    ),
    BackofficeCapabilityDefinition(
        code="suppliers.manage",
        permission_codename="bo_cap_suppliers_manage",
        title="Suppliers manage",
        description="Manage suppliers and supplier operations.",
    ),
    BackofficeCapabilityDefinition(
        code="imports.view",
        permission_codename="bo_cap_imports_view",
        title="Imports view",
        description="Read import runs, quality and errors.",
    ),
    BackofficeCapabilityDefinition(
        code="imports.manage",
        permission_codename="bo_cap_imports_manage",
        title="Imports manage",
        description="Run import and import maintenance actions.",
    ),
    BackofficeCapabilityDefinition(
        code="settings.manage",
        permission_codename="bo_cap_settings_manage",
        title="Settings manage",
        description="Manage operational/system settings in backoffice.",
    ),
    BackofficeCapabilityDefinition(
        code="procurement.manage",
        permission_codename="bo_cap_procurement_manage",
        title="Procurement manage",
        description="Work with procurement recommendations and supplier overrides.",
    ),
)


BACKOFFICE_CAPABILITY_BY_CODE = {item.code: item for item in BACKOFFICE_CAPABILITIES}
BACKOFFICE_CAPABILITY_BY_CODENAME = {item.permission_codename: item for item in BACKOFFICE_CAPABILITIES}
BACKOFFICE_CAPABILITY_CODES = tuple(item.code for item in BACKOFFICE_CAPABILITIES)


def get_backoffice_capability_definition(code: str) -> BackofficeCapabilityDefinition | None:
    return BACKOFFICE_CAPABILITY_BY_CODE.get(str(code or "").strip())


def is_backoffice_capability_code(value: str) -> bool:
    return str(value or "").strip() in BACKOFFICE_CAPABILITY_BY_CODE
