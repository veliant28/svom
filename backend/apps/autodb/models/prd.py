from django.utils.translation import gettext_lazy as _

from .product_group import AutoDbProductGroup


class AutoDbPrd(AutoDbProductGroup):
    class Meta:
        proxy = True
        verbose_name = _("Группа товаров Auto_DB_Pro (PRD)")
        verbose_name_plural = _("Группы товаров Auto_DB_Pro (PRD)")
