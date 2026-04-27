from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0007_backfill_supplieroffer_last_seen_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplieroffer",
            name="price_levels",
            field=models.JSONField(blank=True, default=list, verbose_name="Уровни цен"),
        ),
    ]
