from django.db import migrations, models


def purge_legacy_garage_rows(apps, schema_editor):
    GarageVehicle = apps.get_model("users", "GarageVehicle")
    (
        GarageVehicle.objects.filter(catalog_source="legacy")
        | GarageVehicle.objects.filter(autodb_passanger_car_id__isnull=True)
    ).delete()
    GarageVehicle.objects.exclude(catalog_source="autodb_pro").update(catalog_source="autodb_pro")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0017_backoffice_security_capabilities"),
    ]

    operations = [
        migrations.RunPython(purge_legacy_garage_rows, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="garagevehicle",
            name="users_garage_unique_autocatalog_vehicle_per_user",
        ),
        migrations.RemoveField(
            model_name="garagevehicle",
            name="car_modification",
        ),
        migrations.AlterField(
            model_name="garagevehicle",
            name="catalog_source",
            field=models.CharField(
                choices=[("autodb_pro", "Auto_DB_Pro")],
                db_index=True,
                default="autodb_pro",
                max_length=24,
                verbose_name="Каталог-источник",
            ),
        ),
    ]
