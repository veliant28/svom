from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("autodb", "0008_autodbmatchingrun_autodbmatchjob_autodbmatchevidence_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="autodbremotequotastate",
            name="estimated_limit_per_hour",
            field=models.PositiveIntegerField(default=10000, verbose_name="Estimated limit per hour"),
        ),
        migrations.AddField(
            model_name="autodbremotequotastate",
            name="expected_reset_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Expected reset at"),
        ),
        migrations.AddField(
            model_name="autodbremotequotastate",
            name="last_query_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Last query at"),
        ),
        migrations.AddField(
            model_name="autodbremotequotastate",
            name="recent_points_json",
            field=models.JSONField(blank=True, default=list, verbose_name="Recent quota points"),
        ),
        migrations.AddField(
            model_name="autodbremotequotastate",
            name="window_started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Window started at"),
        ),
    ]
