from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0011_product_autodb_article_composite_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="name_manually_locked",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Название закреплено вручную"),
        ),
        migrations.AddField(
            model_name="product",
            name="name_source",
            field=models.CharField(
                blank=True,
                choices=[("autodb_pro", "Auto_DB_Pro"), ("supplier_fallback", "Supplier fallback"), ("manual", "Manual")],
                db_index=True,
                default="",
                max_length=32,
                verbose_name="Источник названия",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="name_source_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="Хеш исходного названия"),
        ),
        migrations.AddField(
            model_name="product",
            name="name_source_text",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Исходный текст названия"),
        ),
        migrations.AddField(
            model_name="product",
            name="name_translation_error",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Ошибка перевода названия"),
        ),
        migrations.AddField(
            model_name="product",
            name="name_translation_status",
            field=models.CharField(
                blank=True,
                choices=[("pending", "Pending"), ("translated", "Translated"), ("failed", "Failed"), ("manual_locked", "Manual locked")],
                db_index=True,
                default="",
                max_length=24,
                verbose_name="Статус перевода названия",
            ),
        ),
    ]
