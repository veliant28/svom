from __future__ import annotations

from rest_framework import serializers

from apps.commerce.models import OrderEvent, OrderNovaPoshtaWaybillEvent
from apps.commerce.services.nova_poshta.tracking_status_catalog import resolve_tracking_status_text
from apps.users.rbac import get_user_system_role


def _serialize_staff_actor(user) -> dict | None:
    if user is None:
        return None
    role_code = get_user_system_role(user)
    if role_code is None and getattr(user, "is_superuser", False):
        role_code = "administrator"
    full_name = (user.get_full_name() or "").strip() or (user.email or "").strip()
    role_group_name = f"Backoffice Role: {role_code}" if role_code else ""
    return {
        "user_id": str(user.id),
        "full_name": full_name,
        "role_code": role_code,
        "role_group_name": role_group_name,
    }


class BackofficeOrderHistoryEventSerializer(serializers.ModelSerializer):
    source = serializers.SerializerMethodField()
    event_label = serializers.SerializerMethodField()
    action = serializers.CharField(source="action_label", read_only=True)
    occurred_at = serializers.DateTimeField(source="created_at", read_only=True)
    actor = serializers.SerializerMethodField()

    class Meta:
        model = OrderEvent
        fields = (
            "id",
            "source",
            "event_type",
            "event_label",
            "action",
            "message",
            "payload",
            "occurred_at",
            "actor",
        )

    @staticmethod
    def get_source(_obj: OrderEvent) -> str:
        return "order"

    @staticmethod
    def get_event_label(obj: OrderEvent) -> str:
        return str(obj.get_event_type_display() or "")

    @staticmethod
    def get_actor(obj: OrderEvent) -> dict | None:
        return _serialize_staff_actor(obj.created_by)


class BackofficeWaybillHistoryEventSerializer(serializers.ModelSerializer):
    source = serializers.SerializerMethodField()
    event_label = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()
    occurred_at = serializers.DateTimeField(source="created_at", read_only=True)
    actor = serializers.SerializerMethodField()

    class Meta:
        model = OrderNovaPoshtaWaybillEvent
        fields = (
            "id",
            "source",
            "event_type",
            "event_label",
            "action",
            "message",
            "payload",
            "status_code",
            "status_text",
            "occurred_at",
            "actor",
        )

    @staticmethod
    def get_source(_obj: OrderNovaPoshtaWaybillEvent) -> str:
        return "waybill"

    @staticmethod
    def get_event_label(obj: OrderNovaPoshtaWaybillEvent) -> str:
        return str(obj.get_event_type_display() or "")

    def get_action(self, obj: OrderNovaPoshtaWaybillEvent) -> str:
        message = str(obj.message or "").strip()
        if message:
            return message
        label = str(obj.get_event_type_display() or "").strip()
        resolved_status_text = resolve_tracking_status_text(
            status_code=obj.status_code or "",
            status_text=obj.status_text or "",
        )
        if resolved_status_text:
            return f"{label}: {resolved_status_text}"
        return label or str(obj.event_type or "").strip()

    @staticmethod
    def get_actor(obj: OrderNovaPoshtaWaybillEvent) -> dict | None:
        return _serialize_staff_actor(obj.created_by)
