from django.db import migrations


CAPABILITIES = (
    ("backoffice.access", "bo_cap_backoffice_access", "Backoffice access"),
    ("users.view", "bo_cap_users_view", "Users view"),
    ("users.manage", "bo_cap_users_manage", "Users manage"),
    ("groups.view", "bo_cap_groups_view", "Groups view"),
    ("groups.manage", "bo_cap_groups_manage", "Groups manage"),
    ("catalog.view", "bo_cap_catalog_view", "Catalog view"),
    ("catalog.manage", "bo_cap_catalog_manage", "Catalog manage"),
    ("orders.view", "bo_cap_orders_view", "Orders view"),
    ("orders.manage", "bo_cap_orders_manage", "Orders manage"),
    ("customers.support", "bo_cap_customers_support", "Customers support"),
    ("pricing.view", "bo_cap_pricing_view", "Pricing view"),
    ("pricing.manage", "bo_cap_pricing_manage", "Pricing manage"),
    ("suppliers.view", "bo_cap_suppliers_view", "Suppliers view"),
    ("suppliers.manage", "bo_cap_suppliers_manage", "Suppliers manage"),
    ("imports.view", "bo_cap_imports_view", "Imports view"),
    ("imports.manage", "bo_cap_imports_manage", "Imports manage"),
    ("settings.manage", "bo_cap_settings_manage", "Settings manage"),
    ("procurement.manage", "bo_cap_procurement_manage", "Procurement manage"),
)

ROLE_CAPABILITIES = {
    "administrator": [code for code, _codename, _name in CAPABILITIES],
    "manager": [
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
    ],
    "operator": [
        "backoffice.access",
        "users.view",
        "orders.view",
        "orders.manage",
        "customers.support",
    ],
    "user": ["backoffice.access"],
}


def bootstrap_backoffice_rbac(apps, schema_editor):
    User = apps.get_model("users", "User")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    content_type = ContentType.objects.get(app_label=User._meta.app_label, model=User._meta.model_name)

    permissions_by_code = {}
    for code, codename, title in CAPABILITIES:
        permission, _created = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": title},
        )
        if permission.name != title:
            permission.name = title
            permission.save(update_fields=("name",))
        permissions_by_code[code] = permission

    for role_code, capability_codes in ROLE_CAPABILITIES.items():
        group, _created = Group.objects.get_or_create(name=f"Backoffice Role: {role_code}")
        group.permissions.set([permissions_by_code[code] for code in capability_codes if code in permissions_by_code])


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_user_middle_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(bootstrap_backoffice_rbac, noop_reverse),
    ]
