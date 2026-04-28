from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_utrproductenrichment"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="category_manually_locked",
            field=models.BooleanField(default=False, verbose_name="Категория закреплена вручную"),
        ),
    ]
