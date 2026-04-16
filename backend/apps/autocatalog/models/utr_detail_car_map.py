from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class UtrDetailCarMap(models.Model):
    utr_detail_id = models.CharField(_("UTR detail ID"), max_length=64)
    car_modification = models.ForeignKey(
        "autocatalog.CarModification",
        on_delete=models.CASCADE,
        related_name="utr_detail_maps",
        verbose_name=_("Авто"),
    )
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)

    class Meta:
        ordering = ("utr_detail_id", "car_modification_id")
        verbose_name = _("Связь UTR детали с авто")
        verbose_name_plural = _("Связи UTR деталей с авто")
        constraints = [
            models.UniqueConstraint(
                fields=("utr_detail_id", "car_modification"),
                name="autocatalog_unique_utr_detail_car_modification",
            ),
        ]
        indexes = [
            models.Index(fields=("utr_detail_id",), name="autocatalog_utr_detail_id_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.utr_detail_id} -> {self.car_modification_id}"
