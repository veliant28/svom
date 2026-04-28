from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class DatabaseBackupSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "postgresql"
    STATUS_NEVER_RUN = "never_run"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = (
        (STATUS_NEVER_RUN, _("Never run")),
        (STATUS_RUNNING, _("Running")),
        (STATUS_SUCCESS, _("Success")),
        (STATUS_FAILED, _("Failed")),
        (STATUS_SKIPPED, _("Skipped")),
    )

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)
    is_enabled = models.BooleanField(_("Бэкап включен"), default=True)
    schedule_cron = models.CharField(_("Cron расписание"), max_length=64, default="0 23 * * *")
    schedule_timezone = models.CharField(_("Часовой пояс расписания"), max_length=64, default="Europe/Kyiv")
    backup_directory = models.CharField(_("Папка бэкапов"), max_length=512, default="Backup")
    retention_count = models.PositiveIntegerField(_("Количество хранимых бэкапов"), default=3)

    last_started_at = models.DateTimeField(_("Последний старт"), blank=True, null=True)
    last_finished_at = models.DateTimeField(_("Последний финиш"), blank=True, null=True)
    last_success_at = models.DateTimeField(_("Последний успешный бэкап"), blank=True, null=True)
    last_failed_at = models.DateTimeField(_("Последняя ошибка"), blank=True, null=True)
    last_status = models.CharField(_("Последний статус"), max_length=32, choices=STATUS_CHOICES, default=STATUS_NEVER_RUN)
    last_message = models.TextField(_("Сообщение последнего запуска"), blank=True)
    last_backup_path = models.CharField(_("Последний файл бэкапа"), max_length=1024, blank=True)
    last_backup_size = models.PositiveBigIntegerField(_("Размер последнего бэкапа"), default=0)

    class Meta:
        verbose_name = _("Настройки бэкапа PostgreSQL")
        verbose_name_plural = _("Настройки бэкапа PostgreSQL")

    def __str__(self) -> str:
        return f"DatabaseBackupSettings:{self.code}"
