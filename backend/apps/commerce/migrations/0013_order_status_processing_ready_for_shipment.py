from django.db import migrations, models


STATUS_MAP_FORWARD = {
    'new': 'new',
    'confirmed': 'processing',
    'awaiting_procurement': 'processing',
    'reserved': 'processing',
    'partially_reserved': 'processing',
    'ready_to_ship': 'ready_for_shipment',
    'shipped': 'shipped',
    'completed': 'completed',
    'cancelled': 'cancelled',
    'draft': 'new',
    'placed': 'new',
}

STATUS_MAP_REVERSE = {
    'new': 'new',
    'processing': 'confirmed',
    'ready_for_shipment': 'ready_to_ship',
    'shipped': 'shipped',
    'completed': 'completed',
    'cancelled': 'cancelled',
}


def forwards(apps, schema_editor):
    Order = apps.get_model('commerce', 'Order')
    for old_status, new_status in STATUS_MAP_FORWARD.items():
        Order.objects.filter(status=old_status).update(status=new_status)


def backwards(apps, schema_editor):
    Order = apps.get_model('commerce', 'Order')
    for old_status, new_status in STATUS_MAP_REVERSE.items():
        Order.objects.filter(status=old_status).update(status=new_status)


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0012_order_applied_promo_code_order_discount_breakdown_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('new', 'Новый'),
                    ('processing', 'В работе'),
                    ('ready_for_shipment', 'Готов к отправке'),
                    ('shipped', 'Отправлен'),
                    ('completed', 'Завершен'),
                    ('cancelled', 'Отменен'),
                ],
                default='new',
                max_length=32,
                verbose_name='Статус',
            ),
        ),
    ]
