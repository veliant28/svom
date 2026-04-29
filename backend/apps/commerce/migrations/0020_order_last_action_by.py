from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0019_checkoutmethodsettings_novapay_enabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="last_action_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="orders_last_action",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Последнее действие выполнил",
            ),
        ),
    ]
