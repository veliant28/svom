from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class WishlistItem(UUIDPrimaryKeyMixin, TimestampedMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
        verbose_name=_("Пользователь"),
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="wishlist_items",
        verbose_name=_("Товар"),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Элемент избранного")
        verbose_name_plural = _("Избранное")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "product"),
                name="commerce_wishlist_unique_user_product",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.product_id}"
