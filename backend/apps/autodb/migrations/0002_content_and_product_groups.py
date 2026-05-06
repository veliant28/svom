from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("autodb", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoDbArticleAttribute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_number", models.CharField(max_length=128, verbose_name="Артикул")),
                ("normalized_article", models.CharField(db_index=True, max_length=128, verbose_name="Нормализованный артикул")),
                ("attribute_name", models.CharField(max_length=255, verbose_name="Название характеристики")),
                ("attribute_value", models.TextField(blank=True, default="", verbose_name="Значение характеристики")),
                ("unit", models.CharField(blank=True, default="", max_length=64, verbose_name="Единица измерения")),
                ("sort_order", models.IntegerField(default=0, verbose_name="Порядок сортировки")),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="article_attributes",
                        to="autodb.autodbsupplier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Характеристика артикула Auto-DB",
                "verbose_name_plural": "Характеристики артикулов Auto-DB",
                "db_table": "autodb_article_attributes",
            },
        ),
        migrations.AddConstraint(
            model_name="autodbarticleattribute",
            constraint=models.UniqueConstraint(
                fields=("supplier", "article_number", "attribute_name", "attribute_value", "unit"),
                name="adb_attr_uq_sup_art_name_value_unit",
            ),
        ),
        migrations.AddIndex(
            model_name="autodbarticleattribute",
            index=models.Index(fields=["supplier", "normalized_article"], name="adb_attr_sup_norm_art_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbarticleattribute",
            index=models.Index(fields=["attribute_name"], name="adb_attr_name_idx"),
        ),
        migrations.CreateModel(
            name="AutoDbArticleImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_number", models.CharField(max_length=128, verbose_name="Артикул")),
                ("normalized_article", models.CharField(db_index=True, max_length=128, verbose_name="Нормализованный артикул")),
                ("image_url", models.TextField(blank=True, default="", verbose_name="URL изображения")),
                ("image_path", models.TextField(blank=True, default="", verbose_name="Путь изображения")),
                ("file_extension", models.CharField(blank=True, default="", max_length=16, verbose_name="Расширение файла")),
                ("is_primary", models.BooleanField(default=False, verbose_name="Основное изображение")),
                ("sort_order", models.IntegerField(default=0, verbose_name="Порядок сортировки")),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="article_images",
                        to="autodb.autodbsupplier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Изображение артикула Auto-DB",
                "verbose_name_plural": "Изображения артикулов Auto-DB",
                "db_table": "autodb_article_images",
            },
        ),
        migrations.AddConstraint(
            model_name="autodbarticleimage",
            constraint=models.UniqueConstraint(
                fields=("supplier", "article_number", "image_url", "image_path"),
                name="adb_img_uq_sup_art_url_path",
            ),
        ),
        migrations.AddIndex(
            model_name="autodbarticleimage",
            index=models.Index(fields=["supplier", "normalized_article"], name="adb_img_sup_norm_art_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbarticleimage",
            index=models.Index(fields=["is_primary"], name="adb_img_primary_idx"),
        ),
        migrations.CreateModel(
            name="AutoDbProductGroup",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, max_length=255, verbose_name="Название группы")),
                ("normalized_name", models.CharField(blank=True, db_index=True, max_length=255, verbose_name="Нормализованное название")),
            ],
            options={
                "verbose_name": "Группа товаров Auto-DB",
                "verbose_name_plural": "Группы товаров Auto-DB",
                "db_table": "autodb_product_groups",
            },
        ),
        migrations.AddIndex(
            model_name="autodbproductgroup",
            index=models.Index(fields=["normalized_name"], name="adb_prd_norm_name_idx"),
        ),
        migrations.CreateModel(
            name="AutoDbArticleProductGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_number", models.CharField(max_length=128, verbose_name="Артикул")),
                ("normalized_article", models.CharField(db_index=True, max_length=128, verbose_name="Нормализованный артикул")),
                (
                    "product_group",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="article_links",
                        to="autodb.autodbproductgroup",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="article_product_groups",
                        to="autodb.autodbsupplier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Связь артикула с товарной группой Auto-DB",
                "verbose_name_plural": "Связи артикула с товарными группами Auto-DB",
                "db_table": "autodb_article_product_groups",
            },
        ),
        migrations.AddConstraint(
            model_name="autodbarticleproductgroup",
            constraint=models.UniqueConstraint(
                fields=("supplier", "article_number", "product_group"),
                name="adb_art_prd_uq_sup_art_prd",
            ),
        ),
        migrations.AddIndex(
            model_name="autodbarticleproductgroup",
            index=models.Index(fields=["supplier", "normalized_article"], name="adb_art_prd_sup_norm_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbarticleproductgroup",
            index=models.Index(fields=["product_group"], name="adb_art_prd_group_idx"),
        ),
    ]

