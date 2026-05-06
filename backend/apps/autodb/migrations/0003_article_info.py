from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("autodb", "0002_content_and_product_groups"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoDbArticleInfo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_number", models.CharField(max_length=128, verbose_name="Артикул")),
                ("normalized_article", models.CharField(db_index=True, max_length=128, verbose_name="Нормализованный артикул")),
                ("info_text", models.TextField(blank=True, default="", verbose_name="Текстовая информация")),
                ("info_language", models.CharField(blank=True, default="", max_length=32, verbose_name="Язык")),
                ("info_type", models.CharField(blank=True, default="", max_length=64, verbose_name="Тип информации")),
                ("sort_order", models.IntegerField(default=0, verbose_name="Порядок сортировки")),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="article_infos",
                        to="autodb.autodbsupplier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Информация об артикуле Auto-DB",
                "verbose_name_plural": "Информация об артикулах Auto-DB",
                "db_table": "autodb_article_infos",
            },
        ),
        migrations.AddConstraint(
            model_name="autodbarticleinfo",
            constraint=models.UniqueConstraint(
                fields=("supplier", "article_number", "info_text", "info_language", "info_type"),
                name="adb_inf_uq_sup_art_text_lang_type",
            ),
        ),
        migrations.AddIndex(
            model_name="autodbarticleinfo",
            index=models.Index(fields=["supplier", "normalized_article"], name="adb_inf_sup_norm_art_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbarticleinfo",
            index=models.Index(fields=["info_type"], name="adb_inf_type_idx"),
        ),
    ]
