from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin


class SupportThreadParticipantState(TimestampedMixin, models.Model):
    thread = models.ForeignKey(
        "support.SupportThread",
        on_delete=models.CASCADE,
        related_name="participant_states",
        verbose_name=_("Обращение"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_thread_states",
        verbose_name=_("Пользователь"),
    )
    last_read_message = models.ForeignKey(
        "support.SupportMessage",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="read_states",
        verbose_name=_("Последнее прочитанное сообщение"),
    )
    last_read_at = models.DateTimeField(_("Время чтения"), blank=True, null=True)
    unread_count = models.PositiveIntegerField(_("Непрочитанных"), default=0)

    class Meta:
        verbose_name = _("Состояние участника обращения")
        verbose_name_plural = _("Состояния участников обращений")
        constraints = [
            models.UniqueConstraint(fields=("thread", "user"), name="sup_state_thread_user_uniq"),
        ]
        indexes = [
            models.Index(fields=("user", "unread_count"), name="sup_state_user_unread_idx"),
            models.Index(fields=("thread", "user"), name="sup_state_thread_user_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.user_id}"
