from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0021_product_brand_enrichment_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="is_assignable",
            field=models.BooleanField(db_index=True, default=True, verbose_name="Можно назначать товарам"),
        ),
        migrations.CreateModel(
            name="CategoryNavigationCollection",
            fields=[
                ("is_active", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180, verbose_name="Название")),
                ("title_uk", models.CharField(blank=True, default="", max_length=180, verbose_name="Название (UA)")),
                ("title_ru", models.CharField(blank=True, default="", max_length=180, verbose_name="Название (RU)")),
                ("title_en", models.CharField(blank=True, default="", max_length=180, verbose_name="Название (EN)")),
                ("slug", models.SlugField(max_length=220, unique=True, verbose_name="Slug")),
                ("show_in_header", models.BooleanField(db_index=True, default=False, verbose_name="Показывать в шапке")),
                ("sort_order", models.PositiveIntegerField(db_index=True, default=1000, verbose_name="Порядок сортировки")),
                (
                    "root_category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="navigation_collections",
                        to="catalog.category",
                        verbose_name="Корневая категория навигации",
                    ),
                ),
            ],
            options={
                "verbose_name": "Навигационная коллекция",
                "verbose_name_plural": "Навигационные коллекции",
                "ordering": ("sort_order", "title", "id"),
            },
        ),
        migrations.CreateModel(
            name="CategoryNavigationGroup",
            fields=[
                ("is_active", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180, verbose_name="Название")),
                ("title_uk", models.CharField(blank=True, default="", max_length=180, verbose_name="Название (UA)")),
                ("title_ru", models.CharField(blank=True, default="", max_length=180, verbose_name="Название (RU)")),
                ("title_en", models.CharField(blank=True, default="", max_length=180, verbose_name="Название (EN)")),
                ("slug", models.SlugField(max_length=220, verbose_name="Slug")),
                ("sort_order", models.PositiveIntegerField(db_index=True, default=1000, verbose_name="Порядок сортировки")),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="groups",
                        to="catalog.categorynavigationcollection",
                        verbose_name="Коллекция",
                    ),
                ),
            ],
            options={
                "verbose_name": "Группа навигации",
                "verbose_name_plural": "Группы навигации",
                "ordering": ("sort_order", "title", "id"),
            },
        ),
        migrations.CreateModel(
            name="CategoryNavigationItem",
            fields=[
                ("is_active", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title_override", models.CharField(blank=True, default="", max_length=180, verbose_name="Переопределение названия")),
                ("title_override_uk", models.CharField(blank=True, default="", max_length=180, verbose_name="Переопределение названия (UA)")),
                ("title_override_ru", models.CharField(blank=True, default="", max_length=180, verbose_name="Переопределение названия (RU)")),
                ("title_override_en", models.CharField(blank=True, default="", max_length=180, verbose_name="Переопределение названия (EN)")),
                ("sort_order", models.PositiveIntegerField(db_index=True, default=1000, verbose_name="Порядок сортировки")),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="navigation_items",
                        to="catalog.category",
                        verbose_name="Категория",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="catalog.categorynavigationgroup",
                        verbose_name="Группа",
                    ),
                ),
            ],
            options={
                "verbose_name": "Пункт навигации",
                "verbose_name_plural": "Пункты навигации",
                "ordering": ("sort_order", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="categorynavigationgroup",
            constraint=models.UniqueConstraint(fields=("collection", "slug"), name="uniq_catalog_nav_group_collection_slug"),
        ),
        migrations.AddConstraint(
            model_name="categorynavigationitem",
            constraint=models.UniqueConstraint(fields=("group", "category"), name="uniq_catalog_nav_item_group_category"),
        ),
    ]
