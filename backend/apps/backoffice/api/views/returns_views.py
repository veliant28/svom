from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.backoffice.api.pagination import BackofficeOrderPagination
from apps.backoffice.api.serializers import (
    BackofficeReturnOperationalDetailSerializer,
    BackofficeReturnOperationalListSerializer,
    BackofficeReturnStatusUpdateSerializer,
    apply_return_status_transition,
)
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import apply_operational_return_filters, get_operational_returns_queryset
from apps.commerce.models import ReturnRequest
from apps.commerce.services import build_return_address_snapshot
from apps.core.services import send_ops_return_status_notification
from apps.users.rbac import user_has_capability


ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    ReturnRequest.STATUS_NEW: {ReturnRequest.STATUS_APPROVED, ReturnRequest.STATUS_REJECTED, ReturnRequest.STATUS_CANCELLED},
    ReturnRequest.STATUS_APPROVED: {ReturnRequest.STATUS_AWAITING_TTN, ReturnRequest.STATUS_CANCELLED},
    ReturnRequest.STATUS_AWAITING_TTN: {ReturnRequest.STATUS_CANCELLED},
    ReturnRequest.STATUS_IN_TRANSIT: {ReturnRequest.STATUS_RECEIVED, ReturnRequest.STATUS_CANCELLED},
    ReturnRequest.STATUS_RECEIVED: {ReturnRequest.STATUS_ACCEPTED},
    ReturnRequest.STATUS_ACCEPTED: {ReturnRequest.STATUS_REFUND_PROCESSING},
    ReturnRequest.STATUS_REFUND_PROCESSING: {ReturnRequest.STATUS_REFUNDED},
}


class BackofficeReturnListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    required_capability = "returns.view"
    serializer_class = BackofficeReturnOperationalListSerializer
    pagination_class = BackofficeOrderPagination

    def get_queryset(self):
        queryset = get_operational_returns_queryset()
        return apply_operational_return_filters(queryset, params=self.request.query_params)


