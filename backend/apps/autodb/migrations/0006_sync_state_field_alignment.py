from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("autodb", "0005_vehicle_catalog_sync_infra"),
    ]

    operations = [
        migrations.AlterField(
            model_name="autodbsyncstate",
            name="metadata",
            field=models.JSONField(blank=True, default=dict, verbose_name="Metadata"),
        ),
        migrations.AlterField(
            model_name="autodbsyncstate",
            name="source_table",
            field=models.CharField(max_length=64, unique=True, verbose_name="Source table"),
        ),
    ]
