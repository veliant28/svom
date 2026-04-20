from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0007_rename_commerce_order_payment_provider_status_idx_com_ordpay_prov_stat_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_snapshot",
            field=models.JSONField(blank=True, default=dict, verbose_name="Снимок доставки"),
        ),
    ]