class BackofficeReturnDetailAPIView(RetrieveAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    required_capability = "returns.view"
    serializer_class = BackofficeReturnOperationalDetailSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_operational_returns_queryset()


class BackofficeReturnStatusUpdateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    required_capability = "returns.manage"

    @transaction.atomic
    def post(self, request, id):
        serializer = BackofficeReturnStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        obj = get_object_or_404(get_operational_returns_queryset(), id=id)
        previous_status = obj.status
        target_status = str(serializer.validated_data["status"])
        admin_comment = str(serializer.validated_data.get("admin_comment") or "").strip()
        rejection_reason = str(serializer.validated_data.get("rejection_reason") or "").strip()
        approved_items_provided = "approved_items" in serializer.validated_data
        approved_items_payload = serializer.validated_data.get("approved_items") or []

        if target_status == obj.status:
            payload = BackofficeReturnOperationalDetailSerializer(obj, context={"request": request}).data
            return Response(payload, status=status.HTTP_200_OK)

        allowed = ALLOWED_STATUS_TRANSITIONS.get(obj.status, set())
        if target_status not in allowed:
            raise ValidationError({"status": f"Transition {obj.status} -> {target_status} is not allowed."})

        self._check_status_capability(request=request, target_status=target_status)

        if target_status == ReturnRequest.STATUS_APPROVED:
            snapshot = build_return_address_snapshot()
            required_fields = (
                "recipient_full_name",
                "recipient_phone",
                "region_label",
                "city_label",
                "np_warehouse_text",
            )
            if any(not str(snapshot.get(key) or "").strip() for key in required_fields):
                raise ValidationError({"detail": "Return recipient settings are not configured."})
            obj.return_address_snapshot = snapshot
            self._apply_approved_items(
                obj=obj,
                approved_items_payload=approved_items_payload,
                approved_items_provided=approved_items_provided,
            )
            obj.save(update_fields=("return_address_snapshot", "refund_amount", "updated_at"))

        apply_return_status_transition(
            obj=obj,
            target_status=target_status,
            actor=request.user,
            admin_comment=admin_comment,
            rejection_reason=rejection_reason,
        )
        actor_name = (request.user.get_full_name() or "").strip() or str(request.user.email or "").strip()
        transaction.on_commit(
            lambda: send_ops_return_status_notification(
                return_number=obj.return_number,
                from_status=previous_status,
                to_status=target_status,
                actor_name=actor_name,
            )
        )

        if target_status == ReturnRequest.STATUS_ACCEPTED:
            self._fill_accepted_quantities_for_legacy_returns(obj=obj)

        payload = BackofficeReturnOperationalDetailSerializer(
            get_operational_returns_queryset().get(id=obj.id),
            context={"request": request},
        ).data
        return Response(payload, status=status.HTTP_200_OK)

    @staticmethod
    def _check_status_capability(*, request, target_status: str) -> None:
        capability = "returns.manage"
        if target_status == ReturnRequest.STATUS_APPROVED:
            capability = "returns.approve"
        elif target_status == ReturnRequest.STATUS_REJECTED:
            capability = "returns.reject"
        elif target_status == ReturnRequest.STATUS_REFUNDED:
            capability = "returns.refund"

        if not user_has_capability(request.user, capability):
            raise PermissionDenied("Insufficient capability for this transition.")

    @staticmethod
    def _apply_approved_items(*, obj: ReturnRequest, approved_items_payload: list[dict], approved_items_provided: bool) -> None:
        items = list(obj.items.all())
        by_id = {str(item.id): item for item in items}
        requested_by_id = {item_id: max(0, int(item.quantity_requested or 0)) for item_id, item in by_id.items()}

        if approved_items_provided:
            if not approved_items_payload:
                raise ValidationError({"approved_items": "At least one approved item payload entry is required."})
            approved_map: dict[str, int] = {}
            for row in approved_items_payload:
                item_id = str(row.get("item_id") or "")
                if not item_id or item_id not in by_id:
                    raise ValidationError({"approved_items": "Unknown return item in approved_items payload."})
                approved_qty = max(0, int(row.get("quantity_approved") or 0))
                max_requested = requested_by_id[item_id]
                if approved_qty > max_requested:
                    raise ValidationError({"approved_items": "Approved quantity exceeds requested quantity."})
                approved_map[item_id] = approved_qty
        else:
            approved_map = {item_id: requested_qty for item_id, requested_qty in requested_by_id.items()}

        if not any(approved_map.get(item_id, 0) > 0 for item_id in requested_by_id):
            raise ValidationError({"approved_items": "At least one item must remain approved."})

        total_refund = Decimal("0.00")
        for item_id, item in by_id.items():
            approved_qty = max(0, int(approved_map.get(item_id, 0)))
            line_refund = (Decimal(item.original_unit_price or "0") * Decimal(approved_qty)).quantize(Decimal("0.01"))
            if int(item.quantity_approved or 0) != approved_qty or Decimal(item.refund_amount or "0") != line_refund:
                item.quantity_approved = approved_qty
                item.refund_amount = line_refund
                item.save(update_fields=("quantity_approved", "refund_amount", "updated_at"))
            total_refund += line_refund

        obj.refund_amount = total_refund.quantize(Decimal("0.01"))

    @staticmethod
    def _fill_accepted_quantities_for_legacy_returns(*, obj: ReturnRequest) -> None:
        items = list(obj.items.all())
        if not items:
            return
        # Legacy safety: older approved flows may still have all zeros.
        if any(int(item.quantity_approved or 0) > 0 for item in items):
            return

        total_refund = Decimal("0.00")
        for item in items:
            approved_qty = max(0, int(item.quantity_requested or 0))
            line_refund = (Decimal(item.original_unit_price or "0") * Decimal(approved_qty)).quantize(Decimal("0.01"))
            item.quantity_approved = approved_qty
            item.refund_amount = line_refund
            item.save(update_fields=("quantity_approved", "refund_amount", "updated_at"))
            total_refund += line_refund
        obj.refund_amount = total_refund.quantize(Decimal("0.01"))
        obj.save(update_fields=("refund_amount", "updated_at"))
