from __future__ import annotations

from collections.abc import Iterable, Sequence

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from .capabilities import (
    BACKOFFICE_CAPABILITY_BY_CODENAME,
    BACKOFFICE_CAPABILITY_BY_CODE,
    BACKOFFICE_CAPABILITY_CODES,
    BACKOFFICE_CAPABILITIES,
)
from .roles import SYSTEM_ROLE_DEFINITIONS, SYSTEM_ROLE_PRIORITY, get_system_role_for_group_name


User = get_user_model()

STAFF_ENABLED_SYSTEM_ROLES = {"administrator", "manager", "operator"}


def _get_anchor_content_type() -> ContentType:
    return ContentType.objects.get_for_model(User)


@transaction.atomic
def ensure_system_groups_exist() -> dict[str, Group]:
    content_type = _get_anchor_content_type()
    permissions_by_code: dict[str, Permission] = {}

    for definition in BACKOFFICE_CAPABILITIES:
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=definition.permission_codename,
            defaults={"name": definition.title},
        )
        if permission.name != definition.title:
            permission.name = definition.title
            permission.save(update_fields=("name",))
        permissions_by_code[definition.code] = permission

    groups: dict[str, Group] = {}
    for role_code, definition in SYSTEM_ROLE_DEFINITIONS.items():
        group, _ = Group.objects.get_or_create(name=definition.group_name)
        group.permissions.set([permissions_by_code[code] for code in definition.capability_codes if code in permissions_by_code])
        groups[role_code] = group

    return groups


def list_backoffice_capability_payloads() -> list[dict[str, str]]:
    return [
        {
            "code": item.code,
            "title": item.title,
            "description": item.description,
        }
        for item in BACKOFFICE_CAPABILITIES
    ]


def list_system_role_payloads() -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for role_code in SYSTEM_ROLE_PRIORITY:
        definition = SYSTEM_ROLE_DEFINITIONS[role_code]
        payloads.append(
            {
                "code": definition.code,
                "title": definition.title,
                "description": definition.description,
                "group_name": definition.group_name,
                "capabilities": list(definition.capability_codes),
            }
        )
    return payloads


def get_user_system_role(user) -> str | None:
    if not getattr(user, "is_authenticated", False):
        return None

    group_names = set(user.groups.values_list("name", flat=True))
    for role_code in SYSTEM_ROLE_PRIORITY:
        definition = SYSTEM_ROLE_DEFINITIONS[role_code]
        if definition.group_name in group_names:
            return role_code
    return None


def get_user_system_role_definition(user):
    role_code = get_user_system_role(user)
    if not role_code:
        return None
    return SYSTEM_ROLE_DEFINITIONS.get(role_code)


def get_backoffice_capabilities_for_user(user) -> set[str]:
    if not getattr(user, "is_authenticated", False):
        return set()

    if getattr(user, "is_superuser", False):
        return set(BACKOFFICE_CAPABILITY_CODES)

    role = get_user_system_role(user)
    if role == "administrator":
        return set(BACKOFFICE_CAPABILITY_CODES)

    granted: set[str] = set()
    all_permissions = user.get_all_permissions()
    for value in all_permissions:
        if "." not in value:
            continue
        _app_label, codename = value.split(".", 1)
        capability = BACKOFFICE_CAPABILITY_BY_CODENAME.get(codename)
        if capability is not None:
            granted.add(capability.code)

    if role is None and getattr(user, "is_staff", False):
        # Transitional compatibility: legacy staff users without role groups
        # keep backoffice access until migrated to explicit role groups.
        return set(BACKOFFICE_CAPABILITY_CODES)

    granted = _apply_user_card_edit_aliases(role=role, granted=granted)
    return granted


def _apply_user_card_edit_aliases(*, role: str | None, granted: set[str]) -> set[str]:
    if "users.card.edit.all" in granted:
        granted.add("users.manage")
        return granted

    if role == "administrator" and "users.card.edit.administrator" in granted:
        granted.add("users.manage")
        return granted

    if role == "manager" and "users.card.edit.manager" in granted:
        granted.add("users.manage")

    return granted


def user_has_capability(user, capability_code: str) -> bool:
    normalized = str(capability_code or "").strip()
    if not normalized:
        return False
    return normalized in get_backoffice_capabilities_for_user(user)


def should_user_be_staff_by_system_role(*, user) -> bool:
    if getattr(user, "is_superuser", False):
        return True

    role_code = get_user_system_role(user)
    return role_code in STAFF_ENABLED_SYSTEM_ROLES


def sync_user_staff_flag_by_system_role(*, user) -> bool:
    desired_is_staff = should_user_be_staff_by_system_role(user=user)
    if bool(getattr(user, "is_staff", False)) == desired_is_staff:
        return False

    user.is_staff = desired_is_staff
    user.save(update_fields=("is_staff", "updated_at"))
    return True


def set_user_system_role(*, user, role_code: str | None) -> str | None:
    normalized = str(role_code or "").strip().lower() or None
    if normalized is not None and normalized not in SYSTEM_ROLE_DEFINITIONS:
        raise ValueError(f"Unknown system role: {role_code}")

    system_group_names = {definition.group_name for definition in SYSTEM_ROLE_DEFINITIONS.values()}
    user.groups.remove(*list(user.groups.filter(name__in=system_group_names)))

    if normalized is None:
        sync_user_staff_flag_by_system_role(user=user)
        return None

    ensure_system_groups_exist()
    definition = SYSTEM_ROLE_DEFINITIONS[normalized]
    group = Group.objects.get(name=definition.group_name)
    user.groups.add(group)
    sync_user_staff_flag_by_system_role(user=user)
    return normalized


def normalize_capability_codes(values: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in values:
        code = str(raw or "").strip()
        if not code or code in seen:
            continue
        if code not in BACKOFFICE_CAPABILITY_BY_CODE:
            raise ValueError(f"Unknown capability: {code}")
        seen.add(code)
        unique.append(code)
    return unique


def replace_group_capabilities(*, group: Group, capability_codes: Sequence[str]) -> None:
    ensure_system_groups_exist()
    normalized_codes = normalize_capability_codes(capability_codes)
    content_type = _get_anchor_content_type()
    permissions = {
        item.codename: item
        for item in Permission.objects.filter(
            content_type=content_type,
            codename__in=[cap.permission_codename for cap in BACKOFFICE_CAPABILITIES],
        )
    }

    selected_permissions = [
        permissions[BACKOFFICE_CAPABILITY_BY_CODE[code].permission_codename]
        for code in normalized_codes
        if BACKOFFICE_CAPABILITY_BY_CODE[code].permission_codename in permissions
    ]

    # Preserve non-backoffice permissions on a group.
    keep_permissions = list(
        group.permissions.exclude(
            content_type=content_type,
            codename__in=[cap.permission_codename for cap in BACKOFFICE_CAPABILITIES],
        )
    )
    group.permissions.set([*keep_permissions, *selected_permissions])


def get_group_capability_codes(group: Group) -> list[str]:
    codenames = set(group.permissions.values_list("codename", flat=True))
    codes: list[str] = []
    for capability in BACKOFFICE_CAPABILITIES:
        if capability.permission_codename in codenames:
            codes.append(capability.code)
    return codes


def is_system_role_group(group: Group) -> bool:
    return get_system_role_for_group_name(group.name) is not None
