from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import UUIDPrimaryKeyMixin


class SupportMessage(UUIDPrimaryKeyMixin, models.Model):
    SIDE_CUSTOMER = "customer"
    SIDE_STAFF = "staff"
    SIDE_SYSTEM = "system"
    AUTHOR_SIDE_CHOICES = (
        (SIDE_CUSTOMER, _("Клиент")),
        (SIDE_STAFF, _("Сотрудник")),
        (SIDE_SYSTEM, _("Система")),
    )

    KIND_MESSAGE = "message"
    KIND_SYSTEM_EVENT = "system_event"
    KIND_CHOICES = (
        (KIND_MESSAGE, _("Сообщение")),
        (KIND_SYSTEM_EVENT, _("Системное событие")),
    )

    thread = models.ForeignKey(
        "support.SupportThread",
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Обращение"),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="support_messages",
        verbose_name=_("Автор"),
    )
    author_side = models.CharField(_("Сторона автора"), max_length=16, choices=AUTHOR_SIDE_CHOICES)
    kind = models.CharField(_("Тип записи"), max_length=24, choices=KIND_CHOICES, default=KIND_MESSAGE)
    body = models.TextField(_("Текст"), blank=True)
    event_code = models.CharField(_("Код события"), max_length=64, blank=True, default="")
    event_payload = models.JSONField(_("Данные события"), blank=True, default=dict)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    edited_at = models.DateTimeField(_("Изменено"), blank=True, null=True)

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = _("Сообщение поддержки")
        verbose_name_plural = _("Сообщения поддержки")
        indexes = [
            models.Index(fields=("thread", "created_at"), name="support_msg_thread_created_idx"),
            models.Index(fields=("author_side", "created_at"), name="support_msg_side_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.author_side}:{self.kind}"
