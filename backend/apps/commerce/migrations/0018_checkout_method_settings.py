from django.db import migrations, models
import uuid


def create_default_checkout_method_settings(apps, schema_editor):
    CheckoutMethodSettings = apps.get_model("commerce", "CheckoutMethodSettings")
    CheckoutMethodSettings.objects.get_or_create(code="default")


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0017_vchasnokasasettings_fiscal_api_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckoutMethodSettings",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(default="default", max_length=32, unique=True, verbose_name="Код профиля")),
                ("pickup_enabled", models.BooleanField(default=True, verbose_name="Самовывоз включен")),
                ("nova_poshta_enabled", models.BooleanField(default=True, verbose_name="Новая Почта включена")),
                ("courier_enabled", models.BooleanField(default=True, verbose_name="Курьер включен")),
                ("cash_on_delivery_enabled", models.BooleanField(default=True, verbose_name="Наложенный платеж включен")),
                ("monobank_enabled", models.BooleanField(default=True, verbose_name="Monobank включен в checkout")),
                ("liqpay_enabled", models.BooleanField(default=True, verbose_name="LiqPay включен в checkout")),
            ],
            options={
                "verbose_name": "Настройки способов оформления заказа",
                "verbose_name_plural": "Настройки способов оформления заказа",
            },
        ),
        migrations.RunPython(create_default_checkout_method_settings, noop_reverse),
    ]
