import os

from django.db import migrations


def seed_from_env(apps, schema_editor):
    if schema_editor.connection.alias != "default":
        return

    model = apps.get_model("autodb", "AutoDbRemoteSettings")
    settings, _ = model.objects.get_or_create(code="default")

    host = str(os.getenv("AUTODB_PRO_REMOTE_HOST", "") or "").strip()
    port_raw = str(os.getenv("AUTODB_PRO_REMOTE_PORT", "") or "").strip()
    database = str(os.getenv("AUTODB_PRO_REMOTE_DATABASE", "") or "").strip()
    user = str(os.getenv("AUTODB_PRO_REMOTE_USER", "") or "").strip()
    password = str(os.getenv("AUTODB_PRO_REMOTE_PASSWORD", "") or "")
    image_base_url = str(
        os.getenv("AUTODB_PRO_IMAGE_BASE_URL", "") or os.getenv("AUTODB_IMAGE_BASE_URL", "") or ""
    ).strip()

    updated_fields: list[str] = []

    if not str(settings.remote_host or "").strip() and host:
        settings.remote_host = host
        updated_fields.append("remote_host")

    if not int(settings.remote_port or 0) and port_raw:
        try:
            port = int(port_raw)
        except ValueError:
            port = 0
        if 1 <= port <= 65535:
            settings.remote_port = port
            updated_fields.append("remote_port")

    if not str(settings.remote_database or "").strip() and database:
        settings.remote_database = database
        updated_fields.append("remote_database")

    if not str(settings.remote_user or "").strip() and user:
        settings.remote_user = user
        updated_fields.append("remote_user")

    if not str(settings.remote_password or "").strip() and password:
        settings.remote_password = password
        updated_fields.append("remote_password")

    if not str(settings.image_base_url or "").strip() and image_base_url:
        settings.image_base_url = image_base_url
        updated_fields.append("image_base_url")

    if updated_fields:
        settings.save(update_fields=tuple(dict.fromkeys([*updated_fields, "updated_at"])))


class Migration(migrations.Migration):
    dependencies = [
        ("autodb", "0012_move_remotesettings_to_default"),
    ]

    operations = [
        migrations.RunPython(seed_from_env, migrations.RunPython.noop),
    ]
