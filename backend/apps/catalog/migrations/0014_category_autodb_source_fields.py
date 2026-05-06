from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0013_autodbarticlemanualmapping"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="autodb_prd_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True, unique=True, verbose_name="Auto_DB_Pro PRD ID"),
        ),
        migrations.AddField(
            model_name="category",
            name="source",
            field=models.CharField(
                blank=True,
                choices=[("autodb_pro", "Auto_DB_Pro"), ("manual", "Manual"), ("legacy", "Legacy"), ("import", "Import")],
                db_index=True,
                default="legacy",
                max_length=24,
                verbose_name="Источник",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="source_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="Source hash"),
        ),
        migrations.AddField(
            model_name="category",
            name="source_payload",
            field=models.JSONField(blank=True, default=dict, verbose_name="Source payload"),
        ),
    ]
