from django.db import migrations


def detach_local_vehicle_modifications(apps, schema_editor):
    ProductFitment = apps.get_model("compatibility", "ProductFitment")
    ProductFitment.objects.exclude(modification_id__isnull=True).update(modification_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("compatibility", "0004_productfitment_quality_fields"),
    ]

    operations = [
        migrations.RunPython(detach_local_vehicle_modifications, migrations.RunPython.noop),
    ]
