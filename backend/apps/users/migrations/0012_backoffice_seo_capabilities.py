from django.db import migrations


CAPABILITIES = (
    ("seo.view", "bo_cap_seo_view", "SEO view"),
    ("seo.manage", "bo_cap_seo_manage", "SEO manage"),
)


def add_seo_capabilities(apps, schema_editor):
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

    for group_name in ("Backoffice Role: administrator", "Backoffice Role: manager"):
        group = Group.objects.filter(name=group_name).first()
        if group is not None:
            for permission in permissions:
                group.permissions.add(permission)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_backoffice_promo_banners_capability"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(add_seo_capabilities, noop_reverse),
    ]
