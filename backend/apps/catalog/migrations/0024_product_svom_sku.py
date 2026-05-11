from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0023_alter_category_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="svom_sku",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=32,
                null=True,
                unique=True,
                verbose_name="SVOM Public SKU",
            ),
        ),
    ]
