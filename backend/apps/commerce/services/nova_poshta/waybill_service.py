from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
import re
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.commerce.models import NovaPoshtaSenderProfile, Order, OrderNovaPoshtaWaybill, OrderNovaPoshtaWaybillEvent

from .client import NovaPoshtaApiClient
from .constants import WAYBILL_ADDITIONAL_INFO_TEMPLATE, WAYBILL_DESCRIPTION
from .errors import NovaPoshtaBusinessRuleError, NovaPoshtaIntegrationError
from .normalizers import first_data_item
from .payment_rules import resolve_effective_sender_type, resolve_payment_rule
from .sender_service import NovaPoshtaSenderProfileService
from .tracking_service import NovaPoshtaTrackingService

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


@dataclass(frozen=True)
class WaybillUpsertPayload:
    sender_profile: NovaPoshtaSenderProfile
    delivery_type: str
    cargo_type: str
    description: str
    recipient_city_ref: str
    recipient_city_label: str
    recipient_address_ref: str
    recipient_address_label: str
    recipient_counterparty_ref: str
    recipient_contact_ref: str
    recipient_name: str
    recipient_phone: str
    seats_amount: int
    weight: Decimal
    cost: Decimal
    afterpayment_amount: Decimal | None
    payer_type: str = ""
    payment_method: str = ""
    recipient_street_ref: str = ""
    recipient_street_label: str = ""
    recipient_house: str = ""
    recipient_apartment: str = ""
    volume_general: Decimal | None = None
    pack_ref: str = ""
    pack_refs: tuple[str, ...] = ()
    volumetric_width: Decimal | None = None
    volumetric_length: Decimal | None = None
    volumetric_height: Decimal | None = None
    saturday_delivery: bool = False
    local_express: bool = False
    preferred_delivery_date: str = ""
    time_interval: str = ""
    info_reg_client_barcodes: str = ""
    accompanying_documents: str = ""
    red_box_barcode: str = ""
    number_of_floors_lifting: str = ""
    number_of_floors_descent: str = ""
    forwarding_count: str = ""
    delivery_by_hand: bool = False
    delivery_by_hand_recipients: str = ""
    special_cargo: bool = False
    options_seat: tuple["WaybillSeatOption", ...] = ()


