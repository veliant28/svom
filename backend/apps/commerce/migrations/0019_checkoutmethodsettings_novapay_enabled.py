from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0018_checkout_method_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="checkoutmethodsettings",
            name="novapay_enabled",
            field=models.BooleanField(default=True, verbose_name="Nova Pay включен в checkout"),
        ),
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("monobank", "Monobank"),
                    ("novapay", "Nova Pay"),
                    ("liqpay", "LiqPay"),
                    ("cash_on_delivery", "Наложенный платеж"),
                    ("card_placeholder", "Оплата картой (legacy)"),
                ],
                max_length=32,
                verbose_name="Способ оплаты",
            ),
        ),
        migrations.AlterField(
            model_name="orderpayment",
            name="method",
            field=models.CharField(
                choices=[
                    ("monobank", "Monobank"),
                    ("novapay", "Nova Pay"),
                    ("liqpay", "LiqPay"),
                    ("cash_on_delivery", "Наложенный платеж"),
                ],
                default="cash_on_delivery",
                max_length=32,
                verbose_name="Метод оплаты",
            ),
        ),
        migrations.AlterField(
            model_name="orderpayment",
            name="provider",
            field=models.CharField(
                choices=[
                    ("monobank", "Monobank"),
                    ("novapay", "Nova Pay"),
                    ("liqpay", "LiqPay"),
                    ("cash_on_delivery", "Наложенный платеж"),
                ],
                default="cash_on_delivery",
                max_length=32,
                verbose_name="Провайдер оплаты",
            ),
        ),
    ]
