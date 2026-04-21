from __future__ import annotations

from dataclasses import dataclass

from .capabilities import BACKOFFICE_CAPABILITY_CODES


@dataclass(frozen=True)
class BackofficeSystemRoleDefinition:
    code: str
    group_name: str
    title: str
    description: str
    capability_codes: tuple[str, ...]


SYSTEM_ROLE_ADMINISTRATOR = "administrator"
SYSTEM_ROLE_MANAGER = "manager"
SYSTEM_ROLE_USER = "user"
SYSTEM_ROLE_OPERATOR = "operator"

SYSTEM_ROLE_CODES = (
    SYSTEM_ROLE_ADMINISTRATOR,
    SYSTEM_ROLE_MANAGER,
    SYSTEM_ROLE_USER,
    SYSTEM_ROLE_OPERATOR,
)

SYSTEM_ROLE_PRIORITY = (
    SYSTEM_ROLE_ADMINISTRATOR,
    SYSTEM_ROLE_MANAGER,
    SYSTEM_ROLE_OPERATOR,
    SYSTEM_ROLE_USER,
)

SYSTEM_ROLE_DEFINITIONS: dict[str, BackofficeSystemRoleDefinition] = {
    SYSTEM_ROLE_ADMINISTRATOR: BackofficeSystemRoleDefinition(
        code=SYSTEM_ROLE_ADMINISTRATOR,
        group_name="Backoffice Role: administrator",
        title="Administrator",
        description="Full backoffice and RBAC administration access.",
        capability_codes=tuple(BACKOFFICE_CAPABILITY_CODES),
    ),
    SYSTEM_ROLE_MANAGER: BackofficeSystemRoleDefinition(
        code=SYSTEM_ROLE_MANAGER,
        group_name="Backoffice Role: manager",
        title="Manager",
        description="Operational management without full system administration.",
        capability_codes=(
            "backoffice.access",
            "users.view",
            "groups.view",
            "catalog.view",
            "catalog.manage",
            "orders.view",
            "orders.manage",
            "customers.support",
            "pricing.view",
            "suppliers.view",
            "imports.view",
            "procurement.manage",
        ),
    ),
    SYSTEM_ROLE_OPERATOR: BackofficeSystemRoleDefinition(
        code=SYSTEM_ROLE_OPERATOR,
        group_name="Backoffice Role: operator",
        title="Operator",
        description="Customer service role with restricted operational access.",
        capability_codes=(
            "backoffice.access",
            "users.view",
            "orders.view",
            "orders.manage",
            "customers.support",
        ),
    ),
    SYSTEM_ROLE_USER: BackofficeSystemRoleDefinition(
        code=SYSTEM_ROLE_USER,
        group_name="Backoffice Role: user",
        title="User",
        description="Minimal backoffice access with explicitly granted capabilities.",
        capability_codes=("backoffice.access",),
    ),
}


def get_system_role_definition(role_code: str) -> BackofficeSystemRoleDefinition | None:
    normalized = str(role_code or "").strip().lower()
    return SYSTEM_ROLE_DEFINITIONS.get(normalized)


def get_system_role_group_name(role_code: str) -> str:
    definition = get_system_role_definition(role_code)
    if definition is None:
        raise KeyError(f"Unknown system role: {role_code}")
    return definition.group_name


def get_system_role_for_group_name(group_name: str) -> str | None:
    normalized = str(group_name or "").strip()
    if not normalized:
        return None
    for role_code, definition in SYSTEM_ROLE_DEFINITIONS.items():
        if definition.group_name == normalized:
            return role_code
    return None
