from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import re
from typing import Any

from django.core.cache import cache
from django.db import transaction

from apps.commerce.models import NovaPoshtaSenderProfile, Order, OrderNovaPoshtaWaybill, OrderNovaPoshtaWaybillEvent

from .client import NovaPoshtaApiClient
from .constants import WAYBILL_ADDITIONAL_INFO_TEMPLATE, WAYBILL_DESCRIPTION
from .errors import NovaPoshtaBusinessRuleError, NovaPoshtaIntegrationError
from .normalizers import first_data_item
from .payment_rules import resolve_effective_sender_type, resolve_payment_rule
from .sender_service import NovaPoshtaSenderProfileService
from .tracking_service import NovaPoshtaTrackingService
from .waybill_payloads import (
    WaybillUpsertPayload,
    build_waybill_request_payload,
    build_waybill_upsert_payload,
    resolve_service_type,
)

_CREATE_LOCK_TTL_SECONDS = 45
_UPDATE_LOCK_TTL_SECONDS = 30


def _collect_sender_type_hints(profile: NovaPoshtaSenderProfile) -> tuple[str, ...]:
    raw_meta = profile.raw_meta if isinstance(profile.raw_meta, dict) else {}
    candidates = (
        str(raw_meta.get("inferred_sender_type") or ""),
        str(raw_meta.get("counterparty_type") or ""),
        str(raw_meta.get("ownership_form_description") or ""),
        str(raw_meta.get("counterparty_label") or ""),
        str(profile.organization_name or ""),
        str(profile.edrpou or ""),
        str(profile.name or ""),
        str(profile.contact_name or ""),
    )
    return tuple(item.strip() for item in candidates if str(item or "").strip())


