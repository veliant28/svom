from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0010_product_autodb_bridge_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="autodb_article_number",
            field=models.CharField(blank=True, db_index=True, default="", max_length=128, verbose_name="Auto_DB_Pro article number"),
        ),
        migrations.AddField(
            model_name="product",
            name="autodb_article_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=196, verbose_name="Auto_DB_Pro article key"),
        ),
    ]
