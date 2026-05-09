from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0022_category_assignability_navigation"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="category",
            options={
                "ordering": ("sort_order", "name", "id"),
                "verbose_name": "Категория",
                "verbose_name_plural": "Категории",
            },
        ),
    ]
