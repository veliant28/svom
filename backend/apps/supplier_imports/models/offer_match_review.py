from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class OfferMatchReview(UUIDPrimaryKeyMixin, TimestampedMixin):
    ACTION_AUTO_ATTEMPT = "auto_attempt"
    ACTION_RETRY_MATCHING = "retry_matching"
    ACTION_MANUAL_CONFIRM = "manual_confirm"
    ACTION_IGNORE = "ignore"
    ACTION_BULK_AUTO_MATCH = "bulk_auto_match"
    ACTION_BULK_IGNORE = "bulk_ignore"

    ACTION_CHOICES = (
        (ACTION_AUTO_ATTEMPT, _("Автоматическая попытка")),
        (ACTION_RETRY_MATCHING, _("Повторный матчинг")),
        (ACTION_MANUAL_CONFIRM, _("Ручное подтверждение")),
        (ACTION_IGNORE, _("Игнорировать")),
        (ACTION_BULK_AUTO_MATCH, _("Массовый автомэтчинг")),
        (ACTION_BULK_IGNORE, _("Массовое игнорирование")),
    )

    raw_offer = models.ForeignKey(
        "supplier_imports.SupplierRawOffer",
        on_delete=models.CASCADE,
        related_name="match_reviews",
        verbose_name=_("Сырой оффер"),
    )
    action = models.CharField(_("Действие"), max_length=32, choices=ACTION_CHOICES)
    status_before = models.CharField(_("Статус до"), max_length=32, blank=True)
    status_after = models.CharField(_("Статус после"), max_length=32, blank=True)
    reason = models.CharField(_("Причина"), max_length=64, blank=True)
    candidate_product_ids = models.JSONField(_("Кандидаты товаров"), default=list, blank=True)
    selected_product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        related_name="offer_match_reviews",
        blank=True,
        null=True,
        verbose_name=_("Выбранный товар"),
    )
    performed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="offer_match_reviews",
        blank=True,
        null=True,
        verbose_name=_("Исполнитель"),
    )
    note = models.TextField(_("Примечание"), blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Проверка сопоставления оффера")
        verbose_name_plural = _("Проверки сопоставления офферов")

    def __str__(self) -> str:
        return f"{self.raw_offer_id}:{self.action}:{self.status_after or '-'}"
