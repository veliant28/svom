from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class SupportThread(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_NEW = "new"
    STATUS_OPEN = "open"
    STATUS_WAITING_FOR_SUPPORT = "waiting_for_support"
    STATUS_WAITING_FOR_CLIENT = "waiting_for_client"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = (
        (STATUS_NEW, _("Новое")),
        (STATUS_OPEN, _("Открыто")),
        (STATUS_WAITING_FOR_SUPPORT, _("Ожидает поддержку")),
        (STATUS_WAITING_FOR_CLIENT, _("Ожидает клиента")),
        (STATUS_RESOLVED, _("Решено")),
        (STATUS_CLOSED, _("Закрыто")),
    )

    PRIORITY_LOW = "low"
    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"
    PRIORITY_CHOICES = (
        (PRIORITY_LOW, _("Низкий")),
        (PRIORITY_NORMAL, _("Обычный")),
        (PRIORITY_HIGH, _("Высокий")),
    )

    subject = models.CharField(_("Тема"), max_length=255)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_threads",
        verbose_name=_("Клиент"),
    )
    status = models.CharField(_("Статус"), max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW)
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_support_threads",
        verbose_name=_("Ответственный сотрудник"),
    )
    priority = models.CharField(
        _("Приоритет"),
        max_length=16,
        choices=PRIORITY_CHOICES,
        blank=True,
        default=PRIORITY_NORMAL,
    )
    last_message_at = models.DateTimeField(_("Время последнего сообщения"), blank=True, null=True)
    first_response_at = models.DateTimeField(_("Время первого ответа"), blank=True, null=True)
    resolved_at = models.DateTimeField(_("Время решения"), blank=True, null=True)
    closed_at = models.DateTimeField(_("Время закрытия"), blank=True, null=True)

    class Meta:
        ordering = ("-last_message_at", "-created_at")
        verbose_name = _("Обращение в поддержку")
        verbose_name_plural = _("Обращения в поддержку")
        indexes = [
            models.Index(fields=("customer", "status"), name="sup_thr_cust_status_idx"),
            models.Index(fields=("assigned_staff", "status"), name="sup_thr_staff_status_idx"),
            models.Index(fields=("status", "last_message_at"), name="sup_thr_status_lastmsg_idx"),
            models.Index(fields=("created_at",), name="sup_thr_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.subject} [{self.status}]"
