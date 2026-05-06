from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AutoDbManufacturer",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="Название")),
                ("matchcode", models.CharField(blank=True, max_length=255, verbose_name="Matchcode")),
            ],
            options={
                "verbose_name": "Производитель Auto-DB",
                "verbose_name_plural": "Производители Auto-DB",
                "db_table": "autodb_manufacturers",
            },
        ),
        migrations.CreateModel(
            name="AutoDbSupplier",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, max_length=255, verbose_name="Название")),
                ("matchcode", models.CharField(blank=True, max_length=255, verbose_name="Matchcode")),
                (
                    "normalized_name",
                    models.CharField(blank=True, db_index=True, max_length=255, verbose_name="Нормализованное название"),
                ),
                (
                    "normalized_matchcode",
                    models.CharField(blank=True, db_index=True, max_length=255, verbose_name="Нормализованный matchcode"),
                ),
            ],
            options={
                "verbose_name": "Поставщик Auto-DB",
                "verbose_name_plural": "Поставщики Auto-DB",
                "db_table": "autodb_suppliers",
            },
        ),
        migrations.AddIndex(
            model_name="autodbsupplier",
            index=models.Index(fields=["normalized_matchcode"], name="autodb_sup_norm_match_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbsupplier",
            index=models.Index(fields=["normalized_name"], name="autodb_sup_norm_name_idx"),
        ),
        migrations.CreateModel(
            name="AutoDbVehicleModel",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="Модель")),
                ("full_description", models.CharField(blank=True, max_length=255, verbose_name="Полное описание")),
                (
                    "manufacturer",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="vehicle_models",
                        to="autodb.autodbmanufacturer",
                    ),
                ),
            ],
            options={
                "verbose_name": "Модель Auto-DB",
                "verbose_name_plural": "Модели Auto-DB",
                "db_table": "autodb_models",
            },
        ),
        migrations.AddIndex(
            model_name="autodbvehiclemodel",
            index=models.Index(fields=["manufacturer"], name="autodb_model_manu_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbvehiclemodel",
            index=models.Index(fields=["description"], name="autodb_model_desc_idx"),
        ),
        migrations.CreateModel(
            name="AutoDbPassengerCar",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="Модификация")),
                ("full_description", models.CharField(blank=True, max_length=255, verbose_name="Полное описание")),
                ("construction_interval", models.CharField(blank=True, max_length=64, verbose_name="Интервал выпуска")),
                ("start_year", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Год начала")),
                ("start_month", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Месяц начала")),
                ("end_year", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Год окончания")),
                ("end_month", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Месяц окончания")),
                (
                    "model",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="passenger_cars",
                        to="autodb.autodbvehiclemodel",
                    ),
                ),
            ],
            options={
                "verbose_name": "Легковой автомобиль Auto-DB",
                "verbose_name_plural": "Легковые автомобили Auto-DB",
                "db_table": "autodb_passenger_cars",
            },
        ),
        migrations.AddIndex(
            model_name="autodbpassengercar",
            index=models.Index(fields=["model"], name="autodb_pc_model_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbpassengercar",
            index=models.Index(fields=["start_year", "end_year"], name="autodb_pc_years_idx"),
        ),
        migrations.CreateModel(
            name="AutoDbArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_number", models.CharField(max_length=128, verbose_name="Артикул")),
                ("normalized_article", models.CharField(db_index=True, max_length=128, verbose_name="Нормализованный артикул")),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="articles",
                        to="autodb.autodbsupplier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Артикул Auto-DB",
                "verbose_name_plural": "Артикулы Auto-DB",
                "db_table": "autodb_articles",
            },
        ),
        migrations.AddConstraint(
            model_name="autodbarticle",
            constraint=models.UniqueConstraint(
                fields=("supplier", "article_number"),
                name="adb_art_uq_sup_art",
            ),
        ),
        migrations.AddIndex(
            model_name="autodbarticle",
            index=models.Index(fields=["supplier", "normalized_article"], name="autodb_art_sup_norm_idx"),
        ),
        migrations.CreateModel(
            name="AutoDbArticleLinkage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_number", models.CharField(max_length=128, verbose_name="Артикул")),
                ("normalized_article", models.CharField(db_index=True, max_length=128, verbose_name="Нормализованный артикул")),
                ("linkage_type", models.CharField(max_length=32, verbose_name="Тип связи")),
                ("linkage_id", models.PositiveIntegerField(verbose_name="ID связи")),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="article_linkages",
                        to="autodb.autodbsupplier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Связь артикула с авто Auto-DB",
                "verbose_name_plural": "Связи артикулов с авто Auto-DB",
                "db_table": "autodb_article_linkages",
            },
        ),
        migrations.AddConstraint(
            model_name="autodbarticlelinkage",
            constraint=models.UniqueConstraint(
                fields=("supplier", "article_number", "linkage_type", "linkage_id"),
                name="adb_link_uq_sup_art_type_id",
            ),
        ),
        migrations.AddIndex(
            model_name="autodbarticlelinkage",
            index=models.Index(fields=["supplier", "normalized_article"], name="adb_link_sup_norm_art_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbarticlelinkage",
            index=models.Index(fields=["linkage_type", "linkage_id"], name="autodb_linkage_type_id_idx"),
        ),
    ]