@dataclass(frozen=True)
class WaybillSeatOption:
    description: str = ""
    cost: Decimal = Decimal("0")
    weight: Decimal = Decimal("0.001")
    pack_ref: str = ""
    volumetric_width: Decimal | None = None
    volumetric_length: Decimal | None = None
    volumetric_height: Decimal | None = None
    volumetric_volume: Decimal | None = None
    cargo_type: str = "Parcel"
    special_cargo: bool = False


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
            request_payload = self._build_request_payload(
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
                waybill.service_type = self._resolve_service_type(resolved_payload.delivery_type)
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
            request_payload = self._build_request_payload(
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
                waybill.service_type = self._resolve_service_type(resolved_payload.delivery_type)
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
        raw_options_seat = data.get("options_seat") or []
        parsed_options_seat: list[WaybillSeatOption] = []
        if isinstance(raw_options_seat, list):
            for raw_item in raw_options_seat:
                if not isinstance(raw_item, dict):
                    continue
                pack_ref = str(raw_item.get("pack_ref") or "").strip()
                if not pack_ref:
                    refs = raw_item.get("pack_refs") or []
                    if isinstance(refs, list):
                        pack_ref = next((str(item or "").strip() for item in refs if str(item or "").strip()), "")
                parsed_options_seat.append(
                    WaybillSeatOption(
                        description=str(raw_item.get("description") or "").strip(),
                        cost=Decimal(str(raw_item.get("cost") or "0")),
                        weight=max(Decimal("0.001"), Decimal(str(raw_item.get("weight") or "0.001"))),
                        pack_ref=pack_ref,
                        volumetric_width=(
                            Decimal(str(raw_item.get("volumetric_width")))
                            if raw_item.get("volumetric_width") is not None else None
                        ),
                        volumetric_length=(
                            Decimal(str(raw_item.get("volumetric_length")))
                            if raw_item.get("volumetric_length") is not None else None
                        ),
                        volumetric_height=(
                            Decimal(str(raw_item.get("volumetric_height")))
                            if raw_item.get("volumetric_height") is not None else None
                        ),
                        volumetric_volume=(
                            Decimal(str(raw_item.get("volumetric_volume")))
                            if raw_item.get("volumetric_volume") is not None else None
                        ),
                        cargo_type=str(raw_item.get("cargo_type") or "Parcel").strip() or "Parcel",
                        special_cargo=bool(raw_item.get("special_cargo")),
                    )
                )

        seats_amount = int(data.get("seats_amount") or 1)
        weight = Decimal(str(data.get("weight") or "0.1"))
        cost = Decimal(str(data.get("cost") or "0"))
        description = str(data.get("description") or "").strip() or WAYBILL_DESCRIPTION
        pack_refs = tuple(
            str(item or "").strip()
            for item in (data.get("pack_refs") or [])
            if str(item or "").strip()
        )
        if parsed_options_seat:
            seats_amount = len(parsed_options_seat)
            weight = sum((item.weight for item in parsed_options_seat), Decimal("0"))
            if weight <= 0:
                weight = Decimal("0.001")
            cost = sum((item.cost for item in parsed_options_seat), Decimal("0"))
            description = next(
                (item.description for item in parsed_options_seat if item.description),
                description,
            )
            pack_refs = tuple(item.pack_ref for item in parsed_options_seat if item.pack_ref)

        return WaybillUpsertPayload(
            sender_profile=sender_profile,
            delivery_type=str(data.get("delivery_type") or "warehouse").strip(),
            cargo_type=str(data.get("cargo_type") or "Parcel").strip() or "Parcel",
            description=description,
            recipient_city_ref=str(data.get("recipient_city_ref") or "").strip(),
            recipient_city_label=str(data.get("recipient_city_label") or "").strip(),
            recipient_address_ref=str(data.get("recipient_address_ref") or "").strip(),
            recipient_address_label=str(data.get("recipient_address_label") or "").strip(),
            recipient_counterparty_ref=str(data.get("recipient_counterparty_ref") or "").strip(),
            recipient_contact_ref=str(data.get("recipient_contact_ref") or "").strip(),
            recipient_name=str(data.get("recipient_name") or "").strip(),
            recipient_phone=str(data.get("recipient_phone") or "").strip(),
            seats_amount=seats_amount,
            weight=weight,
            cost=cost,
            afterpayment_amount=Decimal(str(data.get("afterpayment_amount"))) if data.get("afterpayment_amount") is not None else None,
            payer_type=str(data.get("payer_type") or "").strip(),
            payment_method=str(data.get("payment_method") or "").strip(),
            recipient_street_ref=str(data.get("recipient_street_ref") or "").strip(),
            recipient_street_label=str(data.get("recipient_street_label") or "").strip(),
            recipient_house=str(data.get("recipient_house") or "").strip(),
            recipient_apartment=str(data.get("recipient_apartment") or "").strip(),
            volume_general=Decimal(str(data.get("volume_general"))) if data.get("volume_general") is not None else None,
            pack_ref=str(data.get("pack_ref") or "").strip(),
            pack_refs=pack_refs,
            volumetric_width=Decimal(str(data.get("volumetric_width"))) if data.get("volumetric_width") is not None else None,
            volumetric_length=Decimal(str(data.get("volumetric_length"))) if data.get("volumetric_length") is not None else None,
            volumetric_height=Decimal(str(data.get("volumetric_height"))) if data.get("volumetric_height") is not None else None,
            saturday_delivery=bool(data.get("saturday_delivery")),
            local_express=bool(data.get("local_express")),
            preferred_delivery_date=str(data.get("preferred_delivery_date") or "").strip(),
            time_interval=str(data.get("time_interval") or "").strip(),
            info_reg_client_barcodes=str(data.get("info_reg_client_barcodes") or "").strip(),
            accompanying_documents=str(data.get("accompanying_documents") or "").strip(),
            red_box_barcode=str(data.get("red_box_barcode") or "").strip().upper(),
            number_of_floors_lifting=str(data.get("number_of_floors_lifting") or "").strip(),
            number_of_floors_descent=str(data.get("number_of_floors_descent") or "").strip(),
            forwarding_count=str(data.get("forwarding_count") or "").strip(),
            delivery_by_hand=bool(data.get("delivery_by_hand")),
            delivery_by_hand_recipients=str(data.get("delivery_by_hand_recipients") or "").strip(),
            special_cargo=bool(data.get("special_cargo")),
            options_seat=tuple(parsed_options_seat),
        )

    def _build_request_payload(
        self,
        *,
        order: Order,
        payload: WaybillUpsertPayload,
        payment_resolution,
        np_ref: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(tz=timezone.get_current_timezone())
        order_total = Decimal(str(order.total or "0"))
        declared_cost = order_total if order_total > 0 else Decimal("1")
        method_properties: dict[str, Any] = {
            "PayerType": payment_resolution.payer_type,
            "PaymentMethod": payment_resolution.payment_method,
            "DateTime": now.strftime("%d.%m.%Y"),
            "CargoType": payload.cargo_type or "Parcel",
            "Weight": str(payload.weight),
            "ServiceType": self._resolve_service_type(payload.delivery_type),
            "SeatsAmount": str(max(1, payload.seats_amount)),
            "Description": WAYBILL_DESCRIPTION,
            "Cost": self._format_decimal(declared_cost),
            "CitySender": payload.sender_profile.city_ref,
            "Sender": payload.sender_profile.counterparty_ref,
            "SenderAddress": payload.sender_profile.address_ref,
            "ContactSender": payload.sender_profile.contact_ref,
            "SendersPhone": payload.sender_profile.phone,
            "CityRecipient": payload.recipient_city_ref,
            "RecipientsPhone": payload.recipient_phone,
            "RecipientName": payload.recipient_name,
            "AdditionalInformation": WAYBILL_ADDITIONAL_INFO_TEMPLATE.format(order_number=order.order_number),
            # Keep client internal number deterministic for every TTN.
            "InfoRegClientBarcodes": order.order_number,
        }

        if payload.recipient_counterparty_ref:
            method_properties["Recipient"] = payload.recipient_counterparty_ref
        if payload.recipient_contact_ref:
            method_properties["ContactRecipient"] = payload.recipient_contact_ref

        if np_ref:
            method_properties["Ref"] = np_ref

        if payment_resolution.afterpayment_amount is not None and payment_resolution.afterpayment_amount > 0:
            method_properties["AfterpaymentOnGoodsCost"] = self._format_decimal(payment_resolution.afterpayment_amount)

        method_properties["SaturdayDelivery"] = "1" if payload.saturday_delivery else "0"
        method_properties["LocalExpress"] = "1" if payload.local_express else "0"
        method_properties["DeliveryByHand"] = "1" if payload.delivery_by_hand else "0"
        if payload.special_cargo:
            method_properties["specialCargo"] = "1"

        if payload.preferred_delivery_date:
            method_properties["PreferredDeliveryDate"] = payload.preferred_delivery_date
        if payload.time_interval:
            method_properties["TimeInterval"] = payload.time_interval
        if payload.accompanying_documents:
            method_properties["AccompanyingDocuments"] = payload.accompanying_documents
        if payload.red_box_barcode:
            method_properties["RedBoxBarcode"] = payload.red_box_barcode
        if payload.number_of_floors_lifting:
            method_properties["NumberOfFloorsLifting"] = payload.number_of_floors_lifting
        if payload.number_of_floors_descent:
            method_properties["NumberOfFloorsDescent"] = payload.number_of_floors_descent
        if payload.forwarding_count:
            method_properties["ForwardingCount"] = payload.forwarding_count

        if payload.delivery_by_hand:
            recipients = self._resolve_delivery_by_hand_recipients(
                recipient_name=payload.recipient_name,
                raw_recipients=payload.delivery_by_hand_recipients,
            )
            if recipients:
                method_properties["DeliveryByHandRecipients"] = recipients

        resolved_pack_refs = [ref for ref in payload.pack_refs if ref]
        if not resolved_pack_refs and payload.pack_ref:
            resolved_pack_refs = [payload.pack_ref]
        if payload.options_seat:
            seats_payload: list[dict[str, Any]] = []
            seat_cost_total = Decimal("0")
            seat_weight_total = Decimal("0")
            for index, seat in enumerate(payload.options_seat):
                seat_weight = max(Decimal("0.001"), seat.weight)
                seat_cost = max(Decimal("0"), seat.cost)
                seat_weight_total += seat_weight
                seat_cost_total += seat_cost

                seat_item: dict[str, Any] = {
                    "weight": self._format_decimal(seat_weight),
                }
                effective_width = seat.volumetric_width if seat.volumetric_width is not None else payload.volumetric_width
                effective_length = seat.volumetric_length if seat.volumetric_length is not None else payload.volumetric_length
                effective_height = seat.volumetric_height if seat.volumetric_height is not None else payload.volumetric_height
                effective_volume = seat.volumetric_volume if seat.volumetric_volume is not None else payload.volume_general
                if effective_width is not None and effective_width > 0:
                    seat_item["volumetricWidth"] = self._format_decimal(effective_width)
                if effective_length is not None and effective_length > 0:
                    seat_item["volumetricLength"] = self._format_decimal(effective_length)
                if effective_height is not None and effective_height > 0:
                    seat_item["volumetricHeight"] = self._format_decimal(effective_height)
                if effective_volume is not None and effective_volume > 0:
                    seat_item["volumetricVolume"] = self._format_decimal(effective_volume)
                if seat_cost > 0:
                    seat_item["cost"] = str(max(1, int(seat_cost)))
                if seat.description:
                    seat_item["description"] = seat.description
                if payload.special_cargo or seat.special_cargo:
                    seat_item["specialCargo"] = "1"

                pack_ref = seat.pack_ref
                if not pack_ref and resolved_pack_refs:
                    pack_ref = resolved_pack_refs[min(index, len(resolved_pack_refs) - 1)]
                if pack_ref:
                    seat_item["packRef"] = pack_ref
                seats_payload.append(seat_item)

            if seats_payload:
                method_properties["OptionsSeat"] = seats_payload
                method_properties["SeatsAmount"] = str(max(1, len(seats_payload)))
                method_properties["Weight"] = self._format_decimal(max(Decimal("0.001"), seat_weight_total))
                method_properties["Cost"] = self._format_decimal(declared_cost)
        elif resolved_pack_refs:
            seat_count = max(1, payload.seats_amount)
            seat_weight = payload.weight / Decimal(seat_count)
            seat_item: dict[str, Any] = {"weight": self._format_decimal(max(Decimal("0.001"), seat_weight))}
            if payload.volumetric_width is not None and payload.volumetric_width > 0:
                seat_item["volumetricWidth"] = self._format_decimal(payload.volumetric_width)
            if payload.volumetric_length is not None and payload.volumetric_length > 0:
                seat_item["volumetricLength"] = self._format_decimal(payload.volumetric_length)
            if payload.volumetric_height is not None and payload.volumetric_height > 0:
                seat_item["volumetricHeight"] = self._format_decimal(payload.volumetric_height)
            if payload.volume_general is not None and payload.volume_general > 0:
                seat_item["volumetricVolume"] = self._format_decimal(payload.volume_general)
            if payload.cost is not None and payload.cost > 0:
                seat_item["cost"] = self._format_decimal(max(Decimal("1"), payload.cost))
            if payload.description:
                seat_item["description"] = payload.description
            if payload.special_cargo:
                seat_item["specialCargo"] = "1"
            seat_refs = [
                resolved_pack_refs[min(index, len(resolved_pack_refs) - 1)]
                for index in range(seat_count)
            ]
            method_properties["OptionsSeat"] = [
                {**seat_item, "packRef": seat_ref}
                for seat_ref in seat_refs
            ]
            method_properties["Cost"] = self._format_decimal(declared_cost)
        elif payload.volume_general is not None and payload.volume_general > 0:
            method_properties["VolumeGeneral"] = str(payload.volume_general)
            method_properties["Cost"] = self._format_decimal(declared_cost)

        if payload.delivery_type == "address":
            method_properties["RecipientAddressName"] = payload.recipient_address_label
            method_properties["StreetRecipient"] = payload.recipient_street_ref
            method_properties["HouseRecipient"] = payload.recipient_house
            if payload.recipient_apartment:
                method_properties["FlatRecipient"] = payload.recipient_apartment
        else:
            method_properties["RecipientAddress"] = payload.recipient_address_ref

        return method_properties

    @staticmethod
    def _resolve_service_type(delivery_type: str) -> str:
        normalized = (delivery_type or "").strip().lower()
        if normalized == "address":
            return "WarehouseDoors"
        return "WarehouseWarehouse"

    @staticmethod
    def _build_print_url(*, identifier: str, sender: NovaPoshtaSenderProfile, fmt: str) -> str:
        return f"https://my.novaposhta.ua/orders/printDocument/orders[]/{identifier}/type/{fmt}/apiKey/{sender.api_token}"

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        normalized = format(value, "f")
        return normalized.rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _resolve_delivery_by_hand_recipients(*, recipient_name: str, raw_recipients: str) -> list[str]:
        values: list[str] = []
        normalized_recipient_name = recipient_name.strip()
        if normalized_recipient_name:
            values.append(normalized_recipient_name)

        raw_parts = [item.strip() for item in raw_recipients.replace(";", "\n").splitlines()]
        for value in raw_parts:
            if not value:
                continue
            if value in values:
                continue
            values.append(value)
            if len(values) >= 15:
                break

        return values

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
