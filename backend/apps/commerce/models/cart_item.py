from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class CartItem(UUIDPrimaryKeyMixin, TimestampedMixin):
    cart = models.ForeignKey(
        "commerce.Cart",
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Корзина"),
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name=_("Товар"),
    )
    quantity = models.PositiveIntegerField(_("Количество"), default=1)
    last_known_unit_price = models.DecimalField(_("Последняя цена за единицу"), max_digits=12, decimal_places=2, default=0)
    last_known_currency = models.CharField(_("Последняя валюта"), max_length=3, default="UAH")
    last_known_availability_status = models.CharField(_("Последний статус доступности"), max_length=32, default="", blank=True)
    last_known_estimated_delivery_days = models.PositiveSmallIntegerField(_("Последний срок доставки, дней"), blank=True, null=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name = _("Позиция корзины")
        verbose_name_plural = _("Позиции корзины")
        constraints = [
            models.UniqueConstraint(
                fields=("cart", "product"),
                name="commerce_cart_item_unique_product",
            )
        ]

    def __str__(self) -> str:
        return f"{self.cart_id}:{self.product_id} x{self.quantity}"
