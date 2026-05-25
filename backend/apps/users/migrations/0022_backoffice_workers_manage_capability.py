from django.db import migrations


CAPABILITY = ("workers.manage", "bo_cap_workers_manage", "Workers manage")


def add_workers_manage_capability(apps, schema_editor):
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

    group = Group.objects.filter(name="Backoffice Role: administrator").first()
    if group is not None:
        group.permissions.add(permission)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0021_returns_role_defaults"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(add_workers_manage_capability, noop_reverse),
    ]
