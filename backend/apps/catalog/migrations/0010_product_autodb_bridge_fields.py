from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_product_i18n_and_autodb_prd_map"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="autodb_article_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name="Auto_DB_Pro article ID"),
        ),
        migrations.AddField(
            model_name="product",
            name="autodb_supplier_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name="Auto_DB_Pro supplier ID"),
        ),
        migrations.AddField(
            model_name="product",
            name="catalog_source",
            field=models.CharField(
                blank=True,
                choices=[("legacy", "Legacy"), ("autodb_pro", "Auto_DB_Pro")],
                db_index=True,
                default="",
                max_length=24,
                verbose_name="Источник каталога",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="normalized_article",
            field=models.CharField(blank=True, db_index=True, default="", max_length=128, verbose_name="Нормализованный артикул"),
        ),
        migrations.AddField(
            model_name="product",
            name="normalized_brand",
            field=models.CharField(blank=True, db_index=True, default="", max_length=180, verbose_name="Нормализованный бренд"),
        ),
    ]
