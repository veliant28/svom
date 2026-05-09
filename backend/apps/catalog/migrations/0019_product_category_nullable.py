from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0018_category_show_in_header"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="catalog.category",
                verbose_name="Категория",
            ),
        ),
    ]

