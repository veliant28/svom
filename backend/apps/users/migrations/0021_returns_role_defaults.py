from django.db import migrations


def apply_returns_role_defaults(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    permissions_by_codename = {
        permission.codename: permission
        for permission in Permission.objects.filter(
            codename__in=(
                "bo_cap_returns_view",
                "bo_cap_returns_manage",
                "bo_cap_returns_approve",
                "bo_cap_returns_reject",
                "bo_cap_returns_refund",
            )
        )
    }

    admin_group = Group.objects.filter(name="Backoffice Role: administrator").first()
    manager_group = Group.objects.filter(name="Backoffice Role: manager").first()
    operator_group = Group.objects.filter(name="Backoffice Role: operator").first()

    if admin_group is not None:
        for codename in (
            "bo_cap_returns_view",
            "bo_cap_returns_manage",
            "bo_cap_returns_approve",
            "bo_cap_returns_reject",
            "bo_cap_returns_refund",
        ):
            permission = permissions_by_codename.get(codename)
            if permission is not None:
                admin_group.permissions.add(permission)

    if manager_group is not None:
        for codename in (
            "bo_cap_returns_view",
            "bo_cap_returns_manage",
            "bo_cap_returns_approve",
            "bo_cap_returns_reject",
            "bo_cap_returns_refund",
        ):
            permission = permissions_by_codename.get(codename)
            if permission is not None:
                manager_group.permissions.add(permission)

    if operator_group is not None:
        for codename in (
            "bo_cap_returns_view",
            "bo_cap_returns_manage",
            "bo_cap_returns_approve",
        ):
            permission = permissions_by_codename.get(codename)
            if permission is not None:
                operator_group.permissions.add(permission)

        for codename in (
            "bo_cap_returns_reject",
            "bo_cap_returns_refund",
        ):
            permission = permissions_by_codename.get(codename)
            if permission is not None:
                operator_group.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0020_remove_legacy_vehicle_fk_fields"),
    ]

    operations = [
        migrations.RunPython(apply_returns_role_defaults, migrations.RunPython.noop),
    ]
