from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class NovaPoshtaSenderProfile(UUIDPrimaryKeyMixin, TimestampedMixin):
    TYPE_PRIVATE_PERSON = "private_person"
    TYPE_FOP = "fop"
    TYPE_BUSINESS = "business"

    SENDER_TYPE_CHOICES = (
        (TYPE_PRIVATE_PERSON, _("Физлицо")),
        (TYPE_FOP, _("ФОП")),
        (TYPE_BUSINESS, _("Организация")),
    )

    name = models.CharField(_("Название профиля"), max_length=255)
    sender_type = models.CharField(_("Тип отправителя"), max_length=32, choices=SENDER_TYPE_CHOICES)
    api_token = models.CharField(_("API токен Новой Почты"), max_length=255)

    counterparty_ref = models.CharField(_("Ref контрагента"), max_length=36)
    contact_ref = models.CharField(_("Ref контактного лица"), max_length=36)
    address_ref = models.CharField(_("Ref адреса отправителя"), max_length=36)
    city_ref = models.CharField(_("Ref города отправителя"), max_length=36)

    phone = models.CharField(_("Телефон отправителя"), max_length=32)
    contact_name = models.CharField(_("Контактное лицо"), max_length=255, blank=True)
    organization_name = models.CharField(_("Название организации"), max_length=255, blank=True)
    edrpou = models.CharField(_("ЕДРПОУ"), max_length=32, blank=True)

    is_active = models.BooleanField(_("Активен"), default=True)
    is_default = models.BooleanField(_("По умолчанию"), default=False)

    last_validated_at = models.DateTimeField(_("Последняя валидация"), blank=True, null=True)
    last_validation_ok = models.BooleanField(_("Валидация успешна"), default=False)
    last_validation_message = models.CharField(_("Комментарий валидации"), max_length=500, blank=True)
    last_validation_payload = models.JSONField(_("Результат последней валидации"), default=dict, blank=True)

    raw_meta = models.JSONField(_("Сырые meta/ref-данные НП"), default=dict, blank=True)

    class Meta:
        ordering = ("-is_default", "name")
        verbose_name = _("Профиль отправителя Новой Почты")
        verbose_name_plural = _("Профили отправителей Новой Почты")
        indexes = [
            models.Index(fields=("is_active", "is_default"), name="com_np_sender_act_def_idx"),
            models.Index(fields=("sender_type",), name="commerce_np_sender_type_idx"),
        ]

    def __str__(self) -> str:
        return self.name
