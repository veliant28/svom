from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class Cart(UUIDPrimaryKeyMixin, TimestampedMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        verbose_name=_("Пользователь"),
    )
    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = _("Корзина")
        verbose_name_plural = _("Корзины")

    def __str__(self) -> str:
        return f"Корзина {self.id}"
