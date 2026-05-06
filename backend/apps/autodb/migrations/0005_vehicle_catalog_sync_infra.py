# Generated manually for Auto_DB_Pro vehicle catalog sync infrastructure.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("autodb", "0004_autodbengine_autodbsupplierbrand_autodbsyncstate_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoDbCountry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("autodb_country_id", models.BigIntegerField(db_index=True, unique=True, verbose_name="Auto-DB country ID")),
                ("name", models.CharField(blank=True, default="", max_length=255, verbose_name="Название")),
                ("iso_code", models.CharField(blank=True, default="", max_length=16, verbose_name="ISO код")),
                ("source_payload", models.JSONField(blank=True, default=dict, verbose_name="Source payload")),
                ("source_updated_at", models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике")),
                ("imported_at", models.DateTimeField(blank=True, null=True, verbose_name="Импортировано")),
            ],
            options={
                "verbose_name": "Страна Auto_DB_Pro",
                "verbose_name_plural": "Страны Auto_DB_Pro",
                "db_table": "autodb_pro_countries",
            },
        ),
        migrations.CreateModel(
            name="AutoDbCountryGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "autodb_country_group_id",
                    models.BigIntegerField(db_index=True, unique=True, verbose_name="Auto-DB country group ID"),
                ),
                ("name", models.CharField(blank=True, default="", max_length=255, verbose_name="Название")),
                ("source_payload", models.JSONField(blank=True, default=dict, verbose_name="Source payload")),
                ("source_updated_at", models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике")),
                ("imported_at", models.DateTimeField(blank=True, null=True, verbose_name="Импортировано")),
            ],
            options={
                "verbose_name": "Группа стран Auto_DB_Pro",
                "verbose_name_plural": "Группы стран Auto_DB_Pro",
                "db_table": "autodb_pro_country_groups",
            },
        ),
        migrations.CreateModel(
            name="AutoDbLanguage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("autodb_language_id", models.BigIntegerField(db_index=True, unique=True, verbose_name="Auto-DB language ID")),
                ("code", models.CharField(blank=True, default="", max_length=32, verbose_name="Код")),
                ("name", models.CharField(blank=True, default="", max_length=255, verbose_name="Название")),
                ("source_payload", models.JSONField(blank=True, default=dict, verbose_name="Source payload")),
                ("source_updated_at", models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике")),
                ("imported_at", models.DateTimeField(blank=True, null=True, verbose_name="Импортировано")),
            ],
            options={
                "verbose_name": "Язык Auto_DB_Pro",
                "verbose_name_plural": "Языки Auto_DB_Pro",
                "db_table": "autodb_pro_languages",
            },
        ),
        migrations.RenameField(
            model_name="autodbsyncstate",
            old_name="scope",
            new_name="source_table",
        ),
        migrations.RenameField(
            model_name="autodbsyncstate",
            old_name="payload",
            new_name="metadata",
        ),
        migrations.AlterField(
            model_name="autodbsyncstate",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("running", "Running"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("paused", "Paused"),
                ],
                default="pending",
                max_length=32,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="failed_rows",
            field=models.BigIntegerField(default=0, verbose_name="Failed rows"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="finished_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Finished at"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="last_cursor",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Last cursor"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="last_error",
            field=models.TextField(blank=True, default="", verbose_name="Last error"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="last_offset",
            field=models.BigIntegerField(blank=True, null=True, verbose_name="Last offset"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="last_pk",
            field=models.BigIntegerField(blank=True, null=True, verbose_name="Last PK"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="processed_rows",
            field=models.BigIntegerField(default=0, verbose_name="Processed rows"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Started at"),
        ),
        migrations.AddField(
            model_name="autodbsyncstate",
            name="total_rows",
            field=models.BigIntegerField(default=0, verbose_name="Total rows"),
        ),
        migrations.AlterField(
            model_name="autodbvehiclemodel",
            name="manufacturer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="vehicle_models",
                to="autodb.autodbmanufacturer",
            ),
        ),
        migrations.AddField(
            model_name="autodbengine",
            name="imported_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Импортировано"),
        ),
        migrations.AddField(
            model_name="autodbengine",
            name="source_updated_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике"),
        ),
        migrations.AddField(
            model_name="autodbpassengercarengine",
            name="imported_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Импортировано"),
        ),
        migrations.AddField(
            model_name="autodbpassengercarengine",
            name="source_row_id",
            field=models.CharField(blank=True, db_index=True, max_length=128, null=True, unique=True, verbose_name="Source row ID"),
        ),
        migrations.AddField(
            model_name="autodbpassengercarengine",
            name="source_updated_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике"),
        ),
        migrations.AddField(
            model_name="autodbpassengercartree",
            name="imported_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Импортировано"),
        ),
        migrations.AddField(
            model_name="autodbpassengercartree",
            name="source_row_id",
            field=models.CharField(blank=True, db_index=True, max_length=128, null=True, unique=True, verbose_name="Source row ID"),
        ),
        migrations.AddField(
            model_name="autodbpassengercartree",
            name="source_updated_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике"),
        ),
        migrations.AddField(
            model_name="autodbproductgroup",
            name="imported_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Импортировано"),
        ),
        migrations.AddField(
            model_name="autodbproductgroup",
            name="source_updated_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике"),
        ),
        migrations.AddField(
            model_name="autodbvehicleattribute",
            name="imported_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Импортировано"),
        ),
        migrations.AddField(
            model_name="autodbvehicleattribute",
            name="source_row_id",
            field=models.CharField(blank=True, db_index=True, max_length=128, null=True, unique=True, verbose_name="Source row ID"),
        ),
        migrations.AddField(
            model_name="autodbvehicleattribute",
            name="source_updated_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Обновлено в источнике"),
        ),
    ]
