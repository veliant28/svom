from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0019_prepare_vehicles_retirement"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="garagevehicle",
            name="users_garage_unique_vehicle_per_user",
        ),
        migrations.RemoveField(
            model_name="garagevehicle",
            name="make",
        ),
        migrations.RemoveField(
            model_name="garagevehicle",
            name="model",
        ),
        migrations.RemoveField(
            model_name="garagevehicle",
            name="generation",
        ),
        migrations.RemoveField(
            model_name="garagevehicle",
            name="engine",
        ),
        migrations.RemoveField(
            model_name="garagevehicle",
            name="modification",
        ),
    ]
