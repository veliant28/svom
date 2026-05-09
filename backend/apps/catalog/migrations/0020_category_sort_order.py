from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0019_product_category_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="sort_order",
            field=models.PositiveIntegerField(db_index=True, default=1000, verbose_name="Порядок сортировки"),
        ),
    ]
