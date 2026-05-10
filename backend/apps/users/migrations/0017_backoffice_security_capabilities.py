from django.db import migrations


CAPABILITIES = (
    ("security.view", "bo_cap_security_view", "Security view"),
    ("security.manage", "bo_cap_security_manage", "Security manage"),
    ("security.audit", "bo_cap_security_audit", "Security audit"),
    ("security.respond", "bo_cap_security_respond", "Security respond"),
)


def add_security_capabilities(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="user")
    permissions = []
    for _code, codename, title in CAPABILITIES:
        permission, _created = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": title},
        )
        if permission.name != title:
            permission.name = title
            permission.save(update_fields=("name",))
        permissions.append(permission)

    group = Group.objects.filter(name="Backoffice Role: administrator").first()
    if group is not None:
        for permission in permissions:
            group.permissions.add(permission)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0016_garagevehicle_autodb_details"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(add_security_capabilities, noop_reverse),
    ]
