from __future__ import annotations

import re

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ArticleNormalizationRule(UUIDPrimaryKeyMixin, TimestampedMixin):
    RULE_REMOVE_SEPARATORS = "remove_separators"
    RULE_STRIP_PREFIX = "strip_prefix"
    RULE_STRIP_SUFFIX = "strip_suffix"
    RULE_REGEX_REPLACE = "regex_replace"
    RULE_FORCE_UPPERCASE = "force_uppercase"

    RULE_TYPE_CHOICES = (
        (RULE_REMOVE_SEPARATORS, _("Удалить разделители")),
        (RULE_STRIP_PREFIX, _("Удалить префикс")),
        (RULE_STRIP_SUFFIX, _("Удалить суффикс")),
        (RULE_REGEX_REPLACE, _("Замена по регулярному выражению")),
        (RULE_FORCE_UPPERCASE, _("Привести к верхнему регистру")),
    )

    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="article_rules",
        blank=True,
        null=True,
        verbose_name=_("Источник"),
    )
    name = models.CharField(_("Название"), max_length=120)
    rule_type = models.CharField(_("Тип правила"), max_length=32, choices=RULE_TYPE_CHOICES)
    pattern = models.CharField(_("Шаблон"), max_length=180, blank=True)
    replacement = models.CharField(_("Замена"), max_length=180, blank=True)
    is_active = models.BooleanField(_("Активно"), default=True)
    priority = models.IntegerField(_("Приоритет"), default=100)
    notes = models.TextField(_("Примечание"), blank=True)

    class Meta:
        ordering = ("-priority", "name")
        verbose_name = _("Правило нормализации артикула")
        verbose_name_plural = _("Правила нормализации артикулов")
        indexes = [
            models.Index(fields=("source", "is_active", "priority")),
            models.Index(fields=("rule_type", "is_active")),
        ]

    def apply(self, value: str) -> str:
        current = value or ""

        if self.rule_type == self.RULE_REMOVE_SEPARATORS:
            return re.sub(r"[\s\-_./]+", "", current)

        if self.rule_type == self.RULE_STRIP_PREFIX and self.pattern:
            pattern = self.pattern
            if current.upper().startswith(pattern.upper()):
                return current[len(pattern) :]
            return current

        if self.rule_type == self.RULE_STRIP_SUFFIX and self.pattern:
            pattern = self.pattern
            if current.upper().endswith(pattern.upper()):
                return current[: -len(pattern)]
            return current

        if self.rule_type == self.RULE_REGEX_REPLACE and self.pattern:
            try:
                return re.sub(self.pattern, self.replacement or "", current)
            except re.error:
                return current

        if self.rule_type == self.RULE_FORCE_UPPERCASE:
            return current.upper()

        return current

    def __str__(self) -> str:
        return f"{self.name} ({self.rule_type})"
