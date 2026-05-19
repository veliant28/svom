from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.services import get_product_display_sku
from apps.catalog.services.product_sku import get_product_catalog_article
from apps.commerce.api.serializers import (
    CreateReturnRequestInputSerializer,
    EligibleOrderListSerializer,
    ReturnRequestDetailSerializer,
    ReturnRequestListSerializer,
    SubmitReturnTrackingInputSerializer,
)
from apps.commerce.models import Order, OrderItem, ReturnEvent, ReturnRequest, ReturnRequestItem
from apps.commerce.services import (
    build_returnable_order_items,
    format_tracking_number,
    generate_return_number,
    get_returns_settings,
    is_order_return_window_open,
    is_tracking_edit_window_open,
    sum_refund_amount,
)
from apps.core.services import send_ops_return_created_notification, send_ops_return_status_notification


RETURNS_DISABLED_MESSAGE = "Сервис возвратов временно недоступен"


def _ensure_returns_enabled() -> None:
    settings_obj = get_returns_settings()
    if not settings_obj.returns_enabled:
        raise ValidationError({"detail": RETURNS_DISABLED_MESSAGE})


class ReturnRequestListAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_returns_enabled()
        queryset = (
            ReturnRequest.objects.filter(user=request.user)
            .select_related("order")
            .order_by("-created_at")
        )
        return Response(ReturnRequestListSerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        return ReturnRequestCreateAPIView().post(request)


class ReturnRequestDetailAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        _ensure_returns_enabled()
        obj = get_object_or_404(
            ReturnRequest.objects.filter(user=request.user)
            .select_related("order")
            .prefetch_related("items__product"),
            id=id,
        )
        return Response(ReturnRequestDetailSerializer(obj, context={"request": request}).data, status=status.HTTP_200_OK)


class EligibleReturnOrdersAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_returns_enabled()
        queryset = (
            Order.objects.filter(user=request.user, status=Order.STATUS_COMPLETED)
            .exclude(received_at__isnull=True)
            .exclude(return_eligible_until__isnull=True)
            .annotate(items_count=Count("items"))
            .prefetch_related("items__product", "items__product__category")
            .order_by("-placed_at")
        )
        rows = []
        locale = getattr(request, "LANGUAGE_CODE", "uk")
        for order in queryset:
            if not is_order_return_window_open(order, now=timezone.now()):
                continue
            # Hide orders that no longer have any actually returnable quantity.
            returnable_items = build_returnable_order_items(order=order, locale=locale)
            if not any(item.is_returnable for item in returnable_items):
                continue
            rows.append(order)
        return Response(EligibleOrderListSerializer(rows, many=True).data, status=status.HTTP_200_OK)


class EligibleReturnOrderDetailAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        _ensure_returns_enabled()
        order = get_object_or_404(
            Order.objects.filter(user=request.user).prefetch_related("items__product", "items__product__images", "items__product__category"),
            id=order_id,
        )
        if not is_order_return_window_open(order, now=timezone.now()):
            raise ValidationError({"detail": "Order is not eligible for return."})

        returnable_items = build_returnable_order_items(order=order, locale=getattr(request, "LANGUAGE_CODE", "uk"))
        payload_items = []
        for item in returnable_items:
            order_item = item.order_item
            product = order_item.product
            primary_image = ""
            product_images = list(getattr(product, "images", []).all()) if hasattr(product, "images") else []
            if product_images:
                product_images.sort(key=lambda row: (not bool(getattr(row, "is_primary", False)), int(getattr(row, "sort_order", 0) or 0)))
                image_obj = product_images[0]
                image_field = getattr(image_obj, "image", None)
                if image_field:
                    primary_image = str(getattr(image_field, "url", "") or "")
                if not primary_image:
                    primary_image = str(getattr(image_obj, "remote_url", "") or "").strip()
            payload_items.append(
                {
                    "order_item_id": str(order_item.id),
                    "product_id": str(product.id),
                    "product": {
                        "id": str(product.id),
                        "sku": get_product_display_sku(product),
                        "article": get_product_catalog_article(product),
                        "name": product.get_localized_name(getattr(request, "LANGUAGE_CODE", "uk")),
                        "slug": str(product.slug or ""),
                        "brand_name": str(product.display_brand_name or product.autodb_supplier_name or "").strip(),
                        "primary_image": primary_image,
                        "final_price": str(order_item.unit_price),
                        "currency": str(order.currency or "UAH"),
                    },
                    "product_name": order_item.product_name,
                    "product_sku": order_item.product_sku,
                    "quantity_ordered": int(order_item.quantity),
                    "max_return_quantity": int(item.max_return_quantity),
                    "unit_price": str(order_item.unit_price),
                    "line_total": str(order_item.line_total),
                    "is_returnable": bool(item.is_returnable),
                    "non_returnable_reason": item.non_returnable_reason,
                }
            )

        return Response(
            {
                "order": {
                    "id": str(order.id),
                    "order_number": order.order_number,
                    "status": order.status,
                    "total": str(order.total),
                    "currency": order.currency,
                    "placed_at": order.placed_at,
                    "return_day_label": EligibleOrderListSerializer(order).data.get("return_day_label", ""),
                },
                "items": payload_items,
            },
            status=status.HTTP_200_OK,
        )


class ReturnRequestCreateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        _ensure_returns_enabled()
        serializer = CreateReturnRequestInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(
            Order.objects.filter(user=request.user).prefetch_related("items__product", "items__product__category"),
            id=serializer.validated_data["order_id"],
        )
        if not is_order_return_window_open(order, now=timezone.now()):
            raise ValidationError({"detail": "Order is not eligible for return."})

        reason_comment = str(serializer.validated_data.get("reason_comment") or "").strip()
        if not reason_comment:
            raise ValidationError({"reason_comment": "Укажите причину возврата"})

        items_payload = serializer.validated_data.get("items") or []
        if not items_payload:
            raise ValidationError({"items": "Выберите хотя бы одну позицию"})

        returnable_items = build_returnable_order_items(order=order, locale=getattr(request, "LANGUAGE_CODE", "uk"))
        returnable_by_id = {str(item.order_item.id): item for item in returnable_items}
        unique_ids: set[str] = set()
        refund_lines: list[tuple[OrderItem, int]] = []

        for row in items_payload:
            order_item_id = str(row.get("order_item_id") or "")
            if not order_item_id:
                continue
            if order_item_id in unique_ids:
                raise ValidationError({"items": "Duplicate order item in request."})
            unique_ids.add(order_item_id)
            quantity = int(row.get("quantity") or 0)
            if quantity <= 0:
                raise ValidationError({"items": "Quantity must be greater than zero."})

            returnable_meta = returnable_by_id.get(order_item_id)
            if returnable_meta is None:
                raise ValidationError({"items": "Order item is not eligible for return."})
            if not returnable_meta.is_returnable:
                raise ValidationError({"items": returnable_meta.non_returnable_reason or "Item is not returnable."})
            if quantity > returnable_meta.max_return_quantity:
                raise ValidationError({"items": "Requested quantity exceeds available return quantity."})

            order_item = returnable_meta.order_item
            refund_lines.append((order_item, quantity))

        if not refund_lines:
            raise ValidationError({"items": "Выберите хотя бы одну позицию"})

        total_refund = sum_refund_amount(refund_lines) if refund_lines else Decimal("0.00")

        return_request = ReturnRequest.objects.create(
            user=request.user,
            order=order,
            return_number=generate_return_number(),
            status=ReturnRequest.STATUS_NEW,
            reason_comment=reason_comment,
            refund_amount=total_refund,
            refund_status=ReturnRequest.REFUND_STATUS_NONE,
        )

        item_objects: list[ReturnRequestItem] = []
        for order_item, quantity in refund_lines:
            line_refund = (Decimal(order_item.unit_price or "0") * Decimal(quantity)).quantize(Decimal("0.01"))
            returnable_meta = returnable_by_id[str(order_item.id)]
            item_objects.append(
                ReturnRequestItem(
                    return_request=return_request,
                    order_item=order_item,
                    product=order_item.product,
                    product_name_snapshot=order_item.product_name,
                    product_sku_snapshot=order_item.product_sku,
                    quantity_ordered=int(order_item.quantity),
                    quantity_requested=int(quantity),
                    quantity_approved=0,
                    original_unit_price=order_item.unit_price,
                    original_line_total=order_item.line_total,
                    refund_amount=line_refund,
                    is_returnable_snapshot=returnable_meta.is_returnable,
                    non_returnable_reason_snapshot=returnable_meta.non_returnable_reason,
                )
            )
        ReturnRequestItem.objects.bulk_create(item_objects)
        ReturnEvent.objects.create(
            return_request=return_request,
            actor=request.user,
            from_status="",
            to_status=ReturnRequest.STATUS_NEW,
            comment=reason_comment[:500],
            metadata={"created_by_customer": True},
        )
        actor_name = (request.user.get_full_name() or "").strip() or str(request.user.email or "").strip()
        transaction.on_commit(
            lambda: send_ops_return_created_notification(
                return_number=return_request.return_number,
                order_number=order.order_number,
                actor_name=actor_name,
            )
        )

        payload = ReturnRequestDetailSerializer(
            ReturnRequest.objects.select_related("order")
            .prefetch_related("items__product")
            .get(id=return_request.id),
            context={"request": request},
        ).data
        return Response(payload, status=status.HTTP_201_CREATED)


class ReturnRequestTrackingSubmitAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, id):
        _ensure_returns_enabled()
        serializer = SubmitReturnTrackingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        normalized_tracking = serializer.validated_data["tracking_number"]

        obj = get_object_or_404(ReturnRequest.objects.filter(user=request.user), id=id)
        if obj.status in {ReturnRequest.STATUS_APPROVED, ReturnRequest.STATUS_AWAITING_TTN}:
            pass
        elif obj.status == ReturnRequest.STATUS_IN_TRANSIT:
            if not is_tracking_edit_window_open(submitted_at=obj.customer_return_tracking_submitted_at):
                raise ValidationError({"detail": "Tracking number edit window has expired."})
        else:
            raise ValidationError({"detail": "Tracking number can be submitted only for approved return."})

        previous_status = obj.status
        submitted_at = obj.customer_return_tracking_submitted_at or timezone.now()
        obj.customer_return_tracking_number = normalized_tracking
        obj.customer_return_tracking_submitted_at = submitted_at
        obj.status = ReturnRequest.STATUS_IN_TRANSIT
        obj.save(
            update_fields=(
                "customer_return_tracking_number",
                "customer_return_tracking_submitted_at",
                "status",
                "updated_at",
            )
        )
        ReturnEvent.objects.create(
            return_request=obj,
            actor=request.user,
            from_status=previous_status,
            to_status=ReturnRequest.STATUS_IN_TRANSIT,
            comment=f"ТТН: {format_tracking_number(normalized_tracking)}",
            metadata={"tracking_number": normalized_tracking},
        )
        actor_name = (request.user.get_full_name() or "").strip() or str(request.user.email or "").strip()
        transaction.on_commit(
            lambda: send_ops_return_status_notification(
                return_number=obj.return_number,
                from_status=previous_status,
                to_status=ReturnRequest.STATUS_IN_TRANSIT,
                actor_name=actor_name,
            )
        )

        return Response(
            {
                "id": str(obj.id),
                "status": obj.status,
                "tracking_number": format_tracking_number(obj.customer_return_tracking_number),
                "customer_return_tracking_submitted_at": obj.customer_return_tracking_submitted_at,
            },
            status=status.HTTP_200_OK,
        )
