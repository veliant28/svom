from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.catalog.services.product_management import get_product_display_name
from apps.catalog.services.product_sku import get_product_catalog_article, get_product_display_sku, get_product_manufacturer_article
from apps.commerce.models import Order, OrderItem, ReturnRequest, ReturnRequestItem
from apps.commerce.services import (
    RETURN_TTN_DIGITS,
    build_return_address_snapshot,
    build_return_day_label,
    build_returnable_order_items,
    format_tracking_number,
    is_tracking_edit_window_open,
    normalize_tracking_number,
)
from apps.commerce.services.returns_service import ReturnableOrderItem

from .product_summary_serializer import CommerceProductSummarySerializer


class ReturnRequestListSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    tracking_number = serializers.SerializerMethodField()
    return_day_label = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = (
            "id",
            "return_number",
            "order_number",
            "created_at",
            "return_day_label",
            "status",
            "refund_amount",
            "tracking_number",
        )

    def get_tracking_number(self, obj: ReturnRequest) -> str:
        return format_tracking_number(obj.customer_return_tracking_number)

    def get_return_day_label(self, obj: ReturnRequest) -> str:
        return build_return_day_label(received_at=obj.order.received_at, created_at=obj.created_at)


class ReturnRequestItemSerializer(serializers.ModelSerializer):
    display_sku = serializers.SerializerMethodField()
    display_brand = serializers.SerializerMethodField()
    display_article = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequestItem
        fields = (
            "id",
            "order_item",
            "product",
            "product_name_snapshot",
            "product_sku_snapshot",
            "quantity_ordered",
            "quantity_requested",
            "quantity_approved",
            "original_unit_price",
            "original_line_total",
            "refund_amount",
            "is_returnable_snapshot",
            "non_returnable_reason_snapshot",
            "display_sku",
            "display_brand",
            "display_article",
            "display_name",
        )

    def _resolve_locale(self) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None
        language_code = getattr(request, "LANGUAGE_CODE", "")
        if language_code:
            return str(language_code)
        accept_language = str(request.headers.get("Accept-Language", "")).strip()
        if not accept_language:
            return None
        return accept_language.split(",", 1)[0]

    def _product(self, obj: ReturnRequestItem):
        return getattr(obj, "product", None)

    def get_display_sku(self, obj: ReturnRequestItem) -> str:
        product = self._product(obj)
        if product is None:
            return str(obj.product_sku_snapshot or "").strip()
        return get_product_display_sku(product)

    def get_display_brand(self, obj: ReturnRequestItem) -> str:
        product = self._product(obj)
        if product is None:
            return ""
        return str(getattr(product, "display_brand_name", "") or getattr(product, "autodb_supplier_name", "") or "").strip()

    def get_display_article(self, obj: ReturnRequestItem) -> str:
        product = self._product(obj)
        if product is None:
            return ""
        return get_product_catalog_article(product) or get_product_manufacturer_article(product)

    def get_display_name(self, obj: ReturnRequestItem) -> str:
        product = self._product(obj)
        if product is None:
            return str(obj.product_name_snapshot or "").strip()
        return get_product_display_name(product, self._resolve_locale())


class ReturnRequestDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    return_day_label = serializers.SerializerMethodField()
    tracking_number = serializers.SerializerMethodField()
    items = ReturnRequestItemSerializer(many=True, read_only=True)
    shipping_address = serializers.SerializerMethodField()
    can_edit_tracking_number = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = (
            "id",
            "return_number",
            "order",
            "order_number",
            "status",
            "reason_comment",
            "admin_comment",
            "rejection_reason",
            "refund_amount",
            "refund_status",
            "refund_method",
            "tracking_number",
            "customer_return_tracking_submitted_at",
            "can_edit_tracking_number",
            "nova_poshta_return_status_code",
            "nova_poshta_return_status_text",
            "nova_poshta_return_status_synced_at",
            "shipping_address",
            "received_at",
            "approved_at",
            "rejected_at",
            "accepted_at",
            "refund_processing_at",
            "refunded_at",
            "created_at",
            "updated_at",
            "return_day_label",
            "items",
        )

    def get_tracking_number(self, obj: ReturnRequest) -> str:
        return format_tracking_number(obj.customer_return_tracking_number)

    def get_return_day_label(self, obj: ReturnRequest) -> str:
        return build_return_day_label(received_at=obj.order.received_at, created_at=obj.created_at)

    def get_shipping_address(self, obj: ReturnRequest) -> dict[str, str]:
        snapshot = obj.return_address_snapshot or {}
        if snapshot:
            return {
                "recipient_full_name": str(snapshot.get("recipient_full_name") or "").strip(),
                "recipient_phone": str(snapshot.get("recipient_phone") or "").strip(),
                "region_ref": str(snapshot.get("region_ref") or "").strip(),
                "region_label": str(snapshot.get("region_label") or "").strip(),
                "city_ref": str(snapshot.get("city_ref") or "").strip(),
                "city_label": str(snapshot.get("city_label") or "").strip(),
                "np_warehouse_text": str(snapshot.get("np_warehouse_text") or "").strip(),
            }
        return build_return_address_snapshot()

    def get_can_edit_tracking_number(self, obj: ReturnRequest) -> bool:
        if obj.status in {ReturnRequest.STATUS_APPROVED, ReturnRequest.STATUS_AWAITING_TTN}:
            return True
        if obj.status != ReturnRequest.STATUS_IN_TRANSIT:
            return False
        return is_tracking_edit_window_open(submitted_at=obj.customer_return_tracking_submitted_at)


class EligibleOrderListSerializer(serializers.ModelSerializer):
    return_day_label = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "total",
            "currency",
            "status",
            "placed_at",
            "return_day_label",
            "items_count",
        )

    def get_return_day_label(self, obj: Order) -> str:
        return build_return_day_label(received_at=obj.received_at, created_at=timezone.now())

    def get_items_count(self, obj: Order) -> int:
        annotated = getattr(obj, "items_count", None)
        if annotated is not None:
            return int(annotated)
        return int(obj.items.count())


class EligibleOrderItemSerializer(serializers.Serializer):
    order_item_id = serializers.CharField()
    product = CommerceProductSummarySerializer()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    quantity_ordered = serializers.IntegerField()
    max_return_quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_returnable = serializers.BooleanField()
    non_returnable_reason = serializers.CharField(allow_blank=True)

    @classmethod
    def from_returnable_item(cls, item: ReturnableOrderItem) -> dict:
        order_item = item.order_item
        product_payload = CommerceProductSummarySerializer(order_item.product).data
        return {
            "order_item_id": str(order_item.id),
            "product": product_payload,
            "product_name": order_item.product_name,
            "product_sku": order_item.product_sku,
            "quantity_ordered": int(order_item.quantity),
            "max_return_quantity": int(item.max_return_quantity),
            "unit_price": Decimal(order_item.unit_price or "0"),
            "line_total": Decimal(order_item.line_total or "0"),
            "is_returnable": bool(item.is_returnable),
            "non_returnable_reason": item.non_returnable_reason,
        }


class CreateReturnRequestItemInputSerializer(serializers.Serializer):
    order_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CreateReturnRequestInputSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    items = CreateReturnRequestItemInputSerializer(many=True)
    reason_comment = serializers.CharField(trim_whitespace=True, min_length=10)


class SubmitReturnTrackingInputSerializer(serializers.Serializer):
    tracking_number = serializers.CharField(trim_whitespace=True)

    def validate_tracking_number(self, value: str) -> str:
        normalized = normalize_tracking_number(value)
        if not normalized:
            raise serializers.ValidationError(f"Tracking number must contain exactly {RETURN_TTN_DIGITS} digits.")
        return normalized
