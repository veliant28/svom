from __future__ import annotations

import hashlib

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.autocatalog.models.normalization import collapse_spaces, normalize_name


class CarModification(models.Model):
    make = models.ForeignKey(
        "autocatalog.CarMake",
        on_delete=models.CASCADE,
        related_name="modifications",
        verbose_name=_("Марка"),
    )
    model = models.ForeignKey(
        "autocatalog.CarModel",
        on_delete=models.CASCADE,
        related_name="modifications",
        verbose_name=_("Модель"),
    )
    start_date_at = models.DateField(_("Дата начала"), blank=True, null=True)
    year = models.PositiveSmallIntegerField(_("Год"), blank=True, null=True, db_index=True)
    modification = models.CharField(_("Модификация"), max_length=255, blank=True, default="")
    capacity = models.CharField(_("Объем"), max_length=32, blank=True, default="")
    engine = models.CharField(_("Двигатель"), max_length=512, blank=True, default="")
    hp_from = models.PositiveSmallIntegerField(_("Мощность HP"), blank=True, null=True)
    kw_from = models.PositiveSmallIntegerField(_("Мощность KW"), blank=True, null=True)
    dedupe_key = models.CharField(max_length=160, unique=True, editable=False)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)

    class Meta:
        ordering = ("-year", "make__name", "model__name", "modification")
        verbose_name = _("Авто в каталоге")
        verbose_name_plural = _("Автокаталог")

    @classmethod
    def build_dedupe_key(
        cls,
        *,
        make_id: int,
        model_id: int,
        start_date_at,
        modification: str,
        capacity: str,
        engine: str,
        hp_from: int | None,
        kw_from: int | None,
    ) -> str:
        start_date_key = start_date_at.isoformat() if start_date_at else ""
        payload = "|".join(
            [
                str(make_id),
                str(model_id),
                start_date_key,
                normalize_name(modification),
                normalize_name(capacity),
                normalize_name(engine),
                str(hp_from or ""),
                str(kw_from or ""),
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()  # noqa: S324

    def save(self, *args, **kwargs):
        self.modification = collapse_spaces(self.modification)
        self.capacity = collapse_spaces(self.capacity)
        self.engine = collapse_spaces(self.engine)
        if self.start_date_at and not self.year:
            self.year = self.start_date_at.year
        self.dedupe_key = self.build_dedupe_key(
            make_id=self.make_id,
            model_id=self.model_id,
            start_date_at=self.start_date_at,
            modification=self.modification,
            capacity=self.capacity,
            engine=self.engine,
            hp_from=self.hp_from,
            kw_from=self.kw_from,
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.year or '-'} {self.make.name} {self.model.name} {self.modification}".strip()
