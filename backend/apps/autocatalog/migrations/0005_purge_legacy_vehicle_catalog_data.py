from django.db import migrations


def purge_legacy_autocatalog_data(apps, schema_editor):
    UtrDetailCarMap = apps.get_model("autocatalog", "UtrDetailCarMap")
    CarModification = apps.get_model("autocatalog", "CarModification")
    CarModel = apps.get_model("autocatalog", "CarModel")
    CarMake = apps.get_model("autocatalog", "CarMake")

    UtrDetailCarMap.objects.all().delete()
    CarModification.objects.all().delete()
    CarModel.objects.all().delete()
    CarMake.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("autocatalog", "0004_carmodification_end_date_at"),
        ("users", "0018_garagevehicle_drop_legacy_autocatalog_fk"),
    ]

    operations = [
        migrations.RunPython(purge_legacy_autocatalog_data, migrations.RunPython.noop),
    ]
