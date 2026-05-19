from django.db import migrations, models


def forwards_unify_refund_status(apps, schema_editor):
    ReturnRequest = apps.get_model("commerce", "ReturnRequest")
    ReturnEvent = apps.get_model("commerce", "ReturnEvent")

    ReturnRequest.objects.filter(status="refund_processing").update(status="refunded")
    ReturnEvent.objects.filter(from_status="refund_processing").update(from_status="refunded")
    ReturnEvent.objects.filter(to_status="refund_processing").update(to_status="refunded")


def backwards_unify_refund_status(apps, schema_editor):
    # Backward migration keeps unified status as-is.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0023_returnrequestnumbersequence"),
    ]

    operations = [
        migrations.RunPython(forwards_unify_refund_status, backwards_unify_refund_status),
        migrations.AlterField(
            model_name="returnrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("new", "Новая заявка"),
                    ("approved", "Одобрено"),
                    ("rejected", "Отказано"),
                    ("awaiting_ttn", "Ожидаем ТТН"),
                    ("in_transit", "В пути"),
                    ("received", "Получено"),
                    ("accepted", "Принято"),
                    ("refunded", "Возврат"),
                    ("cancelled", "Отменено"),
                ],
                db_index=True,
                default="new",
                max_length=32,
                verbose_name="Статус",
            ),
        ),
    ]