class NovaPoshtaWaybillService:
    def __init__(self) -> None:
        self.sender_service = NovaPoshtaSenderProfileService()
        self.tracking_service = NovaPoshtaTrackingService()

    def get_active_waybill(self, *, order: Order) -> OrderNovaPoshtaWaybill | None:
        return (
            order.nova_poshta_waybills
            .select_related("sender_profile")
            .filter(is_deleted=False)
            .order_by("-created_at")
            .first()
        )

    def create_waybill(
        self,
        *,
        order: Order,
        payload: WaybillUpsertPayload,
        actor=None,
    ) -> OrderNovaPoshtaWaybill:
        lock_key = f"nova-poshta:create:{order.id}"
        if not cache.add(lock_key, "1", timeout=_CREATE_LOCK_TTL_SECONDS):
            raise NovaPoshtaBusinessRuleError("Создание ТТН уже выполняется. Подождите несколько секунд и повторите.")

        try:
            existing_waybill = self.get_active_waybill(order=order)
            if existing_waybill and existing_waybill.np_number:
                raise NovaPoshtaBusinessRuleError(
                    f"Для заказа уже создана ТТН: {existing_waybill.np_number}. Откройте ее в режиме редактирования.",
                )

            sender_validation = self.sender_service.validate_profile(profile=payload.sender_profile)
            effective_sender_type = resolve_effective_sender_type(
                sender_type=payload.sender_profile.sender_type,
                hints=_collect_sender_type_hints(payload.sender_profile),
            )

            payment_resolution = resolve_payment_rule(
                sender_type=effective_sender_type,
                requested_afterpayment=payload.afterpayment_amount,
                order_total=Decimal(order.total),
                sender_options=sender_validation.get("options", {}),
                requested_payer_type=payload.payer_type,
                requested_payment_method=payload.payment_method,
            )

            client = NovaPoshtaApiClient(api_token=payload.sender_profile.api_token)
            recipient_counterparty_ref, recipient_contact_ref = self._ensure_recipient_refs(
                client=client,
                payload=payload,
            )
            resolved_payload = replace(
                payload,
                recipient_counterparty_ref=recipient_counterparty_ref,
                recipient_contact_ref=recipient_contact_ref,
            )
            request_payload = build_waybill_request_payload(
                order=order,
                payload=resolved_payload,
                payment_resolution=payment_resolution,
            )
            response = client.create_waybill(method_properties=request_payload)
            data = first_data_item(response.payload)

            np_ref = str(data.get("Ref") or "").strip()
            np_number = str(data.get("IntDocNumber") or "").strip()
            if not np_ref and not np_number:
                raise NovaPoshtaIntegrationError(
                    "Новая Почта не вернула идентификатор ТТН после создания.",
                    context=response.context,
                )

            with transaction.atomic():
                order_total = Decimal(str(order.total or "0"))
                waybill = existing_waybill or OrderNovaPoshtaWaybill(order=order)
                waybill.sender_profile = resolved_payload.sender_profile
                waybill.np_ref = np_ref
                waybill.np_number = np_number
                waybill.payer_type = payment_resolution.payer_type
                waybill.payment_method = payment_resolution.payment_method
                waybill.service_type = resolve_service_type(resolved_payload.delivery_type)
                waybill.cargo_type = resolved_payload.cargo_type or "Parcel"
                waybill.cost = order_total
                waybill.weight = resolved_payload.weight
                waybill.seats_amount = resolved_payload.seats_amount
                waybill.afterpayment_amount = payment_resolution.afterpayment_amount
                waybill.recipient_city_ref = resolved_payload.recipient_city_ref
                waybill.recipient_city_label = resolved_payload.recipient_city_label
                waybill.recipient_address_ref = resolved_payload.recipient_address_ref
                waybill.recipient_address_label = resolved_payload.recipient_address_label
                waybill.recipient_counterparty_ref = resolved_payload.recipient_counterparty_ref
                waybill.recipient_contact_ref = resolved_payload.recipient_contact_ref
                waybill.recipient_name = resolved_payload.recipient_name
                waybill.recipient_phone = resolved_payload.recipient_phone
                waybill.recipient_street_ref = resolved_payload.recipient_street_ref
                waybill.recipient_street_label = resolved_payload.recipient_street_label
                waybill.recipient_house = resolved_payload.recipient_house
                waybill.recipient_apartment = resolved_payload.recipient_apartment
                waybill.description_snapshot = WAYBILL_DESCRIPTION
                waybill.additional_information_snapshot = WAYBILL_ADDITIONAL_INFO_TEMPLATE.format(order_number=order.order_number)
                waybill.raw_request_json = request_payload
                waybill.raw_response_json = response.payload
                waybill.error_codes = response.context.error_codes
                waybill.warning_codes = response.context.warning_codes
                waybill.info_codes = response.context.info_codes
                waybill.print_url_html = self._build_print_url(identifier=np_ref or np_number, sender=resolved_payload.sender_profile, fmt="html")
                waybill.print_url_pdf = self._build_print_url(identifier=np_ref or np_number, sender=resolved_payload.sender_profile, fmt="pdf")
                waybill.can_edit = True
                waybill.last_sync_error = ""
                if not waybill.created_by_id:
                    waybill.created_by = actor
                waybill.updated_by = actor
                waybill.is_deleted = False
                waybill.deleted_at = None
                waybill.save()

                self._create_event(
                    waybill=waybill,
                    event_type=OrderNovaPoshtaWaybillEvent.EVENT_CREATE,
                    message="Waybill created.",
                    payload=request_payload,
                    raw_response=response.payload,
                    actor=actor,
                    errors=response.context.errors,
                    warnings=response.context.warnings,
                    info=response.context.info,
                    error_codes=response.context.error_codes,
                    warning_codes=response.context.warning_codes,
                    info_codes=response.context.info_codes,
                )

            self._safe_sync(waybill=waybill, actor=actor)
            return waybill
        finally:
            cache.delete(lock_key)

    def update_waybill(
        self,
        *,
        waybill: OrderNovaPoshtaWaybill,
        payload: WaybillUpsertPayload,
        actor=None,
    ) -> OrderNovaPoshtaWaybill:
        if waybill.is_deleted:
            raise NovaPoshtaBusinessRuleError("ТТН уже удалена и не может быть обновлена.")
        if not waybill.np_ref:
            raise NovaPoshtaBusinessRuleError("Невозможно обновить ТТН без NP Ref.")

        lock_key = f"nova-poshta:update:{waybill.id}"
        if not cache.add(lock_key, "1", timeout=_UPDATE_LOCK_TTL_SECONDS):
            raise NovaPoshtaBusinessRuleError("Обновление ТТН уже выполняется. Попробуйте еще раз через несколько секунд.")

        try:
            sender_validation = self.sender_service.validate_profile(profile=payload.sender_profile)
            effective_sender_type = resolve_effective_sender_type(
                sender_type=payload.sender_profile.sender_type,
                hints=_collect_sender_type_hints(payload.sender_profile),
            )
            payment_resolution = resolve_payment_rule(
                sender_type=effective_sender_type,
                requested_afterpayment=payload.afterpayment_amount,
                order_total=Decimal(waybill.order.total),
                sender_options=sender_validation.get("options", {}),
                requested_payer_type=payload.payer_type,
                requested_payment_method=payload.payment_method,
            )

            client = NovaPoshtaApiClient(api_token=payload.sender_profile.api_token)
            recipient_counterparty_ref, recipient_contact_ref = self._ensure_recipient_refs(
                client=client,
                payload=payload,
            )
            resolved_payload = replace(
                payload,
                recipient_counterparty_ref=recipient_counterparty_ref,
                recipient_contact_ref=recipient_contact_ref,
            )
            request_payload = build_waybill_request_payload(
                order=waybill.order,
                payload=resolved_payload,
                payment_resolution=payment_resolution,
                np_ref=waybill.np_ref,
            )
            response = client.update_waybill(method_properties=request_payload)

            with transaction.atomic():
                order_total = Decimal(str(waybill.order.total or "0"))
                waybill.sender_profile = resolved_payload.sender_profile
                waybill.payer_type = payment_resolution.payer_type
                waybill.payment_method = payment_resolution.payment_method
                waybill.service_type = resolve_service_type(resolved_payload.delivery_type)
                waybill.cargo_type = resolved_payload.cargo_type or "Parcel"
                waybill.cost = order_total
                waybill.weight = resolved_payload.weight
                waybill.seats_amount = resolved_payload.seats_amount
                waybill.afterpayment_amount = payment_resolution.afterpayment_amount
                waybill.recipient_city_ref = resolved_payload.recipient_city_ref
                waybill.recipient_city_label = resolved_payload.recipient_city_label
                waybill.recipient_address_ref = resolved_payload.recipient_address_ref
                waybill.recipient_address_label = resolved_payload.recipient_address_label
                waybill.recipient_counterparty_ref = resolved_payload.recipient_counterparty_ref
                waybill.recipient_contact_ref = resolved_payload.recipient_contact_ref
                waybill.recipient_name = resolved_payload.recipient_name
                waybill.recipient_phone = resolved_payload.recipient_phone
                waybill.recipient_street_ref = resolved_payload.recipient_street_ref
                waybill.recipient_street_label = resolved_payload.recipient_street_label
                waybill.recipient_house = resolved_payload.recipient_house
                waybill.recipient_apartment = resolved_payload.recipient_apartment
                waybill.description_snapshot = WAYBILL_DESCRIPTION
                waybill.raw_request_json = request_payload
                waybill.raw_response_json = response.payload
                waybill.error_codes = response.context.error_codes
                waybill.warning_codes = response.context.warning_codes
                waybill.info_codes = response.context.info_codes
                waybill.updated_by = actor
                waybill.last_sync_error = ""
                waybill.save()

                self._create_event(
                    waybill=waybill,
                    event_type=OrderNovaPoshtaWaybillEvent.EVENT_UPDATE,
                    message="Waybill updated.",
                    payload=request_payload,
                    raw_response=response.payload,
                    actor=actor,
                    errors=response.context.errors,
                    warnings=response.context.warnings,
                    info=response.context.info,
                    error_codes=response.context.error_codes,
                    warning_codes=response.context.warning_codes,
                    info_codes=response.context.info_codes,
                )

            self._safe_sync(waybill=waybill, actor=actor)
            return waybill
        finally:
            cache.delete(lock_key)

    def delete_waybill(self, *, waybill: OrderNovaPoshtaWaybill, actor=None) -> OrderNovaPoshtaWaybill:
        if waybill.is_deleted:
            return waybill

        client = NovaPoshtaApiClient(api_token=waybill.sender_profile.api_token)
        response = client.delete_waybill(np_ref=waybill.np_ref)

        with transaction.atomic():
            waybill.mark_deleted()
            waybill.can_edit = False
            waybill.updated_by = actor
            waybill.raw_response_json = response.payload
            waybill.error_codes = response.context.error_codes
            waybill.warning_codes = response.context.warning_codes
            waybill.info_codes = response.context.info_codes
            waybill.save(update_fields=(
                "is_deleted",
                "deleted_at",
                "can_edit",
                "updated_by",
                "raw_response_json",
                "error_codes",
                "warning_codes",
                "info_codes",
                "updated_at",
            ))

            self._create_event(
                waybill=waybill,
                event_type=OrderNovaPoshtaWaybillEvent.EVENT_DELETE,
                message="Waybill deleted.",
                payload={"np_ref": waybill.np_ref},
                raw_response=response.payload,
                actor=actor,
                errors=response.context.errors,
                warnings=response.context.warnings,
                info=response.context.info,
                error_codes=response.context.error_codes,
                warning_codes=response.context.warning_codes,
                info_codes=response.context.info_codes,
            )

        return waybill

    def sync_waybill(self, *, waybill: OrderNovaPoshtaWaybill, actor=None) -> OrderNovaPoshtaWaybill:
        self.tracking_service.sync_waybill_status(waybill=waybill, actor=actor)
        waybill.refresh_from_db()
        return waybill

    def build_upsert_payload(self, *, sender_profile: NovaPoshtaSenderProfile, data: dict[str, Any]) -> WaybillUpsertPayload:
        return build_waybill_upsert_payload(sender_profile=sender_profile, data=data)

    @staticmethod
    def _build_print_url(*, identifier: str, sender: NovaPoshtaSenderProfile, fmt: str) -> str:
        return f"https://my.novaposhta.ua/orders/printDocument/orders[]/{identifier}/type/{fmt}/apiKey/{sender.api_token}"

    def _safe_sync(self, *, waybill: OrderNovaPoshtaWaybill, actor=None) -> None:
        try:
            self.tracking_service.sync_waybill_status(waybill=waybill, actor=actor)
        except Exception as exc:
            waybill.last_sync_error = str(exc)
            waybill.save(update_fields=("last_sync_error", "updated_at"))
            self._create_event(
                waybill=waybill,
                event_type=OrderNovaPoshtaWaybillEvent.EVENT_ERROR,
                message=f"Status sync failed: {exc}",
                payload={},
                raw_response={},
                actor=actor,
                errors=[str(exc)],
                warnings=[],
                info=[],
                error_codes=[],
                warning_codes=[],
                info_codes=[],
            )

    def _ensure_recipient_refs(
        self,
        *,
        client: NovaPoshtaApiClient,
        payload: WaybillUpsertPayload,
    ) -> tuple[str, str]:
        counterparty_ref = str(payload.recipient_counterparty_ref or "").strip()
        contact_ref = str(payload.recipient_contact_ref or "").strip()
        if counterparty_ref and contact_ref:
            return counterparty_ref, contact_ref

        if counterparty_ref and not contact_ref:
            contacts_response = client.get_counterparty_contact_persons(counterparty_ref=counterparty_ref)
            contacts = contacts_response.payload.get("data")
            if isinstance(contacts, list):
                for row in contacts:
                    if not isinstance(row, dict):
                        continue
                    resolved_ref = str(row.get("Ref") or "").strip()
                    if resolved_ref:
                        contact_ref = resolved_ref
                        break
            if contact_ref:
                return counterparty_ref, contact_ref

        first_name, middle_name, last_name = self._split_recipient_name(payload.recipient_name)
        normalized_phone = self._normalize_np_phone(payload.recipient_phone)
        if not normalized_phone:
            raise NovaPoshtaBusinessRuleError("Телефон получателя обязателен для создания контрагента Новой Почты.")

        create_response = client.create_recipient_counterparty(
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            phone=normalized_phone,
        )
        created = first_data_item(create_response.payload)
        created_ref = str(created.get("Ref") or "").strip()
        counterparty_ref = str(created.get("Counterparty") or "").strip() or created_ref or counterparty_ref
        created_contact_person = created.get("ContactPerson")
        if isinstance(created_contact_person, dict):
            nested_data = created_contact_person.get("data")
            if isinstance(nested_data, list):
                for row in nested_data:
                    if not isinstance(row, dict):
                        continue
                    nested_ref = str(row.get("Ref") or "").strip()
                    if nested_ref:
                        contact_ref = nested_ref
                        break
        if not contact_ref:
            contact_ref = created_ref

        if counterparty_ref and not contact_ref:
            contacts_response = client.get_counterparty_contact_persons(counterparty_ref=counterparty_ref)
            contacts = contacts_response.payload.get("data")
            if isinstance(contacts, list):
                for row in contacts:
                    if not isinstance(row, dict):
                        continue
                    resolved_ref = str(row.get("Ref") or "").strip()
                    if resolved_ref:
                        contact_ref = resolved_ref
                        break

        if not counterparty_ref or not contact_ref:
            raise NovaPoshtaBusinessRuleError("Не удалось определить контакт получателя. Проверьте ФИО и телефон получателя.")
        return counterparty_ref, contact_ref

    @staticmethod
    def _normalize_np_phone(phone: str) -> str:
        digits = re.sub(r"\D+", "", str(phone or ""))
        if len(digits) == 10 and digits.startswith("0"):
            return f"38{digits}"
        if len(digits) == 12 and digits.startswith("380"):
            return digits
        return digits

    @staticmethod
    def _split_recipient_name(value: str) -> tuple[str, str, str]:
        parts = [part for part in str(value or "").strip().split() if part]
        if len(parts) >= 3:
            return parts[1], parts[2], parts[0]
        if len(parts) == 2:
            return parts[1], parts[1], parts[0]
        if len(parts) == 1:
            return parts[0], parts[0], parts[0]
        return "Отримувач", "Отримувач", "Отримувач"

    @staticmethod
    def _create_event(
        *,
        waybill: OrderNovaPoshtaWaybill,
        event_type: str,
        message: str,
        payload: dict[str, Any],
        raw_response: dict[str, Any],
        actor,
        errors: list[str],
        warnings: list[str],
        info: list[str],
        error_codes: list[str],
        warning_codes: list[str],
        info_codes: list[str],
    ) -> OrderNovaPoshtaWaybillEvent:
        return OrderNovaPoshtaWaybillEvent.objects.create(
            waybill=waybill,
            order=waybill.order,
            event_type=event_type,
            message=message[:500],
            status_code=waybill.status_code,
            status_text=waybill.status_text,
            payload=payload,
            raw_response=raw_response,
            errors=errors,
            warnings=warnings,
            info=info,
            error_codes=error_codes,
            warning_codes=warning_codes,
            info_codes=info_codes,
            created_by=actor,
        )
