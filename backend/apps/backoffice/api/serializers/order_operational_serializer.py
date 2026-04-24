from __future__ import annotations

from functools import lru_cache

from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from django.db.utils import DatabaseError, OperationalError, ProgrammingError
from rest_framework import serializers

from apps.commerce.models import Order, OrderItem
from apps.commerce.services.delivery_snapshot import resolve_delivery_display, resolve_waybill_seed
from apps.commerce.services.nova_poshta.tracking_status_catalog import resolve_tracking_status_text
from apps.commerce.services.vchasno_kasa import serialize_receipt_summary


class BackofficeOrderItemOperationalSerializer(serializers.ModelSerializer):
    product_id = serializers.CharField(source="product.id", read_only=True)
    recommended_supplier_offer_id = serializers.CharField(read_only=True, allow_null=True)
    recommended_supplier_name = serializers.CharField(source="recommended_supplier_offer.supplier.name", read_only=True, default="")
    selected_supplier_offer_id = serializers.CharField(read_only=True, allow_null=True)
    selected_supplier_name = serializers.CharField(source="selected_supplier_offer.supplier.name", read_only=True, default="")

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "line_total",
            "procurement_status",
            "recommended_supplier_offer_id",
            "recommended_supplier_name",
            "selected_supplier_offer_id",
            "selected_supplier_name",
            "shortage_reason_code",
            "shortage_reason_note",
            "operator_note",
            "snapshot_availability_status",
            "snapshot_availability_label",
            "snapshot_estimated_delivery_days",
            "snapshot_procurement_source",
            "snapshot_currency",
            "snapshot_sell_price",
        )


class BackofficeOrderOperationalListSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_id = serializers.CharField(source="user.id", read_only=True)
    items_count = serializers.SerializerMethodField()
    issues_count = serializers.SerializerMethodField()
    nova_poshta_waybill_number = serializers.SerializerMethodField()
    nova_poshta_waybill_status_code = serializers.SerializerMethodField()
    nova_poshta_waybill_status_text = serializers.SerializerMethodField()
    nova_poshta_waybill_has_error = serializers.SerializerMethodField()
    nova_poshta_waybill_exists = serializers.SerializerMethodField()
    delivery_snapshot = serializers.JSONField(read_only=True)
    delivery_city_label = serializers.SerializerMethodField()
    delivery_destination_label = serializers.SerializerMethodField()
    delivery_waybill_seed = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    receipt = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "status",
            "user_id",
            "user_email",
            "contact_full_name",
            "contact_phone",
            "contact_email",
            "delivery_method",
            "delivery_address",
            "delivery_snapshot",
            "delivery_city_label",
            "delivery_destination_label",
            "delivery_waybill_seed",
            "payment_method",
            "payment",
            "receipt",
            "subtotal",
            "delivery_fee",
            "total",
            "currency",
            "items_count",
            "issues_count",
            "nova_poshta_waybill_exists",
            "nova_poshta_waybill_number",
            "nova_poshta_waybill_status_code",
            "nova_poshta_waybill_status_text",
            "nova_poshta_waybill_has_error",
            "placed_at",
        )

    def get_items_count(self, obj: Order) -> int:
        return obj.items.count()

    def get_issues_count(self, obj: Order) -> int:
        problematic_statuses = {
            OrderItem.PROCUREMENT_UNAVAILABLE,
            OrderItem.PROCUREMENT_PARTIALLY_RESERVED,
        }
        return sum(
            1
            for item in obj.items.all()
            if item.procurement_status in problematic_statuses or bool(item.shortage_reason_code)
        )

    @staticmethod
    def _active_waybill(obj: Order):
        waybills = getattr(obj, "backoffice_active_waybills", None)
        if isinstance(waybills, list) and waybills:
            return waybills[0]
        return None

    def get_nova_poshta_waybill_exists(self, obj: Order) -> bool:
        return self._active_waybill(obj) is not None

    def get_nova_poshta_waybill_number(self, obj: Order) -> str:
        waybill = self._active_waybill(obj)
        if not waybill:
            return ""
        return waybill.np_number or ""

    def get_nova_poshta_waybill_status_code(self, obj: Order) -> str:
        waybill = self._active_waybill(obj)
        if not waybill:
            return ""
        return waybill.status_code or ""

    def get_nova_poshta_waybill_status_text(self, obj: Order) -> str:
        waybill = self._active_waybill(obj)
        if not waybill:
            return ""
        return resolve_tracking_status_text(
            status_code=waybill.status_code,
            status_text=waybill.status_text,
        )

    def get_nova_poshta_waybill_has_error(self, obj: Order) -> bool:
        waybill = self._active_waybill(obj)
        if not waybill:
            return False
        return bool(waybill.last_sync_error)

    @staticmethod
    def _normalize_waybill_destination_label(waybill) -> str:
        recipient_address_label = (waybill.recipient_address_label or "").strip()
        if recipient_address_label:
            return recipient_address_label

        street = (waybill.recipient_street_label or "").strip()
        house = (waybill.recipient_house or "").strip()
        apartment = (waybill.recipient_apartment or "").strip()
        if street and house and apartment:
            return f"{street}, {house}, {apartment}"
        if street and house:
            return f"{street}, {house}"
        if street:
            return street
        return ""

    def get_delivery_city_label(self, obj: Order) -> str:
        city_label, _ = resolve_delivery_display(
            delivery_method=obj.delivery_method,
            delivery_address=obj.delivery_address,
            delivery_snapshot=obj.delivery_snapshot,
        )
        if city_label:
            return city_label

        waybill = self._active_waybill(obj)
        if waybill:
            return (waybill.recipient_city_label or "").strip()
        return ""

    def get_delivery_destination_label(self, obj: Order) -> str:
        _, destination_label = resolve_delivery_display(
            delivery_method=obj.delivery_method,
            delivery_address=obj.delivery_address,
            delivery_snapshot=obj.delivery_snapshot,
        )
        if destination_label:
            return destination_label

        waybill = self._active_waybill(obj)
        if waybill:
            return self._normalize_waybill_destination_label(waybill)
        return ""

    def get_delivery_waybill_seed(self, obj: Order) -> dict:
        seed = resolve_waybill_seed(
            delivery_method=obj.delivery_method,
            delivery_address=obj.delivery_address,
            delivery_snapshot=obj.delivery_snapshot,
        )
        if obj.delivery_snapshot:
            return seed

        waybill = self._active_waybill(obj)
        if not waybill:
            return seed

        return {
            "delivery_type": "address" if waybill.service_type == "WarehouseDoors" else "warehouse",
            "recipient_city_ref": (waybill.recipient_city_ref or "").strip(),
            "recipient_city_label": (waybill.recipient_city_label or "").strip(),
            "recipient_address_ref": (waybill.recipient_address_ref or "").strip(),
            "recipient_address_label": self._normalize_waybill_destination_label(waybill),
            "recipient_street_ref": (waybill.recipient_street_ref or "").strip(),
            "recipient_street_label": (waybill.recipient_street_label or "").strip(),
            "recipient_house": (waybill.recipient_house or "").strip(),
            "recipient_apartment": (waybill.recipient_apartment or "").strip(),
        }

    def get_payment(self, obj: Order) -> dict:
        if obj.payment_method == Order.PAYMENT_MONOBANK:
            default_provider = "monobank"
            default_method = "monobank"
        elif obj.payment_method == Order.PAYMENT_LIQPAY:
            default_provider = "liqpay"
            default_method = "liqpay"
        else:
            default_provider = "cash_on_delivery"
            default_method = "cash_on_delivery"

        if not _order_payment_table_exists():
            return {
                "provider": default_provider,
                "method": default_method,
                "status": "pending",
                "amount": obj.total,
                "currency": obj.currency,
                "invoice_id": "",
                "reference": "",
                "page_url": "",
                "failure_reason": "",
                "provider_created_at": None,
                "provider_modified_at": None,
                "last_webhook_received_at": None,
                "last_sync_at": None,
            }

        try:
            payment = obj.payment
        except (ObjectDoesNotExist, DatabaseError, OperationalError, ProgrammingError):
            payment = None
        if not payment:
            return {
                "provider": default_provider,
                "method": default_method,
                "status": "pending",
                "amount": obj.total,
                "currency": obj.currency,
                "invoice_id": "",
                "reference": "",
                "page_url": "",
                "failure_reason": "",
                "provider_created_at": None,
                "provider_modified_at": None,
                "last_webhook_received_at": None,
                "last_sync_at": None,
            }

        provider = payment.provider
        invoice_id = payment.monobank_invoice_id
        reference = payment.monobank_reference
        page_url = payment.monobank_page_url
        if provider == payment.PROVIDER_LIQPAY:
            invoice_id = payment.liqpay_payment_id
            reference = payment.liqpay_order_id
            page_url = payment.liqpay_page_url

        return {
            "provider": payment.provider,
            "method": payment.method,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
            "invoice_id": invoice_id,
            "reference": reference,
            "page_url": page_url,
            "failure_reason": payment.failure_reason,
            "provider_created_at": payment.provider_created_at,
            "provider_modified_at": payment.provider_modified_at,
            "last_webhook_received_at": payment.last_webhook_received_at,
            "last_sync_at": payment.last_sync_at,
        }

    def get_receipt(self, obj: Order) -> dict:
        return serialize_receipt_summary(order=obj)


class BackofficeOrderOperationalDetailSerializer(BackofficeOrderOperationalListSerializer):
    items = BackofficeOrderItemOperationalSerializer(many=True, read_only=True)

    class Meta(BackofficeOrderOperationalListSerializer.Meta):
        fields = BackofficeOrderOperationalListSerializer.Meta.fields + (
            "customer_comment",
            "internal_notes",
            "operator_notes",
            "cancellation_reason_code",
            "cancellation_reason_note",
            "items",
        )


@lru_cache(maxsize=1)
def _order_payment_table_exists() -> bool:
    try:
        return "commerce_orderpayment" in set(connection.introspection.table_names())
    except (DatabaseError, OperationalError, ProgrammingError):
        return False
