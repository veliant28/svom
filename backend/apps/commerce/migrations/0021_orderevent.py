import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0020_order_last_action_by"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("status_change", "Смена статуса"),
                            ("reserve_items", "Резервирование позиций"),
                            ("supplier_override", "Замена предложения поставщика"),
                            ("supplier_order_create", "Создание заказа поставщику"),
                            ("supplier_order_cancel", "Отмена заказа поставщику"),
                            ("note_update", "Обновление заметки"),
                        ],
                        max_length=48,
                        verbose_name="Тип события",
                    ),
                ),
                ("action_label", models.CharField(max_length=255, verbose_name="Действие")),
                ("message", models.CharField(blank=True, max_length=500, verbose_name="Комментарий")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="Payload")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="order_events",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Создал",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="commerce.order",
                        verbose_name="Заказ",
                    ),
                ),
            ],
            options={
                "verbose_name": "Событие заказа",
                "verbose_name_plural": "События заказа",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="orderevent",
            index=models.Index(fields=("order", "-created_at"), name="com_ord_evt_ord_created_idx"),
        ),
        migrations.AddIndex(
            model_name="orderevent",
            index=models.Index(fields=("event_type",), name="com_ord_evt_type_idx"),
        ),
    ]
