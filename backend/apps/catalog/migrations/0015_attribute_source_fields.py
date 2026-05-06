from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0014_category_autodb_source_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="attribute",
            name="autodb_attribute_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name="Auto_DB_Pro attribute ID"),
        ),
        migrations.AddField(
            model_name="attribute",
            name="name_en",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="Название (EN)"),
        ),
        migrations.AddField(
            model_name="attribute",
            name="name_ru",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="Название (RU)"),
        ),
        migrations.AddField(
            model_name="attribute",
            name="name_uk",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="Название (UA)"),
        ),
        migrations.AddField(
            model_name="attribute",
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
            model_name="attribute",
            name="source_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="Source hash"),
        ),
        migrations.AddField(
            model_name="attribute",
            name="source_payload",
            field=models.JSONField(blank=True, default=dict, verbose_name="Source payload"),
        ),
        migrations.AddField(
            model_name="attributevalue",
            name="autodb_attribute_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name="Auto_DB_Pro attribute ID"),
        ),
        migrations.AddField(
            model_name="attributevalue",
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
            model_name="attributevalue",
            name="source_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="Source hash"),
        ),
        migrations.AddField(
            model_name="attributevalue",
            name="source_payload",
            field=models.JSONField(blank=True, default=dict, verbose_name="Source payload"),
        ),
        migrations.AddField(
            model_name="attributevalue",
            name="value_en",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Значение (EN)"),
        ),
        migrations.AddField(
            model_name="attributevalue",
            name="value_ru",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Значение (RU)"),
        ),
        migrations.AddField(
            model_name="attributevalue",
            name="value_uk",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Значение (UA)"),
        ),
        migrations.AddField(
            model_name="productattribute",
            name="autodb_attribute_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name="Auto_DB_Pro attribute ID"),
        ),
        migrations.AddField(
            model_name="productattribute",
            name="manual_locked",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Характеристика закреплена вручную"),
        ),
        migrations.AddField(
            model_name="productattribute",
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
            model_name="productattribute",
            name="source_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="Source hash"),
        ),
        migrations.AddField(
            model_name="productattribute",
            name="source_payload",
            field=models.JSONField(blank=True, default=dict, verbose_name="Source payload"),
        ),
    ]
