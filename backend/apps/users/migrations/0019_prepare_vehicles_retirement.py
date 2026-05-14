from django.db import migrations


def detach_local_vehicle_fk_from_garage(apps, schema_editor):
    GarageVehicle = apps.get_model("users", "GarageVehicle")
    GarageVehicle.objects.exclude(make_id__isnull=True).update(make_id=None)
    GarageVehicle.objects.exclude(model_id__isnull=True).update(model_id=None)
    GarageVehicle.objects.exclude(generation_id__isnull=True).update(generation_id=None)
    GarageVehicle.objects.exclude(engine_id__isnull=True).update(engine_id=None)
    GarageVehicle.objects.exclude(modification_id__isnull=True).update(modification_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_garagevehicle_drop_legacy_autocatalog_fk"),
    ]

    operations = [
        migrations.RunPython(detach_local_vehicle_fk_from_garage, migrations.RunPython.noop),
    ]
