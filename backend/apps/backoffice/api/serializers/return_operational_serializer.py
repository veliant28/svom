from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.catalog.services.product_management import get_product_display_name
from apps.commerce.models import ReturnEvent, ReturnRequest, ReturnRequestItem
from apps.commerce.services import build_return_day_label, format_tracking_number
from apps.users.rbac import get_user_system_role


class BackofficeReturnItemOperationalSerializer(serializers.ModelSerializer):
    product_display_name = serializers.SerializerMethodField()
    product_svom_sku = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    supplier_code = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequestItem
        fields = (
            "id",
            "order_item",
            "product",
            "product_display_name",
            "product_svom_sku",
            "product_name_snapshot",
            "product_sku_snapshot",
            "supplier_name",
            "supplier_code",
            "quantity_ordered",
            "quantity_requested",
            "quantity_approved",
            "original_unit_price",
            "original_line_total",
            "refund_amount",
            "is_returnable_snapshot",
            "non_returnable_reason_snapshot",
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

    def get_product_display_name(self, obj: ReturnRequestItem) -> str:
        product = getattr(obj, "product", None)
        if product is None:
            return str(obj.product_name_snapshot or "").strip()
        return get_product_display_name(product, self._resolve_locale())

    def get_product_svom_sku(self, obj: ReturnRequestItem) -> str:
        product = getattr(obj, "product", None)
        if product is not None:
            svom_sku = str(getattr(product, "svom_sku", "") or "").strip()
            if svom_sku:
                return svom_sku
        return str(obj.product_sku_snapshot or "").strip()

    @staticmethod
    def _resolve_selected_offer(obj: ReturnRequestItem):
        order_item = getattr(obj, "order_item", None)
        if order_item is None:
            return None
        return getattr(order_item, "selected_supplier_offer", None) or getattr(order_item, "snapshot_selected_offer", None)

    def get_supplier_name(self, obj: ReturnRequestItem) -> str:
        offer = self._resolve_selected_offer(obj)
        supplier = getattr(offer, "supplier", None)
        return str(getattr(supplier, "name", "") or "").strip()

    def get_supplier_code(self, obj: ReturnRequestItem) -> str:
        offer = self._resolve_selected_offer(obj)
        supplier = getattr(offer, "supplier", None)
        return str(getattr(supplier, "code", "") or "").strip()


class BackofficeReturnEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ReturnEvent
        fields = (
            "id",
            "actor",
            "actor_name",
            "from_status",
            "to_status",
            "comment",
            "metadata",
            "created_at",
        )

    @staticmethod
    def get_actor_name(obj: ReturnEvent) -> str:
        actor = getattr(obj, "actor", None)
        if actor is None:
            return ""
        return (actor.get_full_name() or "").strip() or str(actor.email or "").strip()


class BackofficeReturnOperationalListSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    customer_name = serializers.CharField(source="order.contact_full_name", read_only=True)
    customer_phone = serializers.CharField(source="order.contact_phone", read_only=True)
    customer_email = serializers.CharField(source="order.contact_email", read_only=True)
    return_day_label = serializers.SerializerMethodField()
    tracking_number = serializers.SerializerMethodField()
    last_actor = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = (
            "id",
            "return_number",
            "order",
            "order_number",
            "status",
            "refund_amount",
            "customer_name",
            "customer_phone",
            "customer_email",
            "tracking_number",
            "created_at",
            "return_day_label",
            "last_actor",
        )

    @staticmethod
    def get_tracking_number(obj: ReturnRequest) -> str:
        return format_tracking_number(obj.customer_return_tracking_number)

    @staticmethod
    def get_return_day_label(obj: ReturnRequest) -> str:
        return build_return_day_label(received_at=obj.order.received_at, created_at=obj.created_at)

    def get_last_actor(self, obj: ReturnRequest) -> dict | None:
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("events")
        if isinstance(prefetched, list) and prefetched:
            latest_event = prefetched[0]
            return self._serialize_staff_actor(getattr(latest_event, "actor", None))
        latest_event = obj.events.select_related("actor").order_by("-created_at").first()
        if latest_event is None:
            return None
        return self._serialize_staff_actor(getattr(latest_event, "actor", None))

    @staticmethod
    def _serialize_staff_actor(user) -> dict | None:
        if user is None:
            return None
        role_code = get_user_system_role(user)
        if role_code is None and getattr(user, "is_superuser", False):
            role_code = "administrator"
        full_name = (user.get_full_name() or "").strip() or str(user.email or "").strip()
        role_group_name = f"Backoffice Role: {role_code}" if role_code else ""
        return {
            "user_id": str(user.id),
            "full_name": full_name,
            "role_code": role_code,
            "role_group_name": role_group_name,
        }


class BackofficeReturnOperationalDetailSerializer(BackofficeReturnOperationalListSerializer):
    items = BackofficeReturnItemOperationalSerializer(many=True, read_only=True)
    events = BackofficeReturnEventSerializer(many=True, read_only=True)

    class Meta(BackofficeReturnOperationalListSerializer.Meta):
        fields = BackofficeReturnOperationalListSerializer.Meta.fields + (
            "reason_comment",
            "admin_comment",
            "rejection_reason",
            "refund_status",
            "refund_method",
            "customer_return_tracking_submitted_at",
            "nova_poshta_return_status_code",
            "nova_poshta_return_status_text",
            "nova_poshta_return_status_synced_at",
            "return_address_snapshot",
            "received_at",
            "approved_at",
            "rejected_at",
            "accepted_at",
            "refund_processing_at",
            "refunded_at",
            "updated_at",
            "items",
            "events",
        )


class BackofficeReturnStatusUpdateSerializer(serializers.Serializer):
    class ApprovedItemSerializer(serializers.Serializer):
        item_id = serializers.UUIDField()
        quantity_approved = serializers.IntegerField(min_value=0)

    status = serializers.ChoiceField(choices=ReturnRequest.STATUS_CHOICES)
    admin_comment = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    approved_items = ApprovedItemSerializer(many=True, required=False)

    def validate(self, attrs: dict) -> dict:
        status_value = str(attrs.get("status") or "").strip()
        if status_value == ReturnRequest.STATUS_REJECTED:
            rejection_reason = str(attrs.get("rejection_reason") or "").strip()
            if not rejection_reason:
                raise serializers.ValidationError({"rejection_reason": "Rejection reason is required."})
        return attrs


class BackofficeReturnsSettingsSerializer(serializers.Serializer):
    returns_enabled = serializers.BooleanField()
    returns_recipient_full_name = serializers.CharField(allow_blank=True, required=False)
    returns_recipient_phone = serializers.CharField(allow_blank=True, required=False)
    returns_region_ref = serializers.CharField(allow_blank=True, required=False)
    returns_region_label = serializers.CharField(allow_blank=True, required=False)
    returns_city_ref = serializers.CharField(allow_blank=True, required=False)
    returns_city_label = serializers.CharField(allow_blank=True, required=False)
    returns_np_warehouse_text = serializers.CharField(allow_blank=True, required=False)
    returns_non_returnable_category_ids = serializers.ListField(child=serializers.CharField(), required=False)
    returns_include_subcategories = serializers.BooleanField(required=False)


class BackofficeReturnsSettingsPatchSerializer(serializers.Serializer):
    returns_recipient_full_name = serializers.CharField(allow_blank=True, required=False, trim_whitespace=True)
    returns_recipient_phone = serializers.CharField(allow_blank=True, required=False, trim_whitespace=True)
    returns_region_ref = serializers.CharField(allow_blank=True, required=False, trim_whitespace=True)
    returns_region_label = serializers.CharField(allow_blank=True, required=False, trim_whitespace=True)
    returns_city_ref = serializers.CharField(allow_blank=True, required=False, trim_whitespace=True)
    returns_city_label = serializers.CharField(allow_blank=True, required=False, trim_whitespace=True)
    returns_np_warehouse_text = serializers.CharField(allow_blank=True, required=False, trim_whitespace=True)
    returns_non_returnable_category_ids = serializers.ListField(child=serializers.CharField(), required=False)
    returns_include_subcategories = serializers.BooleanField(required=False)


def apply_return_status_transition(*, obj: ReturnRequest, target_status: str, actor, admin_comment: str = "", rejection_reason: str = "") -> None:
    now_ts = timezone.now()
    previous_status = obj.status

    obj.status = target_status
    if admin_comment:
        obj.admin_comment = admin_comment

    update_fields = {"status", "updated_at"}
    if admin_comment:
        update_fields.add("admin_comment")

    if target_status == ReturnRequest.STATUS_APPROVED:
        obj.approved_at = now_ts
        update_fields.add("approved_at")
    elif target_status == ReturnRequest.STATUS_REJECTED:
        obj.rejected_at = now_ts
        obj.rejection_reason = rejection_reason
        update_fields.update({"rejected_at", "rejection_reason"})
    elif target_status == ReturnRequest.STATUS_RECEIVED:
        obj.received_at = now_ts
        update_fields.add("received_at")
    elif target_status == ReturnRequest.STATUS_ACCEPTED:
        obj.accepted_at = now_ts
        update_fields.add("accepted_at")
    elif target_status == ReturnRequest.STATUS_REFUNDED:
        if not obj.refund_processing_at:
            obj.refund_processing_at = now_ts
        obj.refunded_at = now_ts
        obj.refund_status = ReturnRequest.REFUND_STATUS_DONE
        update_fields.update({"refund_processing_at", "refunded_at", "refund_status"})

    obj.save(update_fields=tuple(sorted(update_fields)))
    ReturnEvent.objects.create(
        return_request=obj,
        actor=actor,
        from_status=previous_status,
        to_status=target_status,
        comment=admin_comment[:500],
        metadata={"rejection_reason": rejection_reason[:500] if rejection_reason else ""},
    )
