from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("autodb", "0009_autodbremotequotastate_live_points"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoDbTranslationSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(default="default", max_length=32, unique=True)),
                (
                    "provider",
                    models.CharField(
                        choices=[("libretranslate", "libretranslate"), ("google", "google")],
                        default="libretranslate",
                        max_length=32,
                        verbose_name="Translation provider",
                    ),
                ),
                (
                    "google_api_key",
                    models.TextField(blank=True, default="", verbose_name="Google Translate API key"),
                ),
            ],
            options={
                "verbose_name": "Auto_DB translation settings",
                "verbose_name_plural": "Auto_DB translation settings",
                "db_table": "autodb_translation_settings",
            },
        ),
    ]
