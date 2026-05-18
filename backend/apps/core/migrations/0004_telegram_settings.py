from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_database_backup_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelegramSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(default="default", max_length=32, unique=True, verbose_name="Код профиля")),
                ("is_enabled", models.BooleanField(default=False, verbose_name="Telegram интеграция включена")),
                ("ops_enabled", models.BooleanField(default=False, verbose_name="Ops бот включен")),
                ("support_enabled", models.BooleanField(default=False, verbose_name="Support бот включен")),
                ("system_enabled", models.BooleanField(default=False, verbose_name="System бот включен")),
                ("ops_bot_token", models.CharField(blank=True, default="", max_length=255, verbose_name="Ops bot token")),
                ("ops_chat_id", models.CharField(blank=True, default="", max_length=64, verbose_name="Ops chat ID")),
                ("support_bot_token", models.CharField(blank=True, default="", max_length=255, verbose_name="Support bot token")),
                ("support_chat_id", models.CharField(blank=True, default="", max_length=64, verbose_name="Support chat ID")),
                ("system_bot_token", models.CharField(blank=True, default="", max_length=255, verbose_name="System bot token")),
                ("system_chat_id", models.CharField(blank=True, default="", max_length=64, verbose_name="System chat ID")),
                ("ops_notify_order_status", models.BooleanField(default=True, verbose_name="Ops: уведомления о статусах заказа")),
                ("ops_notify_waybill_created", models.BooleanField(default=True, verbose_name="Ops: уведомления о создании ТТН")),
                ("ops_notify_waybill_updated", models.BooleanField(default=True, verbose_name="Ops: уведомления о редактировании ТТН")),
                ("ops_notify_waybill_deleted", models.BooleanField(default=True, verbose_name="Ops: уведомления об удалении ТТН")),
                ("support_notify_new_thread", models.BooleanField(default=True, verbose_name="Support: новый чат поддержки")),
                ("support_notify_new_message", models.BooleanField(default=True, verbose_name="Support: новое сообщение от клиента")),
                ("system_notify_backup_status", models.BooleanField(default=True, verbose_name="System: бэкапы")),
                ("system_notify_import_status", models.BooleanField(default=True, verbose_name="System: импорты")),
            ],
            options={
                "verbose_name": "Настройки Telegram",
                "verbose_name_plural": "Настройки Telegram",
            },
        ),
    ]
