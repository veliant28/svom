from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin


class User(TimestampedMixin, AbstractUser):
    LANGUAGE_UK = "uk"
    LANGUAGE_RU = "ru"
    LANGUAGE_EN = "en"

    LANGUAGE_CHOICES = (
        (LANGUAGE_UK, _("Украинский")),
        (LANGUAGE_RU, _("Русский")),
        (LANGUAGE_EN, _("Английский")),
    )

    email = models.EmailField(_("Email"), unique=True)
    middle_name = models.CharField(_("Отчество"), max_length=150, blank=True)
    phone = models.CharField(_("Телефон"), max_length=32, blank=True)
    preferred_language = models.CharField(
        _("Предпочитаемый язык"),
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default=LANGUAGE_UK,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ("-date_joined",)
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")

    def __str__(self) -> str:
        return self.get_full_name() or self.email
