from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0024_product_svom_sku"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="views_count",
            field=models.PositiveIntegerField(db_index=True, default=0, verbose_name="Просмотры"),
        ),
    ]

