from django.db import migrations


def move_remote_settings_table(apps, schema_editor):
    alias = schema_editor.connection.alias
    model = apps.get_model("autodb", "AutoDbRemoteSettings")
    table = model._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing = set(schema_editor.connection.introspection.table_names(cursor))

    if alias == "default":
        if table not in existing:
            schema_editor.create_model(model)
        return

    if alias == "auto_db_pro":
        if table in existing:
            schema_editor.delete_model(model)
        return


class Migration(migrations.Migration):
    dependencies = [
        ("autodb", "0011_autodbremotesettings"),
    ]

    operations = [
        migrations.RunPython(move_remote_settings_table, migrations.RunPython.noop),
    ]
