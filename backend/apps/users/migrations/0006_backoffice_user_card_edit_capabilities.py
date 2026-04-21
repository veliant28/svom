from django.db import migrations


NEW_CAPABILITIES = (
    (
        "users.card.edit.administrator",
        "bo_cap_users_card_edit_administrator",
        "Users card edit (administrator)",
    ),
    (
        "users.card.edit.manager",
        "bo_cap_users_card_edit_manager",
        "Users card edit (manager)",
    ),
    (
        "users.card.edit.all",
        "bo_cap_users_card_edit_all",
        "Users card edit (all roles)",
    ),
)


def add_user_card_edit_capabilities(apps, schema_editor):
    User = apps.get_model("users", "User")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    content_type = ContentType.objects.get(app_label=User._meta.app_label, model=User._meta.model_name)

    permissions_by_code = {}
    for code, codename, title in NEW_CAPABILITIES:
        permission, _created = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": title},
        )
        if permission.name != title:
            permission.name = title
            permission.save(update_fields=("name",))
        permissions_by_code[code] = permission

    manager_group = Group.objects.filter(name="Backoffice Role: manager").first()
    if manager_group is not None:
        manager_permission = permissions_by_code.get("users.card.edit.manager")
        if manager_permission is not None:
            manager_group.permissions.add(manager_permission)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_bootstrap_backoffice_rbac"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(add_user_card_edit_capabilities, noop_reverse),
    ]

