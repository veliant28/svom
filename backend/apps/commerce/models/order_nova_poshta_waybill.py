from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class OrderNovaPoshtaWaybill(UUIDPrimaryKeyMixin, TimestampedMixin):
    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="nova_poshta_waybills",
        verbose_name=_("Заказ"),
    )
    sender_profile = models.ForeignKey(
        "commerce.NovaPoshtaSenderProfile",
        on_delete=models.PROTECT,
        related_name="waybills",
        verbose_name=_("Профиль отправителя"),
    )

    np_ref = models.CharField(_("Ref ТТН"), max_length=36, blank=True)
    np_number = models.CharField(_("Номер ТТН"), max_length=64, blank=True)

    status_code = models.CharField(_("Код статуса"), max_length=64, blank=True)
    status_text = models.CharField(_("Текст статуса"), max_length=255, blank=True)
    status_synced_at = models.DateTimeField(_("Статус синхронизирован"), blank=True, null=True)

    payer_type = models.CharField(_("Тип плательщика"), max_length=32, blank=True)
    payment_method = models.CharField(_("Метод оплаты"), max_length=32, blank=True)
    service_type = models.CharField(_("Тип доставки"), max_length=32, blank=True)
    cargo_type = models.CharField(_("Тип груза"), max_length=32, default="Cargo")

    cost = models.DecimalField(_("Оценочная стоимость"), max_digits=12, decimal_places=2, default=0)
    weight = models.DecimalField(_("Вес"), max_digits=10, decimal_places=3, default=0)
    seats_amount = models.PositiveIntegerField(_("Количество мест"), default=1)
    afterpayment_amount = models.DecimalField(
        _("Сумма контроля оплаты"),
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    recipient_city_ref = models.CharField(_("Ref города получателя"), max_length=36, blank=True)
    recipient_city_label = models.CharField(_("Город получателя"), max_length=255, blank=True)
    recipient_address_ref = models.CharField(_("Ref адреса/отделения"), max_length=36, blank=True)
    recipient_address_label = models.CharField(_("Адрес/отделение"), max_length=255, blank=True)
    recipient_counterparty_ref = models.CharField(_("Ref контрагента получателя"), max_length=36, blank=True)
    recipient_contact_ref = models.CharField(_("Ref контактного лица получателя"), max_length=36, blank=True)
    recipient_name = models.CharField(_("Получатель"), max_length=255, blank=True)
    recipient_phone = models.CharField(_("Телефон получателя"), max_length=32, blank=True)
    recipient_street_ref = models.CharField(_("Ref улицы получателя"), max_length=36, blank=True)
    recipient_street_label = models.CharField(_("Улица получателя"), max_length=255, blank=True)
    recipient_house = models.CharField(_("Дом"), max_length=32, blank=True)
    recipient_apartment = models.CharField(_("Квартира"), max_length=32, blank=True)

    description_snapshot = models.CharField(_("Описание отправления"), max_length=255, default="")
    additional_information_snapshot = models.CharField(_("Дополнительная информация"), max_length=255, default="")

    raw_request_json = models.JSONField(_("Сырой request JSON"), default=dict, blank=True)
    raw_response_json = models.JSONField(_("Сырой response JSON"), default=dict, blank=True)
    raw_last_tracking_json = models.JSONField(_("Сырой tracking JSON"), default=dict, blank=True)

    error_codes = models.JSONField(_("Коды ошибок НП"), default=list, blank=True)
    warning_codes = models.JSONField(_("Коды предупреждений НП"), default=list, blank=True)
    info_codes = models.JSONField(_("Информационные коды НП"), default=list, blank=True)

    print_url_html = models.URLField(_("URL печати HTML"), max_length=1024, blank=True)
    print_url_pdf = models.URLField(_("URL печати PDF"), max_length=1024, blank=True)

    can_edit = models.BooleanField(_("Можно редактировать"), default=True)
    last_sync_error = models.TextField(_("Последняя ошибка синхронизации"), blank=True)

    is_deleted = models.BooleanField(_("Удалена"), default=False)
    deleted_at = models.DateTimeField(_("Удалена в"), blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_nova_poshta_waybills",
        blank=True,
        null=True,
        verbose_name=_("Создал"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_nova_poshta_waybills",
        blank=True,
        null=True,
        verbose_name=_("Обновил"),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("ТТН Новой Почты")
        verbose_name_plural = _("ТТН Новой Почты")
        indexes = [
            models.Index(fields=("order", "is_deleted"), name="com_np_wb_order_del_idx"),
            models.Index(fields=("np_number",), name="commerce_np_waybill_number_idx"),
            models.Index(fields=("status_code",), name="commerce_np_waybill_status_idx"),
        ]

    def __str__(self) -> str:
        return self.np_number or str(self.id)

    def mark_deleted(self) -> None:
        self.is_deleted = True
        self.deleted_at = timezone.now()


class OrderNovaPoshtaWaybillEvent(UUIDPrimaryKeyMixin, TimestampedMixin):
    EVENT_CREATE = "create"
    EVENT_UPDATE = "update"
    EVENT_DELETE = "delete"
    EVENT_SYNC = "sync"
    EVENT_ERROR = "error"
    EVENT_PRINT = "print"
    EVENT_VALIDATE = "validate_sender"

    EVENT_TYPE_CHOICES = (
        (EVENT_CREATE, _("Создание")),
        (EVENT_UPDATE, _("Обновление")),
        (EVENT_DELETE, _("Удаление")),
        (EVENT_SYNC, _("Синхронизация статуса")),
        (EVENT_ERROR, _("Ошибка")),
        (EVENT_PRINT, _("Печать")),
        (EVENT_VALIDATE, _("Валидация отправителя")),
    )

    waybill = models.ForeignKey(
        "commerce.OrderNovaPoshtaWaybill",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("ТТН"),
    )
    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="nova_poshta_waybill_events",
        verbose_name=_("Заказ"),
    )
    event_type = models.CharField(_("Тип события"), max_length=32, choices=EVENT_TYPE_CHOICES)
    message = models.CharField(_("Сообщение"), max_length=500, blank=True)
    status_code = models.CharField(_("Код статуса"), max_length=64, blank=True)
    status_text = models.CharField(_("Текст статуса"), max_length=255, blank=True)

    payload = models.JSONField(_("Payload"), default=dict, blank=True)
    raw_response = models.JSONField(_("Сырой ответ"), default=dict, blank=True)
    errors = models.JSONField(_("Ошибки"), default=list, blank=True)
    warnings = models.JSONField(_("Предупреждения"), default=list, blank=True)
    info = models.JSONField(_("Инфо"), default=list, blank=True)
    error_codes = models.JSONField(_("Коды ошибок"), default=list, blank=True)
    warning_codes = models.JSONField(_("Коды предупреждений"), default=list, blank=True)
    info_codes = models.JSONField(_("Коды инфо"), default=list, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="nova_poshta_waybill_events",
        blank=True,
        null=True,
        verbose_name=_("Создал"),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Событие ТТН Новой Почты")
        verbose_name_plural = _("События ТТН Новой Почты")
        indexes = [
            models.Index(fields=("order", "event_type"), name="com_np_wbe_order_type_idx"),
            models.Index(fields=("waybill", "-created_at"), name="com_np_wbe_wb_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.order_id}"
