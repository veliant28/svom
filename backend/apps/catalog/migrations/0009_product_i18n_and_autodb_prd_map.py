from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_product_available_stock_qty_cached"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="name_en",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Название (EN)"),
        ),
        migrations.AddField(
            model_name="product",
            name="name_ru",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Название (RU)"),
        ),
        migrations.AddField(
            model_name="product",
            name="name_uk",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Название (UA)"),
        ),
        migrations.CreateModel(
            name="AutoDbPrdCategoryMap",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("prd_id", models.PositiveIntegerField(db_index=True, unique=True, verbose_name="ID группы Auto-DB")),
                ("prd_name", models.CharField(blank=True, default="", max_length=255, verbose_name="Название группы Auto-DB")),
                (
                    "source",
                    models.CharField(
                        choices=[("auto", "Автоматически"), ("manual", "Вручную")],
                        default="auto",
                        max_length=16,
                        verbose_name="Источник",
                    ),
                ),
                ("confidence", models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True, verbose_name="Уверенность")),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="autodb_prd_maps",
                        to="catalog.category",
                        verbose_name="Категория каталога",
                    ),
                ),
            ],
            options={
                "verbose_name": "Маппинг группы Auto-DB в категорию",
                "verbose_name_plural": "Маппинги групп Auto-DB в категории",
                "ordering": ("prd_name", "prd_id"),
            },
        ),
    ]
