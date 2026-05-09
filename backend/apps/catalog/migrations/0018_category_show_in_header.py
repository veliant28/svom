from django.db import migrations, models


def seed_header_visibility(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    curated_names = {
        "автохимия и аксессуары",
        "тормозная система",
        "двигатель и система выхлопа",
        "детали кузова",
        "электричество и освещение",
        "сцепление и трансмиссия",
        "автохімія та аксесуари",
        "гальмівна система",
        "двигун і система вихлопу",
        "електрика та освітлення",
        "зчеплення та трансмісія",
    }

    Category.objects.filter(source="autodb_pro").update(show_in_header=False)

    for category in Category.objects.filter(parent__isnull=True, is_active=True).exclude(source="autodb_pro"):
        normalized = " ".join(str(category.name or "").split()).casefold()
        category.show_in_header = normalized in curated_names
        category.save(update_fields=["show_in_header", "updated_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0017_autodbproductlinkquality"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="show_in_header",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Показывать в шапке"),
        ),
        migrations.RunPython(seed_header_visibility, noop_reverse),
    ]
