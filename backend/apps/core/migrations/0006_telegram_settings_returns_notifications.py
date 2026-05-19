from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_returnservicesettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramsettings",
            name="ops_notify_return_created",
            field=models.BooleanField(default=True, verbose_name="Ops: уведомления о новых возвратах"),
        ),
        migrations.AddField(
            model_name="telegramsettings",
            name="ops_notify_return_status",
            field=models.BooleanField(default=True, verbose_name="Ops: уведомления о статусах возвратов"),
        ),
    ]
