from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("autodb", "0010_autodbtranslationsettings"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoDbRemoteSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(default="default", max_length=32, unique=True)),
                ("remote_host", models.CharField(blank=True, default="", max_length=255, verbose_name="Remote host")),
                ("remote_port", models.PositiveIntegerField(default=3306, verbose_name="Remote port")),
                ("remote_database", models.CharField(blank=True, default="", max_length=255, verbose_name="Remote database")),
                ("remote_user", models.CharField(blank=True, default="", max_length=255, verbose_name="Remote user")),
                ("remote_password", models.TextField(blank=True, default="", verbose_name="Remote password")),
                ("image_base_url", models.CharField(blank=True, default="", max_length=512, verbose_name="Image base URL")),
            ],
            options={
                "verbose_name": "Auto_DB remote settings",
                "verbose_name_plural": "Auto_DB remote settings",
                "db_table": "autodb_remote_settings",
            },
        ),
    ]
