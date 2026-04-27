from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_email_delivery_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="emaildeliverysettings",
            name="provider",
            field=models.CharField(
                choices=[("resend_smtp", "Resend SMTP"), ("manual_smtp", "Manual SMTP")],
                default="manual_smtp",
                max_length=32,
                verbose_name="SMTP provider",
            ),
        ),
        migrations.AddField(
            model_name="emaildeliverysettings",
            name="from_name",
            field=models.CharField(blank=True, max_length=255, verbose_name="Имя отправителя"),
        ),
    ]
