from django.db import migrations


ROLE_GROUP_NAME = "Backoffice Role: user"
ACCESS_PERMISSION_CODENAME = "bo_cap_backoffice_access"


def remove_access_from_user_role(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group = Group.objects.filter(name=ROLE_GROUP_NAME).first()
    if group is None:
        return

    permission = Permission.objects.filter(codename=ACCESS_PERMISSION_CODENAME).first()
    if permission is None:
        return

    group.permissions.remove(permission)


def restore_access_to_user_role(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group = Group.objects.filter(name=ROLE_GROUP_NAME).first()
    if group is None:
        return

    permission = Permission.objects.filter(codename=ACCESS_PERMISSION_CODENAME).first()
    if permission is None:
        return

    group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0007_alter_user_managers_remove_user_username"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(remove_access_from_user_role, restore_access_to_user_role),
    ]

