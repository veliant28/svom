from django.db import migrations


CAPABILITY = (
    "loyalty.issue",
    "bo_cap_loyalty_issue",
    "Loyalty issue",
)


def add_loyalty_issue_capability(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="user")

    _code, codename, title = CAPABILITY
    permission, _created = Permission.objects.get_or_create(
        content_type=content_type,
        codename=codename,
        defaults={"name": title},
    )
    if permission.name != title:
        permission.name = title
        permission.save(update_fields=("name",))

    for group_name in ("Backoffice Role: administrator", "Backoffice Role: manager"):
        group = Group.objects.filter(name=group_name).first()
        if group is not None:
            group.permissions.add(permission)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_remove_backoffice_access_from_user_role"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(add_loyalty_issue_capability, noop_reverse),
    ]
