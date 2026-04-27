from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0005_pricehistory_summary_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplieroffer",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Последний раз в прайсе"),
        ),
        migrations.AddIndex(
            model_name="supplieroffer",
            index=models.Index(fields=["supplier", "last_seen_at"], name="pricing_so_supplier_seen_idx"),
        ),
    ]
