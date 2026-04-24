from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.backoffice.services.procurement_service import ProcurementService
from apps.commerce.models import Order, OrderItem
from apps.pricing.models import SupplierOffer
from apps.users.rbac import get_user_system_role


@dataclass(frozen=True)
class OrderActionResult:
    order_id: str
    status: str


class OrderOperationsService:
    PRIVILEGED_STATUS_ROLES = {"administrator", "manager"}

    OPERATOR_NEXT_STATUS: dict[str, set[str]] = {
        Order.STATUS_NEW: {Order.STATUS_PROCESSING, Order.STATUS_CANCELLED},
        Order.STATUS_PROCESSING: {Order.STATUS_READY_FOR_SHIPMENT, Order.STATUS_CANCELLED},
        Order.STATUS_READY_FOR_SHIPMENT: {Order.STATUS_SHIPPED, Order.STATUS_CANCELLED},
        Order.STATUS_SHIPPED: {Order.STATUS_COMPLETED},
        Order.STATUS_COMPLETED: set(),
        Order.STATUS_CANCELLED: set(),
    }

    def __init__(self) -> None:
        self.procurement_service = ProcurementService()

    @transaction.atomic
    def confirm_order(self, *, order: Order, operator_note: str = "", actor=None) -> OrderActionResult:
        return self.set_status(
            order=order,
            target_status=Order.STATUS_PROCESSING,
            actor=actor,
            operator_note=operator_note,
        )

    @transaction.atomic
    def mark_awaiting_procurement(self, *, order: Order, operator_note: str = "", actor=None) -> OrderActionResult:
        for item in order.items.all():
            if item.procurement_status == OrderItem.PROCUREMENT_PENDING:
                item.procurement_status = OrderItem.PROCUREMENT_AWAITING
                item.save(update_fields=("procurement_status", "updated_at"))

        return self.set_status(
            order=order,
            target_status=Order.STATUS_PROCESSING,
            actor=actor,
            operator_note=operator_note,
        )

    @transaction.atomic
    def reserve_items(
        self,
        *,
        order: Order,
        item_ids: list[str] | None = None,
        operator_note: str = "",
    ) -> OrderActionResult:
        queryset = order.items.all()
        if item_ids:
            queryset = queryset.filter(id__in=item_ids)

        for item in queryset:
            offer = item.selected_supplier_offer or item.recommended_supplier_offer
            if offer is None:
                recommendation = self.procurement_service.build_item_recommendation(item)
                offer_id = recommendation["recommended_offer"].get("offer_id")
                if offer_id:
                    offer = SupplierOffer.objects.filter(id=offer_id).first()
                    item.recommended_supplier_offer = offer

            if offer is None:
                item.procurement_status = OrderItem.PROCUREMENT_AWAITING
                item.shortage_reason_code = OrderItem.SHORTAGE_UNAVAILABLE
            elif offer.is_available and offer.stock_qty >= item.quantity:
                item.procurement_status = OrderItem.PROCUREMENT_RESERVED
                item.shortage_reason_code = ""
                item.shortage_reason_note = ""
            elif offer.is_available and offer.stock_qty > 0:
                item.procurement_status = OrderItem.PROCUREMENT_PARTIALLY_RESERVED
                item.shortage_reason_code = OrderItem.SHORTAGE_STOCK
            else:
                item.procurement_status = OrderItem.PROCUREMENT_UNAVAILABLE
                item.shortage_reason_code = OrderItem.SHORTAGE_UNAVAILABLE

            item.save(
                update_fields=(
                    "recommended_supplier_offer",
                    "procurement_status",
                    "shortage_reason_code",
                    "shortage_reason_note",
                    "updated_at",
                )
            )

        self._recalculate_order_status_from_items(order)
        if operator_note:
            order.operator_notes = self._merge_note(order.operator_notes, operator_note)
            order.save(update_fields=("operator_notes", "updated_at"))

        return OrderActionResult(order_id=str(order.id), status=order.status)

    @transaction.atomic
    def set_supplier_for_item(
        self,
        *,
        item: OrderItem,
        supplier_offer: SupplierOffer,
        operator_note: str = "",
    ) -> dict:
        if supplier_offer.product_id != item.product_id:
            raise ValidationError({"supplier_offer_id": _("Supplier offer does not match order item product.")})

        item.selected_supplier_offer = supplier_offer
        if item.recommended_supplier_offer_id is None:
            item.recommended_supplier_offer = supplier_offer
        if operator_note:
            item.operator_note = self._merge_note(item.operator_note, operator_note)

        item.save(update_fields=("selected_supplier_offer", "recommended_supplier_offer", "operator_note", "updated_at"))
        return self.procurement_service.build_item_recommendation(item)

    @transaction.atomic
    def mark_ready_to_ship(self, *, order: Order, operator_note: str = "", actor=None) -> OrderActionResult:
        return self.set_status(
            order=order,
            target_status=Order.STATUS_READY_FOR_SHIPMENT,
            actor=actor,
            operator_note=operator_note,
        )

    @transaction.atomic
    def mark_shipped(self, *, order: Order, operator_note: str = "", actor=None) -> OrderActionResult:
        return self.set_status(
            order=order,
            target_status=Order.STATUS_SHIPPED,
            actor=actor,
            operator_note=operator_note,
        )

    @transaction.atomic
    def mark_completed(self, *, order: Order, operator_note: str = "", actor=None) -> OrderActionResult:
        return self.set_status(
            order=order,
            target_status=Order.STATUS_COMPLETED,
            actor=actor,
            operator_note=operator_note,
        )

    @transaction.atomic
    def reset_to_new(self, *, order: Order, operator_note: str = "", actor=None) -> OrderActionResult:
        return self.set_status(
            order=order,
            target_status=Order.STATUS_NEW,
            actor=actor,
            operator_note=operator_note,
        )

    @transaction.atomic
    def cancel_order(
        self,
        *,
        order: Order,
        reason_code: str,
        reason_note: str = "",
        operator_note: str = "",
        actor=None,
    ) -> OrderActionResult:
        return self.set_status(
            order=order,
            target_status=Order.STATUS_CANCELLED,
            actor=actor,
            operator_note=operator_note,
            reason_code=reason_code,
            reason_note=reason_note,
        )

    @transaction.atomic
    def set_status(
        self,
        *,
        order: Order,
        target_status: str,
        actor=None,
        operator_note: str = "",
        reason_code: str = "",
        reason_note: str = "",
    ) -> OrderActionResult:
        self._ensure_transition_allowed(order=order, target_status=target_status, actor=actor)

        order.status = target_status
        if target_status == Order.STATUS_CANCELLED:
            order.cancellation_reason_code = reason_code or Order.CANCELLATION_OPERATOR_DECISION
            order.cancellation_reason_note = reason_note
        else:
            order.cancellation_reason_code = ""
            order.cancellation_reason_note = ""

        if operator_note:
            order.operator_notes = self._merge_note(order.operator_notes, operator_note)

        order.save(
            update_fields=(
                "status",
                "cancellation_reason_code",
                "cancellation_reason_note",
                "operator_notes",
                "updated_at",
            )
        )

        if target_status == Order.STATUS_CANCELLED:
            order.items.update(procurement_status=OrderItem.PROCUREMENT_CANCELLED)

        return OrderActionResult(order_id=str(order.id), status=order.status)

    @transaction.atomic
    def delete_order(self, *, order: Order, operator_note: str = "") -> dict:
        if order.status in {Order.STATUS_SHIPPED, Order.STATUS_COMPLETED}:
            raise ValidationError({"order": _("Нельзя удалить заказ в статусе отправлен/завершен.")})

        if operator_note:
            order.operator_notes = self._merge_note(order.operator_notes, operator_note)
            order.save(update_fields=("operator_notes", "updated_at"))

        order_id = str(order.id)
        order_number = order.order_number
        order.delete()
        return {"order_id": order_id, "order_number": order_number}

    @transaction.atomic
    def bulk_confirm(self, *, order_ids: list[str], operator_note: str = "") -> dict:
        orders = Order.objects.filter(id__in=order_ids)
        updated = 0
        for order in orders:
            self.confirm_order(order=order, operator_note=operator_note)
            updated += 1
        return {"updated": updated}

    @transaction.atomic
    def bulk_mark_awaiting_procurement(self, *, order_ids: list[str], operator_note: str = "") -> dict:
        orders = Order.objects.filter(id__in=order_ids)
        updated = 0
        for order in orders:
            self.mark_awaiting_procurement(order=order, operator_note=operator_note)
            updated += 1
        return {"updated": updated}

    def bulk_delete(self, *, order_ids: list[str], operator_note: str = "") -> dict:
        orders = Order.objects.filter(id__in=order_ids)
        deleted = 0
        skipped: list[dict[str, str]] = []

        for order in orders:
            try:
                self.delete_order(order=order, operator_note=operator_note)
                deleted += 1
            except ValidationError as exc:
                skipped.append(
                    {
                        "order_id": str(order.id),
                        "reason": self._extract_validation_reason(exc),
                    }
                )

        return {"deleted": deleted, "skipped": skipped}

    @transaction.atomic
    def supplier_recommendation_for_item(self, *, item: OrderItem) -> dict:
        return self.procurement_service.build_item_recommendation(item)

    def _recalculate_order_status_from_items(self, order: Order) -> None:
        if order.status in {
            Order.STATUS_READY_FOR_SHIPMENT,
            Order.STATUS_SHIPPED,
            Order.STATUS_COMPLETED,
            Order.STATUS_CANCELLED,
        }:
            return

        next_status = Order.STATUS_PROCESSING

        if order.status != next_status:
            order.status = next_status
            order.save(update_fields=("status", "updated_at"))

    def _merge_note(self, existing: str, note: str) -> str:
        note = note.strip()
        if not note:
            return existing
        if not existing:
            return note
        return f"{existing}\n{note}"

    def _is_privileged_actor(self, actor) -> bool:
        if actor is None:
            return False
        if getattr(actor, "is_superuser", False):
            return True
        role = get_user_system_role(actor)
        return role in self.PRIVILEGED_STATUS_ROLES

    def _ensure_transition_allowed(self, *, order: Order, target_status: str, actor) -> None:
        allowed_statuses = {value for value, _label in Order.STATUS_CHOICES}
        if target_status not in allowed_statuses:
            raise DRFValidationError({"order": _("Unsupported status transition target.")})

        if order.status == target_status:
            return

        if self._is_privileged_actor(actor):
            return

        allowed_next = self.OPERATOR_NEXT_STATUS.get(order.status, set())
        if target_status not in allowed_next:
            raise DRFValidationError({"order": _("Operator can change status only in sequence.")})

    def _extract_validation_reason(self, error: ValidationError) -> str:
        if hasattr(error, "message_dict"):
            values = list(error.message_dict.values())
            if values and isinstance(values[0], list) and values[0]:
                return str(values[0][0])
        if hasattr(error, "messages") and error.messages:
            return str(error.messages[0])
        return str(error)
