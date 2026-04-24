from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0013_order_status_processing_ready_for_shipment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VchasnoKasaSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(default="default", max_length=32, unique=True, verbose_name="Код профиля")),
                ("is_enabled", models.BooleanField(default=False, verbose_name="Вчасно.Каса включена")),
                ("api_token", models.CharField(blank=True, max_length=255, verbose_name="Токен кассы")),
                ("rro_fn", models.CharField(blank=True, max_length=64, verbose_name="Фискальный номер РРО/ПРРО")),
                ("default_payment_type", models.PositiveSmallIntegerField(default=1, verbose_name="Тип оплаты по умолчанию")),
                ("default_tax_group", models.CharField(blank=True, max_length=32, verbose_name="Налоговая группа по умолчанию")),
                ("auto_issue_on_completed", models.BooleanField(default=True, verbose_name="Автоматически создавать чек при завершении")),
                ("send_customer_email", models.BooleanField(default=True, verbose_name="Передавать email клиента")),
                ("last_connection_checked_at", models.DateTimeField(blank=True, null=True, verbose_name="Последняя проверка соединения")),
                ("last_connection_ok", models.BooleanField(blank=True, null=True, verbose_name="Последняя проверка успешна")),
                ("last_connection_message", models.TextField(blank=True, verbose_name="Сообщение последней проверки")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_vchasno_kasa_settings", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_vchasno_kasa_settings", to=settings.AUTH_USER_MODEL, verbose_name="Обновил")),
            ],
            options={
                "verbose_name": "Настройки Вчасно.Каса",
                "verbose_name_plural": "Настройки Вчасно.Каса",
            },
        ),
        migrations.CreateModel(
            name="OrderReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(choices=[("vchasno_kasa", "Вчасно.Каса")], default="vchasno_kasa", max_length=32, verbose_name="Провайдер")),
                ("receipt_type", models.CharField(choices=[("sale", "Продажа"), ("return", "Возврат")], default="sale", max_length=16, verbose_name="Тип чека")),
                ("external_order_id", models.UUIDField(default=uuid.uuid4, editable=False, verbose_name="Наш idempotency id")),
                ("vchasno_order_number", models.CharField(blank=True, max_length=128, verbose_name="Номер заказа во Вчасно")),
                ("check_fn", models.CharField(blank=True, max_length=128, verbose_name="Фискальный номер чека")),
                ("fiscal_status_code", models.IntegerField(blank=True, null=True, verbose_name="Код фискального статуса")),
                ("fiscal_status_key", models.CharField(blank=True, max_length=64, verbose_name="Ключ фискального статуса")),
                ("fiscal_status_label", models.CharField(blank=True, max_length=255, verbose_name="Подпись фискального статуса")),
                ("receipt_url", models.URLField(blank=True, max_length=1024, verbose_name="Ссылка на чек")),
                ("pdf_url", models.URLField(blank=True, max_length=1024, verbose_name="Ссылка на PDF")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Email")),
                ("email_sent_at", models.DateTimeField(blank=True, null=True, verbose_name="Чек отправлен на email")),
                ("fiscalized_at", models.DateTimeField(blank=True, null=True, verbose_name="Фискализирован")),
                ("error_code", models.CharField(blank=True, max_length=64, verbose_name="Код ошибки")),
                ("error_message", models.TextField(blank=True, verbose_name="Текст ошибки")),
                ("request_payload", models.JSONField(blank=True, default=dict, verbose_name="Payload запроса")),
                ("response_payload", models.JSONField(blank=True, default=dict, verbose_name="Payload ответа")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_order_receipts", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receipts", to="commerce.order", verbose_name="Заказ")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_order_receipts", to=settings.AUTH_USER_MODEL, verbose_name="Обновил")),
            ],
            options={
                "verbose_name": "Фискальный чек",
                "verbose_name_plural": "Фискальные чеки",
                "ordering": ("-updated_at", "-created_at"),
            },
        ),
        migrations.AddConstraint(
            model_name="orderreceipt",
            constraint=models.UniqueConstraint(fields=("order", "provider", "receipt_type"), name="commerce_order_receipt_provider_type_uniq"),
        ),
        migrations.AddIndex(
            model_name="orderreceipt",
            index=models.Index(fields=("provider", "receipt_type"), name="com_rcpt_provider_type_idx"),
        ),
        migrations.AddIndex(
            model_name="orderreceipt",
            index=models.Index(fields=("fiscal_status_code",), name="com_rcpt_status_code_idx"),
        ),
        migrations.AddIndex(
            model_name="orderreceipt",
            index=models.Index(fields=("vchasno_order_number",), name="com_rcpt_order_number_idx"),
        ),
    ]
