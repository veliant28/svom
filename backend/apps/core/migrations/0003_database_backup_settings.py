from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_email_delivery_provider_from_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="DatabaseBackupSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(default="postgresql", max_length=32, unique=True, verbose_name="Код профиля")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="Бэкап включен")),
                ("schedule_cron", models.CharField(default="0 23 * * *", max_length=64, verbose_name="Cron расписание")),
                ("schedule_timezone", models.CharField(default="Europe/Kyiv", max_length=64, verbose_name="Часовой пояс расписания")),
                ("backup_directory", models.CharField(default="Backup", max_length=512, verbose_name="Папка бэкапов")),
                ("retention_count", models.PositiveIntegerField(default=3, verbose_name="Количество хранимых бэкапов")),
                ("last_started_at", models.DateTimeField(blank=True, null=True, verbose_name="Последний старт")),
                ("last_finished_at", models.DateTimeField(blank=True, null=True, verbose_name="Последний финиш")),
                ("last_success_at", models.DateTimeField(blank=True, null=True, verbose_name="Последний успешный бэкап")),
                ("last_failed_at", models.DateTimeField(blank=True, null=True, verbose_name="Последняя ошибка")),
                (
                    "last_status",
                    models.CharField(
                        choices=[
                            ("never_run", "Never run"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        default="never_run",
                        max_length=32,
                        verbose_name="Последний статус",
                    ),
                ),
                ("last_message", models.TextField(blank=True, verbose_name="Сообщение последнего запуска")),
                ("last_backup_path", models.CharField(blank=True, max_length=1024, verbose_name="Последний файл бэкапа")),
                ("last_backup_size", models.PositiveBigIntegerField(default=0, verbose_name="Размер последнего бэкапа")),
            ],
            options={
                "verbose_name": "Настройки бэкапа PostgreSQL",
                "verbose_name_plural": "Настройки бэкапа PostgreSQL",
            },
        ),
    ]
