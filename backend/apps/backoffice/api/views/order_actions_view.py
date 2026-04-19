from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.serializers import (
    OrderActionSerializer,
    OrderBulkActionSerializer,
    OrderCancelActionSerializer,
    OrderItemSupplierOverrideSerializer,
    OrderReserveActionSerializer,
    OrderSupplierCancelSerializer,
    OrderSupplierCreateSerializer,
    OrderSupplierPayloadSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.api.views.supplier_workspace_views import supplier_action_error_response
from apps.backoffice.services import OrderOperationsService, OrderSupplierService
from apps.commerce.models import Order, OrderItem
from apps.pricing.models import SupplierOffer


class ConfirmOrderActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        result = OrderOperationsService().confirm_order(
            order=order,
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response({"order_id": result.order_id, "status": result.status})


class MarkAwaitingProcurementActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        result = OrderOperationsService().mark_awaiting_procurement(
            order=order,
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response({"order_id": result.order_id, "status": result.status})


class ReserveOrderItemsActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderReserveActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        result = OrderOperationsService().reserve_items(
            order=order,
            item_ids=[str(item_id) for item_id in serializer.validated_data.get("item_ids", [])],
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response({"order_id": result.order_id, "status": result.status})


class ReadyToShipOrderActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        result = OrderOperationsService().mark_ready_to_ship(
            order=order,
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response({"order_id": result.order_id, "status": result.status})


class CancelOrderActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderCancelActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        result = OrderOperationsService().cancel_order(
            order=order,
            reason_code=serializer.validated_data["reason_code"],
            reason_note=serializer.validated_data.get("reason_note", ""),
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response({"order_id": result.order_id, "status": result.status})


class BulkConfirmOrdersActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = OrderOperationsService().bulk_confirm(
            order_ids=[str(order_id) for order_id in serializer.validated_data["order_ids"]],
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response(result)


class BulkAwaitingProcurementActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = OrderOperationsService().bulk_mark_awaiting_procurement(
            order_ids=[str(order_id) for order_id in serializer.validated_data["order_ids"]],
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response(result)


class DeleteOrderActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        try:
            result = OrderOperationsService().delete_order(
                order=order,
                operator_note=serializer.validated_data.get("operator_note", ""),
            )
        except ValidationError as exc:
            return Response({"detail": _extract_validation_reason(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result)


class BulkDeleteOrdersActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = OrderOperationsService().bulk_delete(
            order_ids=[str(order_id) for order_id in serializer.validated_data["order_ids"]],
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response(result)


class OrderItemSupplierRecommendationAPIView(BackofficeAPIView):
    def get(self, request, item_id):
        item = get_object_or_404(
            OrderItem.objects.select_related(
                "order",
                "product",
                "selected_supplier_offer",
                "selected_supplier_offer__supplier",
                "recommended_supplier_offer",
                "recommended_supplier_offer__supplier",
            ),
            id=item_id,
        )
        payload = OrderOperationsService().supplier_recommendation_for_item(item=item)
        return Response(payload)


class OrderItemSupplierOverrideAPIView(BackofficeAPIView):
    def post(self, request, item_id):
        serializer = OrderItemSupplierOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = get_object_or_404(
            OrderItem.objects.select_related(
                "order",
                "product",
                "selected_supplier_offer",
                "recommended_supplier_offer",
            ),
            id=item_id,
        )
        offer = get_object_or_404(
            SupplierOffer.objects.select_related("supplier"),
            id=serializer.validated_data["supplier_offer_id"],
        )

        payload = OrderOperationsService().set_supplier_for_item(
            item=item,
            supplier_offer=offer,
            operator_note=serializer.validated_data.get("operator_note", ""),
        )
        return Response(payload)


class GplOrdersListRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, min_value=1, default=1)


class GplSupplierOrdersListAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = GplOrdersListRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        try:
            payload = OrderSupplierService().list_gpl_orders(page=serializer.validated_data["page"])
        except Exception as exc:
            return supplier_action_error_response(exc)

        return Response(payload)


class GplSupplierOrderDetailAPIView(BackofficeAPIView):
    def post(self, request, supplier_order_id: int):
        try:
            payload = OrderSupplierService().show_gpl_order(supplier_order_id=supplier_order_id)
        except Exception as exc:
            return supplier_action_error_response(exc)

        return Response(payload)


class GplOrderPayloadPreviewAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderSupplierPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        payload = OrderSupplierService().get_gpl_payload_preview(order=order)
        return Response(payload)


class GplCreateOrderAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderSupplierCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        try:
            payload = OrderSupplierService().create_gpl_order_for_local_order(
                order=order,
                products=serializer.validated_data.get("products"),
                test_mode=serializer.validated_data.get("test", False),
            )
        except Exception as exc:
            return supplier_action_error_response(exc)

        return Response(payload, status=status.HTTP_201_CREATED)


class GplCancelOrderAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = OrderSupplierCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=serializer.validated_data["order_id"])
        try:
            payload = OrderSupplierService().cancel_gpl_order_for_local_order(
                order=order,
                supplier_order_id=serializer.validated_data["supplier_order_id"],
            )
        except Exception as exc:
            return supplier_action_error_response(exc)

        return Response(payload)


def _extract_validation_reason(error: ValidationError) -> str:
    if hasattr(error, "message_dict"):
        values = list(error.message_dict.values())
        if values and isinstance(values[0], list) and values[0]:
            return str(values[0][0])
    if hasattr(error, "messages") and error.messages:
        return str(error.messages[0])
    return str(error)
