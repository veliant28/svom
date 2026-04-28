from django.db import migrations


CAPABILITY = (
    "checkout.methods.manage",
    "bo_cap_checkout_methods_manage",
    "Checkout methods manage",
)


def add_checkout_methods_capability(apps, schema_editor):
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

    admin_group = Group.objects.filter(name="Backoffice Role: administrator").first()
    if admin_group is not None:
        admin_group.permissions.add(permission)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0013_backoffice_email_settings_capability"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(add_checkout_methods_capability, noop_reverse),
    ]
