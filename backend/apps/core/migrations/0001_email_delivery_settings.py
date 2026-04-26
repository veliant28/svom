from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EmailDeliverySettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(default="default", max_length=32, unique=True, verbose_name="Код профиля")),
                ("is_enabled", models.BooleanField(default=False, verbose_name="SMTP отправка включена")),
                ("from_email", models.CharField(blank=True, max_length=255, verbose_name="Email отправителя")),
                ("host", models.CharField(blank=True, max_length=255, verbose_name="SMTP host")),
                ("port", models.PositiveIntegerField(default=587, verbose_name="SMTP port")),
                ("host_user", models.CharField(blank=True, max_length=255, verbose_name="SMTP user")),
                ("host_password", models.CharField(blank=True, max_length=255, verbose_name="SMTP password")),
                ("use_tls", models.BooleanField(default=True, verbose_name="Use TLS")),
                ("use_ssl", models.BooleanField(default=False, verbose_name="Use SSL")),
                ("timeout", models.PositiveIntegerField(default=10, verbose_name="Timeout")),
                ("frontend_base_url", models.URLField(blank=True, max_length=255, verbose_name="Frontend base URL")),
                ("last_connection_checked_at", models.DateTimeField(blank=True, null=True, verbose_name="Последняя проверка соединения")),
                ("last_connection_ok", models.BooleanField(blank=True, null=True, verbose_name="Последняя проверка успешна")),
                ("last_connection_message", models.TextField(blank=True, verbose_name="Сообщение последней проверки")),
            ],
            options={
                "verbose_name": "Настройки отправки email",
                "verbose_name_plural": "Настройки отправки email",
            },
        ),
    ]
